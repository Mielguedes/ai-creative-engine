import os
from datetime import datetime, timezone

import requests
import streamlit as st

from admin_panel import render_admin_panel

st.set_page_config(page_title="AI Creative Engine", layout="wide")


def config():
    return (
        st.secrets.get("SUPABASE_URL", "").rstrip("/"),
        st.secrets.get("SUPABASE_ANON_KEY", ""),
    )


def auth_headers(token=None):
    url, anon_key = config()
    headers = {"apikey": anon_key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return url, headers


def login_supabase(email, password):
    url, headers = auth_headers()
    if not url or not headers["apikey"]:
        return None, "Configure SUPABASE_URL e SUPABASE_ANON_KEY nos Secrets."
    try:
        response = requests.post(
            f"{url}/auth/v1/token?grant_type=password",
            headers=headers,
            json={"email": email, "password": password},
            timeout=20,
        )
        if response.ok:
            return response.json(), None
        return None, "E-mail ou senha inválidos."
    except requests.RequestException:
        return None, "Não foi possível conectar ao serviço de autenticação."


def access_record(token, user_id):
    url, headers = auth_headers(token)
    try:
        response = requests.get(
            f"{url}/rest/v1/app_access",
            headers={**headers, "Accept": "application/json"},
            params={"select": "user_id,email,enabled,plan,expires_at", "user_id": f"eq.{user_id}"},
            timeout=20,
        )
        if not response.ok:
            return None
        records = response.json()
        return records[0] if records else None
    except requests.RequestException:
        return None


def access_is_valid(record):
    if not record or not record.get("enabled"):
        return False
    expires_at = record.get("expires_at")
    if not expires_at:
        return True
    try:
        expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return expiration >= datetime.now(timezone.utc)
    except ValueError:
        return False


def show_login():
    st.title("🔐 AI Creative Engine")
    st.caption("Entre com sua conta para acessar o multiplicador de vídeos.")
    with st.form("supabase_login"):
        email = st.text_input("📧 E-mail")
        password = st.text_input("🔑 Senha", type="password")
        submitted = st.form_submit_button("🚀 ENTRAR", type="primary", use_container_width=True)
    if submitted:
        session, error = login_supabase(email.strip(), password)
        if error:
            st.error(error)
            return False
        user = session.get("user", {})
        record = access_record(session.get("access_token", ""), user.get("id", ""))
        if not access_is_valid(record):
            st.error("Sua conta não possui acesso ativo ou está vencida.")
            return False
        st.session_state.update(
            autenticado=True,
            auth_ok=True,
            access_token=session.get("access_token", ""),
            refresh_token=session.get("refresh_token", ""),
            user_id=user.get("id", ""),
            user_email=user.get("email", email.strip()),
            user_plano=record.get("plan", "mensal"),
            user_ativo=record.get("enabled", False),
        )
        st.rerun()
    return False


if not st.session_state.get("auth_ok", False):
    show_login()
    st.stop()

access_token = st.session_state.get("access_token", "")
user_id = st.session_state.get("user_id", "")
record = access_record(access_token, user_id)
if not access_is_valid(record):
    st.session_state.clear()
    st.error("Seu acesso não está mais ativo. Faça login novamente após a regularização.")
    st.stop()

is_admin = record.get("plan") == "admin"
st.sidebar.success(f"Conectado: {st.session_state.get('user_email', '')}")
st.sidebar.caption(f"Plano: {record.get('plan', 'mensal')}")
if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.clear()
    st.rerun()

render_admin_panel(access_token, is_admin)

# Mantém o multiplicador completo existente, sem duplicar seu código.
# O wrapper autentica antes de executar o arquivo legado.
legacy_path = os.path.join(os.path.dirname(__file__), "app_com_login.py")
with open(legacy_path, "r", encoding="utf-8") as legacy_file:
    legacy_code = legacy_file.read()
exec(compile(legacy_code, legacy_path, "exec"), globals(), globals())
