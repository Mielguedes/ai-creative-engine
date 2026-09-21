-- Execute este SQL uma única vez no SQL Editor do Supabase.
-- O e-mail precisa pertencer a uma conta já criada em Authentication > Users.

DROP FUNCTION IF EXISTS public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT);

CREATE OR REPLACE FUNCTION public.admin_upsert_access_by_email(
    p_email TEXT,
    p_enabled BOOLEAN DEFAULT TRUE,
    p_plan TEXT DEFAULT 'monthly'
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    v_user_id UUID;
    v_plan TEXT;
    v_expires_at TIMESTAMPTZ;
BEGIN
    IF NOT public.is_app_access_admin() THEN
        RAISE EXCEPTION 'Apenas administradores podem cadastrar acessos';
    END IF;

    IF p_email IS NULL OR btrim(p_email) = '' OR position('@' IN btrim(p_email)) = 0 THEN
        RAISE EXCEPTION 'Informe um e-mail válido';
    END IF;

    v_plan := CASE lower(btrim(coalesce(p_plan, 'monthly')))
        WHEN 'mensal' THEN 'monthly'
        WHEN 'trimestral' THEN 'quarterly'
        WHEN 'anual' THEN 'annual'
        WHEN 'administrador' THEN 'admin'
        ELSE lower(btrim(coalesce(p_plan, 'monthly')))
    END;

    IF v_plan NOT IN ('monthly', 'quarterly', 'annual', 'admin') THEN
        RAISE EXCEPTION 'Plano inválido: %', p_plan;
    END IF;

    SELECT id INTO v_user_id
    FROM auth.users
    WHERE lower(email) = lower(btrim(p_email))
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Este e-mail ainda não possui uma conta no Supabase Auth';
    END IF;

    v_expires_at := CASE v_plan
        WHEN 'monthly' THEN now() + interval '30 days'
        WHEN 'quarterly' THEN now() + interval '90 days'
        WHEN 'annual' THEN now() + interval '365 days'
        WHEN 'admin' THEN NULL
    END;

    INSERT INTO public.app_access (user_id, email, enabled, plan, expires_at, updated_at)
    VALUES (v_user_id, lower(btrim(p_email)), coalesce(p_enabled, true), v_plan, v_expires_at, now())
    ON CONFLICT (user_id) DO UPDATE SET
        email = excluded.email,
        enabled = excluded.enabled,
        plan = excluded.plan,
        expires_at = excluded.expires_at,
        updated_at = now();
END;
$$;

REVOKE ALL ON FUNCTION public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT) TO authenticated;
NOTIFY pgrst, 'reload schema';