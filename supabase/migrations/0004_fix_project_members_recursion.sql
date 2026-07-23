-- Fixes "infinite recursion detected in policy for relation project_members".
--
-- The original "owners/admins can manage members" policy queried
-- project_members directly inside its own USING clause. Evaluating that
-- policy on a row re-triggers RLS on project_members, which re-evaluates
-- the same policy — infinite recursion.
--
-- Fix: route the check through a SECURITY DEFINER function instead (same
-- pattern as is_project_member). Functions like this run as the function's
-- owner, which owns the table, so the owner bypasses RLS on the internal
-- query — breaking the recursion.

create or replace function is_project_admin(p_project_id uuid)
returns boolean language sql security definer stable as $$
  select exists (
    select 1 from project_members
    where project_id = p_project_id and user_id = auth.uid() and role in ('owner', 'admin')
  );
$$;

drop policy if exists "owners/admins can manage members" on project_members;
create policy "owners/admins can manage members" on project_members
  for all using (is_project_admin(project_id));
