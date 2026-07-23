-- Adds a flexible column for project_config settings added after the initial
-- schema (branding, taxonomy lists, attachment limits) so future new settings
-- don't each need their own migration.

alter table project_config
  add column if not exists extra jsonb not null default '{}'::jsonb;
