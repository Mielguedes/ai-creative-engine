"""Painel administrativo de acessos do AI Creative Engine.

Este módulo usa o token do usuário autenticado e a API REST do Supabase.
A criação de contas Auth deve ser feita por uma Edge Function protegida,
nunca com a service role key no Streamlit.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
import streamlit as st


def _config() -> tuple[str, str]:
    url = str(st.secrets.get("SUPABASE_URL", "")).rstrip("/")
    anon_key = str(st.secrets.get("SUPABASE_ANON_KEY", ""))
    if not url or not anon_key:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_ANON_KEY nos secrets.")
    return url, anon_key


def _headers(access_token: str) -> dict[str, str]:
    url, anon_key = _config()
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def listar_acessos(access_token: str) -> list[dict[str, Any]]:
    url, _ = _config()
    response = requests.get(
        f"{url}/rest/v1/app_access",
        headers=_headers(access_token),
        params={"select": "*", "order": "created_at.desc"},
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def atualizar_acesso(
    access_token: str,
    user_id: str,
    enabled: bool,
    plan: str,
    expires_at: str | None,
) -> None:
    url, _ = _config()
    payload = {
        "enabled": enabled,
        "plan": plan,
        "expires_at": expires_at or None,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    response = requests.patch(
        f"{url}/rest/v1/app_access",
        headers={**_headers(access_token), "Prefer": "return=minimal"},
        params={"user_id": f"eq.{user_id}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def render_admin_panel(access_token: str, is_admin: bool) -> None:
    if not is_admin:
        return

    with st.expander("🛡️ Administração de membros", expanded=False):
        st.caption("Gerencie acessos existentes. A criação de usuários Auth será integrada por backend protegido.")
        try:
            rows = listar_acessos(access_token)
        except Exception as exc:
            st.error(f"Não foi possível carregar os acessos: {exc}")
            return

        if not rows:
            st.info("Nenhum acesso cadastrado.")
            return

        for row in rows:
            user_id = str(row.get("user_id", ""))
            if not user_id:
                continue
            with st.container(border=True):
                st.write(f"**Usuário:** `{user_id}`")
                enabled = st.checkbox(
                    "Acesso ativo",
                    value=bool(row.get("enabled", False)),
                    key=f"access_enabled_{user_id}",
                )
                plan = st.selectbox(
                    "Plano",
                    ["admin", "mensal", "trimestral", "anual"],
                    index=["admin", "mensal", "trimestral", "anual"].index(str(row.get("plan", "mensal")))
                    if str(row.get("plan", "mensal")) in ["admin", "mensal", "trimestral", "anual"]
                    else 1,
                    key=f"access_plan_{user_id}",
                )
                expires_at = st.text_input(
                    "Validade (ISO ou vazio)",
                    value=str(row.get("expires_at") or ""),
                    key=f"access_expires_{user_id}",
                )
                if st.button("Salvar acesso", key=f"save_access_{user_id}"):
                    try:
                        atualizar_acesso(access_token, user_id, enabled, plan, expires_at.strip() or None)
                        st.success("Acesso atualizado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Falha ao atualizar: {exc}")
