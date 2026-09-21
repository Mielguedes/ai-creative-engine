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

# O restante do arquivo deve ser recuperado do histórico antes de executar.
