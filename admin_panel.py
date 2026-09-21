"""Painel administrativo de acessos do AI Creative Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

PLANOS = ["admin", "mensal", "trimestral", "anual"]


def _config() -> tuple[str, str]:
    url = str(st.secrets.get("SUPABASE_URL", "")).rstrip("/")
    anon_key = str(st.secrets.get("SUPABASE_ANON_KEY", ""))
    if not url or not anon_key:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_ANON_KEY nos secrets.")
    return url, anon_key


def _headers(access_token: str) -> dict[str, str]:
    _, anon_key = _config()
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


def _normalizar_validade(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    try:
        datetime.fromisoformat(texto.replace("Z", "+00:00"))
        return texto
    except ValueError:
        return ""


def _validar_validade(valor: str) -> str | None:
    texto = valor.strip()
    if not texto:
        return None
    try:
        data = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Use uma data ISO válida, por exemplo: 2026-12-31T23:59:59Z") from exc
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def cadastrar_acesso(
    access_token: str,
    email: str,
    enabled: bool,
    plan: str,
    expires_at: str | None,
) -> None:
    url, _ = _config()
    payload = {
        "email": email.strip().lower(),
        "enabled": enabled,
        "plan": plan,
        "expires_at": _validar_validade(expires_at or ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    response = requests.post(
        f"{url}/rest/v1/app_access",
        headers={**_headers(access_token), "Prefer": "return=minimal"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def atualizar_acesso(
    access_token: str,
    user_id: str,
    email: str,
    enabled: bool,
    plan: str,
    expires_at: str | None,
) -> None:
    url, _ = _config()
    payload = {
        "enabled": enabled,
        "plan": plan,
        "expires_at": _validar_validade(expires_at or ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    filtro = {"user_id": f"eq.{user_id}"} if user_id else {"email": f"eq.{email.strip().lower()}"}
    response = requests.patch(
        f"{url}/rest/v1/app_access",
        headers={**_headers(access_token), "Prefer": "return=minimal"},
        params=filtro,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()


def render_admin_panel(access_token: str, is_admin: bool) -> None:
    if not is_admin:
        return

    with st.expander("🛡️ Administração de membros", expanded=False):
        st.caption("Informe somente o e-mail para liberar o acesso. A conta da pessoa precisa existir no Supabase Auth para ela conseguir fazer login.")

        st.markdown("### ➕ Cadastrar novo membro")
        with st.form("new_access_form", clear_on_submit=True):
            new_email = st.text_input("E-mail da pessoa", placeholder="pessoa@email.com")
            new_plan = st.selectbox("Plano", PLANOS, index=1)
            new_expires = st.text_input("Validade (opcional)", placeholder="2026-12-31T23:59:59Z")
            new_enabled = st.checkbox("Acesso ativo", value=True)
            register = st.form_submit_button("Cadastrar acesso", type="primary", use_container_width=True)

        if register:
            normalized_email = new_email.strip().lower()
            if not normalized_email or "@" not in normalized_email:
                st.error("Informe um e-mail válido.")
            else:
                try:
                    cadastrar_acesso(
                        access_token,
                        normalized_email,
                        new_enabled,
                        new_plan,
                        _validar_validade(new_expires),
                    )
                    st.success("Acesso cadastrado. A pessoa já pode entrar se sua conta Auth existir.")
                    st.rerun()
                except requests.HTTPError as exc:
                    detail = exc.response.text if exc.response is not None else str(exc)
                    st.error(f"Não foi possível cadastrar o e-mail. Verifique se a coluna email existe, se o user_id aceita vazio e se a policy INSERT está ativa. Detalhes: {detail}")
                except Exception as exc:
                    st.error(f"Não foi possível cadastrar: {exc}")

        st.divider()
        st.markdown("### 👥 Acessos existentes")
        try:
            rows = listar_acessos(access_token)
        except Exception as exc:
            st.error(f"Não foi possível carregar os acessos: {exc}")
            return

        if not rows:
            st.info("Nenhum acesso cadastrado.")
            return

        for row in rows:
            user_id = str(row.get("user_id") or "").strip()
            email = str(row.get("email") or row.get("user_email") or "").strip()
            identifier = user_id or email
            if not identifier:
                continue

            validade_atual = _normalizar_validade(row.get("expires_at"))
            with st.container(border=True):
                st.write(f"**E-mail:** `{email or 'não informado'}`")
                if user_id:
                    st.caption(f"Usuário: `{user_id}`")
                enabled = st.checkbox(
                    "Acesso ativo",
                    value=bool(row.get("enabled", False)),
                    key=f"access_enabled_{identifier}",
                )
                plan_atual = str(row.get("plan", "mensal"))
                plan = st.selectbox(
                    "Plano",
                    PLANOS,
                    index=PLANOS.index(plan_atual) if plan_atual in PLANOS else 1,
                    key=f"access_plan_{identifier}",
                )
                expires_at = st.text_input(
                    "Validade (ISO ou vazio)",
                    value=validade_atual,
                    placeholder="2026-12-31T23:59:59Z",
                    key=f"access_expires_{identifier}",
                )

                if st.button("Salvar acesso", key=f"save_access_{identifier}"):
                    try:
                        atualizar_acesso(access_token, user_id, email, enabled, plan, expires_at)
                        st.success("Acesso atualizado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Falha ao atualizar: {exc}")
