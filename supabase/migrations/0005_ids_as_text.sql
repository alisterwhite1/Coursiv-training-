-- The app generates its own investigation/NCR ids as strings like
-- "rec_mrx9smsju8j4td" or "ncr_...", not real UUIDs — and it always
-- supplies its own id rather than relying on a database-generated one.
-- The original schema declared these columns as `uuid`, which rejects
-- every id the app actually produces ("invalid input syntax for type
-- uuid"). This affects every investigation/NCR ever created by the
-- app, not just the legacy-data import.
--
-- Fix: change investigations.id and ncrs.id (and everything that
-- references them) to plain text.

-- Drop the ncr_attachments policies first — they reference ncrs.id and
-- ncr_attachments.ncr_id inside a subquery, and Postgres won't allow
-- altering a column's type while an RLS policy depends on it.
drop policy if exists "members can view ncr_attachments" on ncr_attachments;
drop policy if exists "members can manage ncr_attachments" on ncr_attachments;

-- Drop FKs that reference these columns so the type change isn't blocked.
alter table ncrs drop constraint if exists ncrs_linked_investigation_id_fkey;
alter table investigations drop constraint if exists investigations_linked_ncr_id_fkey;
alter table ncr_attachments drop constraint if exists ncr_attachments_ncr_id_fkey;

alter table investigations alter column id type text;
alter table investigations alter column id drop default;
alter table investigations alter column linked_ncr_id type text;

alter table ncrs alter column id type text;
alter table ncrs alter column id drop default;
alter table ncrs alter column linked_investigation_id type text;

alter table ncr_attachments alter column ncr_id type text;

-- Recreate the foreign keys with matching (text) types.
alter table ncrs
  add constraint ncrs_linked_investigation_id_fkey
  foreign key (linked_investigation_id) references investigations(id);

alter table investigations
  add constraint investigations_linked_ncr_id_fkey
  foreign key (linked_ncr_id) references ncrs(id);

alter table ncr_attachments
  add constraint ncr_attachments_ncr_id_fkey
  foreign key (ncr_id) references ncrs(id) on delete cascade;

-- Recreate the ncr_attachments policies (unchanged definitions).
create policy "members can view ncr_attachments" on ncr_attachments
  for select using (is_project_member((select project_id from ncrs where ncrs.id = ncr_id)));
create policy "members can manage ncr_attachments" on ncr_attachments
  for all using (is_project_member((select project_id from ncrs where ncrs.id = ncr_id)));
