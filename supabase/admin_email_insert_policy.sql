-- Permite ao administrador cadastrar um acesso informando apenas o e-mail.
-- A conta precisa existir no Supabase Auth para conseguir fazer login.

ALTER TABLE public.app_access
ADD COLUMN IF NOT EXISTS email TEXT;

ALTER TABLE public.app_access
ALTER COLUMN user_id DROP NOT NULL;

DROP POLICY IF EXISTS app_access_admin_insert ON public.app_access;

CREATE POLICY app_access_admin_insert
ON public.app_access
FOR INSERT
TO authenticated
WITH CHECK (
  public.is_app_access_admin()
);
