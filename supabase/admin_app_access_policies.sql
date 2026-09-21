-- Políticas seguras para permitir que administradores gerenciem app_access.
-- Execute este arquivo no Supabase SQL Editor.
-- Não coloque service_role key no Streamlit.

create or replace function public.is_app_access_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.app_access aa
    where aa.user_id = auth.uid()
      and aa.enabled = true
      and aa.plan = 'admin'
      and (aa.expires_at is null or aa.expires_at > now())
  );
$$;

revoke all on function public.is_app_access_admin() from public;
grant execute on function public.is_app_access_admin() to authenticated;

alter table public.app_access enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'app_access'
      and policyname = 'app_access_admin_select'
  ) then
    create policy app_access_admin_select
      on public.app_access
      for select
      to authenticated
      using (public.is_app_access_admin() or user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'app_access'
      and policyname = 'app_access_admin_update'
  ) then
    create policy app_access_admin_update
      on public.app_access
      for update
      to authenticated
      using (public.is_app_access_admin())
      with check (public.is_app_access_admin());
  end if;
end
$$;
