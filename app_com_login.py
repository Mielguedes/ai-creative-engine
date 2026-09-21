import itertools
import json
import os
import random
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

import requests
import streamlit as st
from faster_whisper import WhisperModel

from admin_panel import render_admin_panel

st.set_page_config(page_title="AI Creative Engine", layout="wide")

LEGACY_SOURCE_URL = "https://raw.githubusercontent.com/Mielguedes/ai-creative-engine/bc0c3587292d82ef156dd74af9cb51c0c07e3031/app_com_login.py"
LEGACY_MARKERS = ("# --- ESTRUTURA DE PASTAS E PROJETOS ---", "# ESTRUTURA DE PASTAS E PROJETOS")


def config():
    return (st.secrets.get("SUPABASE_URL", "").rstrip("/"), st.secrets.get("SUPABASE_ANON_KEY", ""))


def auth_headers(token=None):
    url, anon_key = config()
    return url, {"apikey": anon_key, "Authorization": f"Bearer {token}" if token else f"Bearer {anon_key}", "Content-Type": "application/json"}


def login_supabase(email, password):
    url, headers = auth_headers()
    if not url or not headers["apikey"]:
        return None, "Configure SUPABASE_URL e SUPABASE_ANON_KEY nos Secrets."
    try:
        response = requests.post(f"{url}/auth/v1/token?grant_type=password", headers=headers, json={"email": email, "password": password}, timeout=20)
        if response.ok:
            return response.json(), None
        return None, "E-mail ou senha inválidos."
    except requests.RequestException:
        return None, "Não foi possível conectar ao serviço de autenticação."


def _query_access(token, params):
    url, headers = auth_headers(token)
    try:
        response = requests.get(f"{url}/rest/v1/app_access", headers={**headers, "Accept": "application/json"}, params=params, timeout=20)
        if response.ok:
            records = response.json()
            return records[0] if records else None
    except requests.RequestException:
        pass
    return None


def access_record(token, user_id, email):
    record = _query_access(token, {"select": "user_id,email,enabled,plan,expires_at", "user_id": f"eq.{user_id}", "limit": "1"})
    return record or _query_access(token, {"select": "user_id,email,enabled,plan,expires_at", "email": f"eq.{email}", "limit": "1"})


def access_is_valid(record):
    if not record or not record.get("enabled"):
        return False
    expires_at = record.get("expires_at")
    if not expires_at:
        return True
    try:
        expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return expiration >= datetime.now(timezone.utc)
    except (TypeError, ValueError):
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
        user_id = user.get("id", "")
        user_email = user.get("email", email.strip())
        record = access_record(session.get("access_token", ""), user_id, user_email)
        if not access_is_valid(record):
            st.error("Sua conta não possui acesso ativo ou está vencida.")
            return False
        st.session_state.update(autenticado=True, auth_ok=True, access_token=session.get("access_token", ""), refresh_token=session.get("refresh_token", ""), user_id=user_id, user_email=user_email, user_plano=record.get("plan", "monthly"), user_ativo=record.get("enabled", False))
        st.rerun()
    return False


if not st.session_state.get("auth_ok", False):
    show_login()
    st.stop()

access_token = st.session_state.get("access_token", "")
user_id = st.session_state.get("user_id", "")
user_email = st.session_state.get("user_email", "")
record = access_record(access_token, user_id, user_email)
if not access_is_valid(record):
    st.session_state.clear()
    st.error("Seu acesso não está mais ativo. Faça login novamente após a regularização.")
    st.stop()

is_admin = record.get("plan") == "admin"
SUPABASE_URL, SUPABASE_KEY = config()
USER_ID = user_id
USER_EMAIL = user_email
USER_NAME = user_email
USER_PLANO = record.get("plan", "monthly").lower()
IS_ADMIN = is_admin

st.sidebar.success(f"Conectado: {user_email}")
st.sidebar.caption(f"Plano: {record.get('plan', 'monthly')}")
if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.clear()
    st.rerun()

render_admin_panel(access_token, is_admin)


def carregar_multiplicador():
    fontes = [
        ("arquivo local restaurado", os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_restauracao_storage_final.py")),
        ("arquivo legado remoto", LEGACY_SOURCE_URL),
    ]
    ultimo_erro = None
    for origem, fonte in fontes:
        try:
            if origem.startswith("arquivo local"):
                with open(fonte, "r", encoding="utf-8") as arquivo:
                    source = arquivo.read()
            else:
                response = requests.get(fonte, timeout=30)
                response.raise_for_status()
                source = response.text
            marker_position = -1
            for marker in LEGACY_MARKERS:
                marker_position = source.find(marker)
                if marker_position >= 0:
                    break
            if marker_position < 0:
                raise RuntimeError("marcador do núcleo do multiplicador não encontrado")
            return source[marker_position:]
        except Exception as error:
            ultimo_erro = error
    raise RuntimeError(str(ultimo_erro or "fonte indisponível"))


try:
    legacy_functional_source = carregar_multiplicador()
    exec(compile(legacy_functional_source, "legacy_multiplicador.py", "exec"), globals(), globals())
except Exception as error:
    st.error(f"Não foi possível carregar o módulo do multiplicador: {error}")
    st.info("O cadastro e o login foram preservados. Detalhe técnico: " + str(error))
    st.stop()
