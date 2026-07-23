-- Attachments stored as a JSON column directly on ncrs, matching the app's
-- existing in-memory shape ({name, type, dataUrl}). Simpler and lower-risk
-- than wiring up Supabase Storage + signed URLs for this first pass — the
-- ncr_attachments/storage bucket approach from 0001 remains unused for now
-- and can be adopted later as an optimization if attachment volume grows.

alter table ncrs
  add column if not exists attachments jsonb not null default '[]'::jsonb;
