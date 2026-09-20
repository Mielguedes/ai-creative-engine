-- Execute no SQL Editor do mesmo projeto Supabase usado pelo Loop de Live.
create table if not exists public.app_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text,
  enabled boolean not null default false,
  plan text not null default 'monthly',
  expires_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.app_access enable row level security;

 drop policy if exists "Usuário pode consultar seu próprio acesso" on public.app_access;
create policy "Usuário pode consultar seu próprio acesso"
on public.app_access
for select
to authenticated
using (user_id = auth.uid());

-- Depois de executar, cadastre manualmente cada comprador autorizado:
-- insert into public.app_access (user_id, email, enabled, plan, expires_at)
-- values ('UUID_DO_USUARIO', 'email@cliente.com', true, 'monthly', now() + interval '30 days');
