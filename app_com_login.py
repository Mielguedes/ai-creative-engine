import streamlit as st
import itertools
import os
import json
import subprocess
import shutil
import zipfile
import re
import random
import requests
from faster_whisper import WhisperModel
from storage_ui import save_uploaded_files
from storage_sync import project_prefix, restore_file_from_storage, sync_project_to_storage
from access_control import check_user_access

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(page_title="AI Creative Engine Local", layout="wide")

# ============================================================
# SUPABASE / LOGIN
# ============================================================
def normalizar_supabase_url(url):
    url = (url or "").strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-7]
    return url.rstrip("/")

try:
    SUPABASE_URL = normalizar_supabase_url(st.secrets["SUPABASE_URL"])
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("❌ Configure SUPABASE_URL e SUPABASE_KEY em Settings → Secrets.")
    st.stop()

def supabase_auth(email, senha):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
    resposta = requests.post(url, headers=headers, json={"email": email.strip(), "password": senha}, timeout=20)
    try:
        dados = resposta.json()
    except Exception:
        dados = {}
    if resposta.status_code != 200:
        mensagem = dados.get("error_description") or dados.get("msg") or "E-mail ou senha incorretos."
        return None, mensagem
    return dados, None

def buscar_perfil(access_token, user_id):
    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {access_token}"}
    params = {"select": "user_id,display_name,avatar_url,created_at,updated_at", "user_id": f"eq.{user_id}", "limit": "1"}
    resposta = requests.get(url, headers=headers, params=params, timeout=20)
    if resposta.status_code != 200:
        return None, resposta.text
    registros = resposta.json()
    if not registros:
        return {"display_name": ""}, None
    return registros[0], None

def fazer_logout():
    for chave in ["auth_ok", "access_token", "refresh_token", "user_id", "user_email", "user_name", "user_plano", "user_ativo"]:
        st.session_state.pop(chave, None)
    st.rerun()

def tela_login():
    st.markdown("""<style>.login-title{font-size:42px;font-weight:800;color:#183153;margin-bottom:4px}.login-subtitle{color:#7b8190;font-size:15px;margin-bottom:24px}</style>""", unsafe_allow_html=True)
    st.markdown('<div class="login-title">🔐 AI Creative Engine</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">Entre para acessar o gerador de vídeos.</div>', unsafe_allow_html=True)
    email = st.text_input("📧 E-mail", key="login_email")
    senha = st.text_input("🔑 Senha", type="password", key="login_password")
    if st.button("🚀 ENTRAR", type="primary", use_container_width=True, key="btn_login"):
        if not email.strip() or not senha:
            st.error("❌ Informe e-mail e senha.")
            return
        with st.spinner("Entrando..."):
            dados, erro = supabase_auth(email, senha)
        if erro:
            st.error(f"❌ {erro}")
            return
        access_token = dados.get("access_token")
        refresh_token = dados.get("refresh_token")
        user = dados.get("user") or {}
        user_id = user.get("id")
        if not access_token or not user_id:
            st.error("❌ O Supabase não retornou os dados de autenticação.")
            return
        perfil, erro_perfil = buscar_perfil(access_token, user_id)
        if erro_perfil:
            st.error(f"❌ Não foi possível carregar seu perfil: {erro_perfil}")
            return
        st.session_state["auth_ok"] = True
        st.session_state["access_token"] = access_token
        st.session_state["refresh_token"] = refresh_token
        st.session_state["user_id"] = user_id
        st.session_state["user_email"] = email.strip()
        st.session_state["user_name"] = perfil.get("display_name") or email.strip()
        st.session_state["user_plano"] = "user"
        st.session_state["user_ativo"] = True
        st.rerun()

if not st.session_state.get("auth_ok", False):
    tela_login()
    st.stop()

USER_ID = st.session_state["user_id"]
USER_EMAIL = st.session_state["user_email"]
USER_NAME = st.session_state.get("user_name") or USER_EMAIL
USER_PLANO = st.session_state.get("user_plano", "user").lower()
IS_ADMIN = USER_PLANO == "admin"

_access_allowed, _access_message, _access_record = check_user_access(st=st, supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY, access_token=st.session_state.get("access_token", ""), user_id=USER_ID)
if not _access_allowed:
    st.error(f"🔒 {_access_message}")
    st.info("Se você acredita que isso é um engano, entre em contato com o suporte.")
    st.stop()
if _access_record:
    st.session_state["user_plano"] = str(_access_record.get("plan") or "user")

BASE_DIR = os.path.abspath(os.path.join("projetos", USER_ID))
os.makedirs(BASE_DIR, exist_ok=True)

def listar_projetos():
    return sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])

# O restante do aplicativo permanece no arquivo original.
