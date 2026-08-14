-- Verity Checker — migration 001
-- Run in the Supabase SQL editor after the initial schema.sql

-- Add findings storage, publish state, human verdict, and persona to reviews
alter table reviews
  add column if not exists findings     jsonb,          -- array of {section, requirement, finding, ai_status, decision}
  add column if not exists published    boolean not null default false,
  add column if not exists final_verdict text,           -- human-confirmed verdict after Publish
  add column if not exists final_score  int,             -- human-confirmed score after Publish
  add column if not exists persona      text;            -- 'engineer' | 'contractor'

-- Index for the Validation tab list queries
create index if not exists reviews_published_idx on reviews(user_id, published, created_at desc);
