-- Verity Checker — Supabase schema
-- Run this in the SQL editor of a NEW, dedicated Supabase project.
-- Supabase Auth handles the users table automatically.

-- ── Projects ─────────────────────────────────────────────────────────────────
-- Each row is one user's named project context. No sharing, no members.
create table if not exists projects (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- Users can only see and touch their own projects
alter table projects enable row level security;
create policy "projects: owner only"
  on projects for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create index on projects(user_id, created_at desc);

-- ── Reviews ──────────────────────────────────────────────────────────────────
-- One row per compliance check run. Scoped to a user (and optionally a project).
create table if not exists reviews (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references auth.users(id) on delete cascade,
  project_id         uuid references projects(id) on delete set null,
  submitted_filename text,
  spec_filename      text,
  query_text         text,          -- populated when query mode was used
  report_markdown    text,          -- the full AI-generated report
  verdict            text,          -- 'Approved' / 'Approved with Comments' / 'Reject — Resubmit'
  score              int,           -- 0-100
  created_at         timestamptz not null default now()
);

alter table reviews enable row level security;
create policy "reviews: owner only"
  on reviews for all
  using  (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create index on reviews(user_id, created_at desc);
create index on reviews(project_id);

-- ── Updated-at trigger ───────────────────────────────────────────────────────
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

create trigger projects_updated_at
  before update on projects
  for each row execute function set_updated_at();
