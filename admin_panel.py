"""Painel administrativo de acessos do AI Creative Engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

PLANOS = ["monthly", "quarterly", "annual", "admin"]
PLANOS_LABELS = {
    "monthly": "Mensal",
    "quarterly": "Trimestral",
    "annual": "Anual",
    "admin": "Administrador",
}


def normalizar_plano(valor: Any) -> str:
    plano = str(valor or "").strip().lower()
    equivalencias = {
        "mensal": "monthly",
        "trimestral": "quarterly",
        "anual": "annual",
        "administrador": "admin",
    }
    return equivalencias.get(plano, plano if plano in PLANOS else "monthly")


def _config() -> tuple[str, str]:
    url = str(st.secrets.get("SUPABASE_URL", "")).rstrip("/")
    anon_key = str(st.secrets.get("SUPABASE_ANON_KEY", ""))
    if not url or not anon_key:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_ANON_KEY nos Secrets.")
    return url, anon_key


def _headers(access_token: str) -> dict[str, str]:
    _, anon_key = _config()
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def cadastrar_acesso(access_token: str, email: str, plan: str) -> None:
    """Cadastra um usuário que já existe no Supabase Auth pelo e-mail."""
    url, _ = _config()
    response = requests.post(
        f"{url}/rest/v1/rpc/admin_upsert_access_by_email",
        headers={**_headers(access_token), "Prefer": "return=minimal"},
        json={
            "p_email": email.strip().lower(),
            "p_enabled": True,
            "p_plan": normalizar_plano(plan),
        },
        timeout=20,
    )
    response.raise_for_status()


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
        raise ValueError("Use uma data ISO válida, exemplo: 2026-12-31T23:59:59Z") from exc
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def atualizar_acesso(access_token: str, user_id: str, email: str, enabled: bool, plan: str, expires_at: str | None) -> None:
    url, _ = _config()
    payload = {
        "enabled": enabled,
        "plan": normalizar_plano(plan),
        "expires_at": _validar_validade(expires_at or ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    filtro = {"email": f"eq.{email.strip().lower()}"} if email else {"user_id": f"eq.{user_id}"}
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
        st.caption("Digite o e-mail de uma conta já criada no Supabase Auth. Escolha o plano e clique em cadastrar.")

        with st.form("new_access_form", clear_on_submit=True):
            new_email = st.text_input("E-mail do membro", placeholder="pessoa@email.com")
            new_plan = st.selectbox("Plano", PLANOS, format_func=lambda value: PLANOS_LABELS[value])
            register = st.form_submit_button("Cadastrar membro", type="primary", use_container_width=True)

        if register:
            normalized_email = new_email.strip().lower()
            if not normalized_email or "@" not in normalized_email or "." not in normalized_email.split("@")[-1]:
                st.error("Digite um e-mail válido.")
            else:
                try:
                    cadastrar_acesso(access_token, normalized_email, new_plan)
                    st.success("Membro cadastrado com sucesso!")
                    st.rerun()
                except requests.HTTPError as exc:
                    detail = exc.response.text if exc.response is not None else str(exc)
                    st.error(f"Não foi possível cadastrar. Verifique se o e-mail já possui conta no Auth.\n\n{detail}")
                except Exception as exc:
                    st.error(f"Não foi possível cadastrar: {exc}")

        with st.expander("👥 Gerenciar acessos existentes", expanded=False):
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

                with st.expander(email or "Membro sem e-mail", expanded=False):
                    enabled = st.checkbox("Acesso ativo", value=bool(row.get("enabled", False)), key=f"access_enabled_{identifier}")
                    plan = st.selectbox("Plano", PLANOS, index=PLANOS.index(normalizar_plano(row.get("plan"))), format_func=lambda value: PLANOS_LABELS[value], key=f"access_plan_{identifier}")
                    expires_at = st.text_input("Validade (opcional)", value=_normalizar_validade(row.get("expires_at")), placeholder="2026-12-31T23:59:59Z", key=f"access_expires_{identifier}")
                    if st.button("Salvar", key=f"save_access_{identifier}"):
                        try:
                            atualizar_acesso(access_token, user_id, email, enabled, plan, expires_at)
                            st.success("Acesso atualizado.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Falha ao atualizar: {exc}")
