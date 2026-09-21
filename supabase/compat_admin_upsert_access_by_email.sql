-- Compatibilidade com a versão antiga do painel.
-- O erro PGREST202 indica que o aplicativo publicado ainda chama
-- admin_upsert_access_by_email.

CREATE OR REPLACE FUNCTION public.admin_upsert_access_by_email(
    p_email TEXT,
    p_enabled BOOLEAN DEFAULT TRUE,
    p_plan TEXT DEFAULT 'mensal'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN public.cadastrar_acesso_por_email(
        p_email,
        p_plan,
        p_enabled
    );
END;
$$;

REVOKE ALL ON FUNCTION public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_upsert_access_by_email(TEXT, BOOLEAN, TEXT) TO authenticated;

NOTIFY pgrst, 'reload schema';
