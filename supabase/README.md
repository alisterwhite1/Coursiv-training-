# SiteAssure Supabase Backend

This replaces the app's current storage — everything lives in one
browser's `localStorage` today, which means no shared NCR register
across a team and no backup if browser data is cleared. This schema
moves that to a real, shared, multi-user backend.

**Status: schema is applied-ready, and the app now has an experimental
sign-in wired up under Configuration → Account.** The migration below
has been tested against a local Postgres instance and runs cleanly.
Sign-in is additive only — it doesn't gate the app yet, so it can be
tested safely before the CRUD migration (localStorage → real Supabase
reads/writes) makes it load-bearing.

## Testing sign-in

1. Open the app, tap the gear icon → scroll to **Account**
2. Enter your email, tap **Send Sign-In Code**
3. Check your inbox for a 6-digit code (check spam if it doesn't arrive
   within a minute or two)
4. Enter the code, tap **Verify Code**

This uses an emailed one-time code rather than a clickable magic link,
since the app runs as a local file with no stable web address for a
link to redirect back to — codes sidestep that entirely and will keep
working the same way once the app is hosted or packaged as a native app.

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

- Every localStorage read/write in the app needs to be swapped for a
  Supabase query (the big remaining piece)
- A way to create your first project and add yourself as `owner` — once
  you've signed in at least once (so your row exists in `auth.users`),
  run this once in the SQL Editor, replacing the email:

  ```sql
  insert into projects (name) values ('My First Project')
  returning id;  -- copy this id for the next statement

  insert into project_members (project_id, user_id, role)
  select '<paste-project-id-here>', id, 'owner'
  from auth.users where email = 'you@company.com';
  ```

Nothing above needs to be actioned by you yet except applying the
migration and creating the bucket, whenever you're ready to move
forward with this piece.
