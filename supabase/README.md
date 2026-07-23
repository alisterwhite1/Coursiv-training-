# SiteAssure Supabase Backend

This replaces the app's current storage — everything lives in one
browser's `localStorage` today, which means no shared NCR register
across a team and no backup if browser data is cleared. This schema
moves that to a real, shared, multi-user backend.

**Status: schema only, not yet wired into the app.** The migration
below has been tested against a local Postgres instance and runs
cleanly, but the app itself doesn't talk to Supabase yet — that's the
next piece of work.

## What's in the schema (`migrations/0001_init.sql`)

| Table | Mirrors (today's localStorage) | Notes |
|---|---|---|
| `projects` | — (new concept) | A site/contract. Everything else belongs to one. |
| `project_members` | — (new concept) | Who can see/edit a project's data, with a role. |
| `project_config` | `rcaNavigatorProjectConfig` | NCR numbering format + the AI Worker URL, per project instead of per browser. |
| `investigations` | `rcaNavigatorState` + `rcaNavigatorLibrary` | One row per investigation — in progress or concluded. |
| `ncrs` | `rcaNavigatorNcrState` + `rcaNavigatorNcrLibrary` | One row per NCR. |
| `ncr_attachments` | the `attachments` array on each NCR | Photos/PDFs move out of inline base64 into a Supabase Storage bucket (`ncr-attachments`); this table just indexes what's there. |

Row Level Security is enabled on every table: a user can only see or
edit rows in a project they're a member of (`project_members`).

## Applying it to your Supabase project

1. Go to your project at **supabase.com/dashboard**
2. Open **SQL Editor** (left sidebar)
3. Click **"New query"**
4. Paste the entire contents of `migrations/0001_init.sql`
5. Click **Run**

That creates all the tables, triggers, and security policies in one go.

## One more manual step: the attachments bucket

1. In the Supabase dashboard, go to **Storage**
2. Click **"New bucket"**, name it exactly `ncr-attachments`
3. Leave it **private** (not public) — access is controlled through the
   app's Supabase auth session, same as the database rows

## What's still needed before this is live

- The app needs the Supabase client wired in, with your project URL and
  anon/public key (safe to share client-side — never the service_role key)
- Every localStorage read/write in the app needs to be swapped for a
  Supabase query
- Basic sign-in (Supabase Auth) so `project_members` has someone to check
  against
- A way to create your first project and add yourself as `owner` (there's
  no UI for that yet — for the very first project, this can be a couple
  of manual inserts run once in the SQL Editor while the app screens for
  it get built)

This is being built next — nothing above needs to be actioned by you
yet except applying the migration and creating the bucket, whenever
you're ready to move forward with this piece.
