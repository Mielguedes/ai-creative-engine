"""Controle opcional de acesso para o AI Creative Engine.

Ativação: defina ACCESS_CONTROL_ENABLED = true nos Secrets do Streamlit
após criar a tabela app_access no Supabase.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import requests


def _is_enabled(st) -> bool:
    value = st.secrets.get("ACCESS_CONTROL_ENABLED", False)
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def check_user_access(*, st, supabase_url: str, supabase_key: str, access_token: str, user_id: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
    """Retorna (permitido, mensagem, registro)."""
    if not _is_enabled(st):
        return True, "Controle de acesso desativado", None

    url = f"{supabase_url.rstrip('/')}/rest/v1/app_access"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {access_token}",
    }
    params = {
        "select": "user_id,email,enabled,plan,expires_at,notes",
        "user_id": f"eq.{user_id}",
        "limit": "1",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
    except requests.RequestException as exc:
        return False, f"Não foi possível verificar sua licença: {exc}", None

    if response.status_code in (401, 403):
        return False, "O Supabase bloqueou a consulta de licença. Verifique as políticas RLS.", None
    if response.status_code == 404:
        return False, "A tabela de controle de acesso ainda não foi criada no Supabase.", None
    if response.status_code != 200:
        return False, f"Falha ao consultar a licença (HTTP {response.status_code}).", None

    rows = response.json() or []
    if not rows:
        return False, "Seu acesso ainda não foi liberado. Entre em contato com o suporte.", None

    record = rows[0]
    if record.get("enabled") is not True:
        return False, "Seu acesso está desativado. Entre em contato com o suporte.", record

    expires_at = record.get("expires_at")
    if expires_at:
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed <= datetime.now(timezone.utc):
                return False, "Sua licença expirou. Entre em contato com o suporte.", record
        except ValueError:
            return False, "A validade da sua licença está configurada incorretamente.", record

    return True, "Acesso liberado", record
