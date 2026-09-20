"""Controle opcional de acesso para o AI Creative Engine.

Ativação: defina ACCESS_CONTROL_ENABLED = true nos Secrets do Streamlit
após criar a tabela app_access no Supabase.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Optional

import requests


def _is_enabled(st) -> bool:
    value = st.secrets.get("ACCESS_CONTROL_ENABLED", False)
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _email_from_access_token(access_token: str) -> str:
    """Extrai o e-mail do JWT já validado pelo Supabase Auth.

    A assinatura do token é validada pelo Supabase durante o login.
    Aqui usamos apenas o claim de e-mail para fazer uma busca alternativa
    quando o user_id da tabela app_access não coincidir.
    """
    try:
        parts = (access_token or "").split(".")
        if len(parts) != 3:
            return ""
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = base64.urlsafe_b64decode(payload.encode("ascii"))
        claims = json.loads(data.decode("utf-8"))
        return str(claims.get("email") or "").strip().lower()
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return ""


def _query_access(
    *,
    url: str,
    headers: dict[str, str],
    params: dict[str, str],
) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
    except requests.RequestException as exc:
        return None, f"Não foi possível verificar sua licença: {exc}"

    if response.status_code in (401, 403):
        return None, "O Supabase bloqueou a consulta de licença. Verifique as políticas RLS."
    if response.status_code == 404:
        return None, "A tabela de controle de acesso ainda não foi criada no Supabase."
    if response.status_code != 200:
        return None, f"Falha ao consultar a licença (HTTP {response.status_code})."

    return response.json() or [], None


def check_user_access(
    *,
    st,
    supabase_url: str,
    supabase_key: str,
    access_token: str,
    user_id: str,
) -> tuple[bool, str, Optional[dict[str, Any]]]:
    """Retorna (permitido, mensagem, registro).

    A consulta tenta primeiro o user_id e, como alternativa compatível com
    a autorização do Loop de Live, procura pelo e-mail presente no JWT.
    """
    if not _is_enabled(st):
        return True, "Controle de acesso desativado", None

    url = f"{supabase_url.rstrip('/')}/rest/v1/app_access"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {access_token}",
    }
    base_params = {
        "select": "user_id,email,enabled,plan,expires_at,notes",
        "limit": "1",
    }

    rows, error = _query_access(
        url=url,
        headers=headers,
        params={**base_params, "user_id": f"eq.{user_id}"},
    )
    if error:
        return False, error, None

    # Compatibilidade: o Lovable pode ter salvo a autorização pelo e-mail.
    if not rows:
        email = _email_from_access_token(access_token)
        if email:
            rows, error = _query_access(
                url=url,
                headers=headers,
                params={**base_params, "email": f"eq.{email}"},
            )
            if error:
                return False, error, None

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
