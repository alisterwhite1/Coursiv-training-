-- SiteAssure RCA Navigator — initial schema
-- Maps the app's current localStorage model onto Supabase/Postgres tables.
-- Run this once in the Supabase SQL Editor (Dashboard > SQL Editor > New query > paste > Run)
-- on a fresh project before the app is pointed at it.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Projects: a project is a site/contract with its own NCR numbering scheme
-- and its own set of NCRs/investigations. Replaces the single-tenant,
-- one-browser localStorage model with something a team can share.
-- ---------------------------------------------------------------------------
create table projects (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now(),
  created_by uuid references auth.users(id)
);

create table project_members (
  project_id uuid not null references projects(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member')),
  created_at timestamptz not null default now(),
  primary key (project_id, user_id)
);

-- One row per project. Mirrors rcaNavigatorProjectConfig (NCR numbering
-- format + the optional AI-suggestions Worker URL).
create table project_config (
  project_id uuid primary key references projects(id) on delete cascade,
  prefix text not null default 'NCR',
  include_year boolean not null default true,
  year_format text not null default 'YYYY' check (year_format in ('YYYY', 'YY')),
  sequence_digits int not null default 3,
  separator text not null default '-',
  reset_yearly boolean not null default false,
  ai_worker_url text
);

-- ---------------------------------------------------------------------------
-- Investigations: mirrors rcaNavigatorState (the in-progress one) and each
-- entry in rcaNavigatorLibrary (saved ones) — same shape either way, an
-- investigation is just "concluded_node_id is null" while still in progress.
-- ---------------------------------------------------------------------------
create table investigations (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  schema_version int not null default 2,
  fault_title text not null default '',
  evidence jsonb not null default '{}'::jsonb,       -- { [nodeId]: "evidence text" }
  nav_path int[] not null default '{1}',
  concluded_node_id int,
  concluded_path int[],
  capa jsonb not null default '{
    "correctiveAction": "", "preventiveAction": "", "owner": "", "targetDate": "",
    "approvedBy": "", "approvedDate": "", "approved": false
  }'::jsonb,
  linked_ncr_id uuid,                                 -- FK added after ncrs exists (see below)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id)
);

-- ---------------------------------------------------------------------------
-- NCRs: mirrors rcaNavigatorNcrState / rcaNavigatorNcrLibrary.
-- ---------------------------------------------------------------------------
create table ncrs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  schema_version int not null default 1,
  ncr_number text not null,
  date_raised date,
  respondent text default '',
  ncr_reason text default '',
  source text default '',
  location text default '',
  geo_lat double precision,
  geo_lng double precision,
  description text default '',
  requirement_ref text default '',
  reference_docs text default '',
  supporting_evidence text default '',
  raised_by text default '',
  raised_by_date date,
  approved_by_qm text default '',
  approved_by_qm_date date,
  disposition_type text default '',
  proposed_correction text default '',
  closure_date_agreed date,
  proposed_by text default '',
  proposed_by_date date,
  correction_acceptance text default '',
  acceptance_notes text default '',
  accepted_by_qm text default '',
  accepted_by_qm_date date,
  ca_required boolean,
  ca_number text default '',
  linked_investigation_id uuid references investigations(id),
  root_cause_text text default '',
  ncr_owner_remarks text default '',
  qm_remarks text default '',
  confirmed_by text default '',
  confirmed_by_date date,
  ca_verified_by text default '',
  ca_verified_by_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by uuid references auth.users(id),
  unique (project_id, ncr_number)
);

alter table investigations
  add constraint investigations_linked_ncr_id_fkey
  foreign key (linked_ncr_id) references ncrs(id);

-- Attachments move out of a base64 jsonb blob (how localStorage stored
-- them) and into Supabase Storage. This table just indexes what's in the
-- 'ncr-attachments' storage bucket against the NCR it belongs to.
create table ncr_attachments (
  id uuid primary key default gen_random_uuid(),
  ncr_id uuid not null references ncrs(id) on delete cascade,
  name text not null,
  type text not null check (type in ('Photo', 'Document', 'Other')),
  storage_path text not null,          -- path within the 'ncr-attachments' bucket
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- updated_at auto-touch triggers
-- ---------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger investigations_set_updated_at
  before update on investigations
  for each row execute function set_updated_at();

create trigger ncrs_set_updated_at
  before update on ncrs
  for each row execute function set_updated_at();

-- ---------------------------------------------------------------------------
-- Row Level Security: a user can only see/edit rows in projects they belong to.
-- ---------------------------------------------------------------------------
alter table projects enable row level security;
alter table project_members enable row level security;
alter table project_config enable row level security;
alter table investigations enable row level security;
alter table ncrs enable row level security;
alter table ncr_attachments enable row level security;

create or replace function is_project_member(p_project_id uuid)
returns boolean language sql security definer stable as $$
  select exists (
    select 1 from project_members
    where project_id = p_project_id and user_id = auth.uid()
  );
$$;

create policy "members can view their projects" on projects
  for select using (is_project_member(id));
create policy "members can create projects" on projects
  for insert with check (true);

create policy "members can view project_members rows for their projects" on project_members
  for select using (is_project_member(project_id));
create policy "owners/admins can manage members" on project_members
  for all using (
    exists (
      select 1 from project_members pm
      where pm.project_id = project_members.project_id
        and pm.user_id = auth.uid()
        and pm.role in ('owner', 'admin')
    )
  );

create policy "members can view project_config" on project_config
  for select using (is_project_member(project_id));
create policy "members can manage project_config" on project_config
  for all using (is_project_member(project_id));

create policy "members can view investigations" on investigations
  for select using (is_project_member(project_id));
create policy "members can manage investigations" on investigations
  for all using (is_project_member(project_id));

create policy "members can view ncrs" on ncrs
  for select using (is_project_member(project_id));
create policy "members can manage ncrs" on ncrs
  for all using (is_project_member(project_id));

create policy "members can view ncr_attachments" on ncr_attachments
  for select using (is_project_member((select project_id from ncrs where ncrs.id = ncr_id)));
create policy "members can manage ncr_attachments" on ncr_attachments
  for all using (is_project_member((select project_id from ncrs where ncrs.id = ncr_id)));
