-- CADASTRO DE ACESSO POR E-MAIL
-- Mantém user_id como chave primária obrigatória e resolve o ID
-- automaticamente a partir de auth.users.

ALTER TABLE public.app_access
ADD COLUMN IF NOT EXISTS email TEXT;

CREATE OR REPLACE FUNCTION public.admin_upsert_access_by_email(
    p_email TEXT,
    p_enabled BOOLEAN DEFAULT TRUE,
    p_plan TEXT DEFAULT 'mensal'
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
DECLARE
    target_user_id UUID;
    calculated_expires_at TIMESTAMPTZ;
BEGIN
    IF NOT public.is_app_access_admin() THEN
        RAISE EXCEPTION 'Apenas administradores podem cadastrar acessos';
    END IF;

    IF p_email IS NULL OR btrim(p_email) = '' OR position('@' IN p_email) = 0 THEN
        RAISE EXCEPTION 'Informe um e-mail válido';
    END IF;

    IF p_plan NOT IN ('admin', 'mensal', 'trimestral', 'anual') THEN
        RAISE EXCEPTION 'Plano inválido';
    END IF;

    SELECT id
      INTO target_user_id
      FROM auth.users
     WHERE lower(email) = lower(btrim(p_email))
     LIMIT 1;

    IF target_user_id IS NULL THEN
        RAISE EXCEPTION 'Este e-mail ainda não possui uma conta no Supabase Auth';
    END IF;

    calculated_expires_at := CASE p_plan
        WHEN 'admin' THEN NULL
        WHEN 'mensal' THEN NOW() + INTERVAL '30 days'
        WHEN 'trimestral' THEN NOW() + INTERVAL '90 days'
        WHEN 'anual' THEN NOW() + INTERVAL '365 days'
    END;

    INSERT INTO public.app_access (
        user_id,
        email,
        enabled,
        plan,
        expires_at,
        updated_at
    )
    VALUES (
        target_user_id,
        lower(btrim(p_email)),
        COALESCE(p_enabled, TRUE),
        p_plan,
        calculated_expires_at,
        NOW()
    )
    ON CONFLICT (user_id)
    DO UPDATE SET
        email = EXCLUDED.email,
        enabled = EXCLUDED.enabled,
        plan = EXCLUDED.plan,
        expires_at = EXCLUDED.expires_at,
        updated_at = NOW();
END;
$$;

REVOKE ALL ON FUNCTION public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT) TO authenticated;
