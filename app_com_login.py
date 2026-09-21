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
        return None, "Perfil não encontrado na tabela profiles para este usuário."
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

def buscar_todos_perfis_admin():
    return None, "O painel administrativo será habilitado após a definição de permissões na estrutura atual do Loop de Live."

def atualizar_perfil_admin(profile_id, ativo, plano):
    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json", "Prefer": "return=minimal"}
    params = {"id": f"eq.{profile_id}"}
    dados = {"ativo": bool(ativo), "plano": plano}
    resposta = requests.patch(url, headers=headers, params=params, json=dados, timeout=20)
    return resposta.status_code in (200, 204), resposta.text

def painel_admin():
    if not IS_ADMIN:
        return
    st.sidebar.divider()
    with st.sidebar.expander("👑 Painel Administrativo", expanded=False):
        st.markdown("**Controle de usuários**")
        perfis, erro = buscar_todos_perfis_admin()
        if erro:
            st.warning("⚠️ O painel administrativo precisa de uma policy para o admin consultar todos os perfis.")
            st.caption("Configure a policy no Supabase e recarregue o app.")
            return
        if not perfis:
            st.info("Nenhum usuário encontrado.")
            return
        for perfil in perfis:
            email = perfil.get("email") or ""
            nome = perfil.get("nome") or email
            plano_atual = (perfil.get("plano") or "user").lower()
            ativo_atual = bool(perfil.get("ativo", True))
            profile_id = perfil.get("id")
            st.markdown(f"**👤 {nome}**")
            st.caption(email)
            novo_plano = st.selectbox("Plano", ["user", "admin"], index=0 if plano_atual != "admin" else 1, key=f"admin_plano_{profile_id}")
            novo_ativo = st.checkbox("Usuário ativo", value=ativo_atual, key=f"admin_ativo_{profile_id}")
            if st.button("💾 Salvar", key=f"admin_salvar_{profile_id}", use_container_width=True):
                ok, detalhe = atualizar_perfil_admin(profile_id, novo_ativo, novo_plano)
                if ok:
                    st.success("Salvo!")
                    if profile_id == st.session_state.get("user_id"):
                        st.session_state["user_plano"] = novo_plano
                        st.session_state["user_ativo"] = novo_ativo
                    st.rerun()
                else:
                    st.error(f"Erro ao salvar: {detalhe}")
            st.divider()

st.sidebar.title("📁 Projetos")
st.sidebar.caption(f"👤 {USER_NAME}")
st.sidebar.caption(USER_EMAIL)
if IS_ADMIN:
    st.sidebar.success("👑 Administrador")
else:
    st.sidebar.info("👤 Usuário")
if st.sidebar.button("🚪 Sair", use_container_width=True, key="btn_logout"):
    fazer_logout()
painel_admin()

novo_proj_nome = st.sidebar.text_input("Novo Projeto:", key="novo_projeto_nome")
if st.sidebar.button("➕ Criar Projeto", use_container_width=True, key="criar_projeto"):
    if novo_proj_nome.strip():
        nome_limpo = re.sub(r'[^\w\s-]', '', novo_proj_nome.strip()).replace(" ", "_")
        if not nome_limpo:
            st.sidebar.error("Nome de projeto inválido.")
        else:
            proj_path = os.path.join(BASE_DIR, nome_limpo)
            for pasta in ["ganchos", "corpos", "ctas", "output"]:
                os.makedirs(os.path.join(proj_path, pasta), exist_ok=True)
            st.sidebar.success(f"Projeto '{nome_limpo}' criado!")
            st.rerun()

st.sidebar.divider()
projetos_disponiveis = listar_projetos()
if not projetos_disponiveis:
    st.warning("⚠️ Nenhum projeto encontrado. Crie um projeto no menu lateral para começar!")
    st.stop()
projeto_atual = st.sidebar.selectbox("Selecione o Projeto Ativo:", projetos_disponiveis, key="projeto_ativo")
PROJ_PATH = os.path.join(BASE_DIR, projeto_atual)
PATH_GANCHOS = os.path.join(PROJ_PATH, "ganchos")
PATH_CORPOS = os.path.join(PROJ_PATH, "corpos")
PATH_CTAS = os.path.join(PROJ_PATH, "ctas")
PATH_OUTPUT = os.path.join(PROJ_PATH, "output")
for pasta in [PATH_GANCHOS, PATH_CORPOS, PATH_CTAS, PATH_OUTPUT]:
    os.makedirs(pasta, exist_ok=True)

def restaurar_projeto_do_storage():
    cache_key = f"storage_restored::{USER_ID}::{projeto_atual}"
    if st.session_state.get(cache_key):
        return
    manifest_object = f"{project_prefix(USER_ID, projeto_atual)}/.storage-manifest.json"
    manifest_url = f"{SUPABASE_URL}/storage/v1/object/{st.secrets.get('SUPABASE_STORAGE_BUCKET', 'ai-creative-engine')}/{manifest_object}"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {st.session_state.get('access_token') or SUPABASE_KEY}"}
    try:
        resposta = requests.get(manifest_url, headers=headers, timeout=30)
        if resposta.status_code in (400, 404):
            st.session_state[cache_key] = True
            return
        resposta.raise_for_status()
        manifest = resposta.json()
        arquivos = manifest.get("files", [])
        restaurados = 0
        for item in arquivos:
            relativo = str(item.get("path") or "").strip()
            if not relativo or not relativo.lower().endswith((".mp4", ".mov", ".m4v")):
                continue
            destino = os.path.join(PROJ_PATH, relativo)
            if os.path.isfile(destino) and os.path.getsize(destino) > 0:
                continue
            restore_file_from_storage(USER_ID, projeto_atual, relativo, PROJ_PATH, access_token=st.session_state.get("access_token"))
            restaurados += 1
        if restaurados:
            st.sidebar.success(f"☁️ {restaurados} arquivo(s) restaurado(s) do Storage.")
        st.session_state[cache_key] = True
    except Exception as exc:
        st.sidebar.warning(f"⚠️ Não foi possível restaurar o projeto do Storage: {exc}")

restaurar_projeto_do_storage()
