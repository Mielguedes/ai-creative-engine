import itertools
import json
import os
import random
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import requests
import streamlit as st

try:
    from imageio_ffmpeg import get_ffmpeg_exe
except Exception:
    get_ffmpeg_exe = None


st.set_page_config(page_title="AI Creative Engine", page_icon="🎬", layout="wide")

APP_TITLE = "🎬 AI Creative Engine"
DATA_ROOT = Path("data")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv")


def supabase_settings():
    try:
        url = str(st.secrets["SUPABASE_URL"]).strip().rstrip("/")
        key = str(st.secrets["SUPABASE_KEY"]).strip()
        if not url or not key:
            return None, None
        return url, key
    except Exception:
        return None, None


SUPABASE_URL, SUPABASE_KEY = supabase_settings()


def clear_auth():
    for key in (
        "auth_ok",
        "access_token",
        "refresh_token",
        "user_id",
        "user_email",
        "user_name",
        "user_plan",
        "access_record",
    ):
        st.session_state.pop(key, None)


def supabase_login(email, password):
    endpoint = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"email": email.strip(), "password": password},
            timeout=20,
        )
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if response.status_code != 200:
            message = (
                payload.get("error_description")
                or payload.get("msg")
                or payload.get("message")
                or "E-mail ou senha incorretos."
            )
            return None, str(message)
        return payload, None
    except requests.RequestException as exc:
        return None, f"Falha de conexão com o Supabase: {exc}"


def load_access_record(access_token, user_id):
    endpoint = f"{SUPABASE_URL}/rest/v1/app_access"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {access_token}",
    }
    params = {
        "select": "user_id,email,enabled,plan,expires_at",
        "user_id": f"eq.{user_id}",
        "limit": "1",
    }
    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=20)
        if response.status_code != 200:
            return None, f"Não foi possível consultar o acesso: {response.text}"
        records = response.json()
        return (records[0] if records else None), None
    except requests.RequestException as exc:
        return None, f"Falha ao consultar o acesso: {exc}"


def access_is_valid(record):
    if not record:
        return False, "Seu e-mail ainda não possui acesso liberado."
    if not bool(record.get("enabled")):
        return False, "Seu acesso está desativado."
    plan = str(record.get("plan") or "user").lower()
    if plan == "admin":
        return True, ""
    expires_at = record.get("expires_at")
    if not expires_at:
        return False, "Seu plano não possui validade configurada."
    from datetime import datetime, timezone
    try:
        normalized = str(expires_at).replace("Z", "+00:00")
        expiration = datetime.fromisoformat(normalized)
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration <= datetime.now(timezone.utc):
            return False, "Seu plano está vencido."
    except ValueError:
        return False, "A validade do seu plano está inválida."
    return True, ""


def login_screen():
    st.title(APP_TITLE)
    st.caption("Entre para acessar o multiplicador de vídeos.")
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Configure SUPABASE_URL e SUPABASE_KEY em Settings → Secrets do Streamlit.")
        st.stop()

    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("📧 E-mail")
        password = st.text_input("🔑 Senha", type="password")
        submitted = st.form_submit_button("🚀 ENTRAR", use_container_width=True, type="primary")

    if submitted:
        if not email.strip() or not password:
            st.error("Informe o e-mail e a senha.")
            return
        with st.spinner("Validando acesso..."):
            payload, error = supabase_login(email, password)
        if error:
            st.error(error)
            return

        user = payload.get("user") or {}
        user_id = user.get("id")
        access_token = payload.get("access_token")
        if not user_id or not access_token:
            st.error("O Supabase não retornou os dados necessários para o login.")
            return

        record, access_error = load_access_record(access_token, user_id)
        if access_error:
            st.error(access_error)
            return
        allowed, message = access_is_valid(record)
        if not allowed:
            st.error(message)
            return

        st.session_state["auth_ok"] = True
        st.session_state["access_token"] = access_token
        st.session_state["refresh_token"] = payload.get("refresh_token")
        st.session_state["user_id"] = user_id
        st.session_state["user_email"] = str(user.get("email") or email).strip()
        st.session_state["user_name"] = str(user.get("user_metadata", {}).get("name") or email).strip()
        st.session_state["user_plan"] = str(record.get("plan") or "user").lower()
        st.session_state["access_record"] = record
        st.rerun()


def user_root():
    safe_user = str(st.session_state["user_id"]).replace("/", "_")
    root = DATA_ROOT / safe_user
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_path(project_name):
    path = user_root() / project_name
    for category in ("ganchos", "corpos", "ctas", "output"):
        (path / category).mkdir(parents=True, exist_ok=True)
    return path


def safe_name(value):
    result = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value.strip())
    return result.strip("._-") or "projeto"


def list_projects():
    root = user_root()
    projects = sorted(path.name for path in root.iterdir() if path.is_dir())
    if not projects:
        project_path("Meu_Projeto")
        projects = ["Meu_Projeto"]
    return projects


def list_videos(folder):
    if not folder.exists():
        return []
    return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS)


def save_uploads(uploaded_files, destination):
    destination.mkdir(parents=True, exist_ok=True)
    saved = 0
    for uploaded in uploaded_files or []:
        filename = safe_name(Path(uploaded.name).stem) + Path(uploaded.name).suffix.lower()
        target = destination / filename
        target.write_bytes(uploaded.getbuffer())
        saved += 1
    return saved


def ffmpeg_path():
    if get_ffmpeg_exe is None:
        raise RuntimeError("O pacote imageio-ffmpeg não está disponível.")
    return get_ffmpeg_exe()


def normalize_video(source, target):
    command = [
        ffmpeg_path(),
        "-y",
        "-i",
        str(source),
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Erro desconhecido")[-1200:]
        raise RuntimeError(detail)


def concatenate_videos(sources, output_file):
    if not sources:
        raise RuntimeError("Nenhum vídeo selecionado.")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        normalized = []
        for index, source in enumerate(sources):
            destination = temp_path / f"part_{index:03d}.mp4"
            normalize_video(source, destination)
            normalized.append(destination)

        concat_file = temp_path / "concat.txt"
        concat_file.write_text("".join(f"file '{item.as_posix()}'\n" for item in normalized), encoding="utf-8")
        command = [
            ffmpeg_path(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_file),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "Erro desconhecido")[-1200:]
            raise RuntimeError(detail)


def create_zip(files, destination):
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, arcname=file.name)


def render_project(project_name, count):
    root = project_path(project_name)
    hooks = list_videos(root / "ganchos")
    bodies = list_videos(root / "corpos")
    ctas = list_videos(root / "ctas")
    if not hooks or not bodies or not ctas:
        raise RuntimeError("Adicione pelo menos 1 vídeo em Ganchos, Corpos e CTAs.")

    combinations = list(itertools.product(hooks, bodies, ctas))
    random.shuffle(combinations)
    selected = combinations[: min(count, len(combinations))]
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    progress = st.progress(0, text="Preparando renderização...")
    for index, combination in enumerate(selected, start=1):
        output_file = output_dir / f"video_{index:03d}.mp4"
        progress.progress((index - 1) / len(selected), text=f"Renderizando vídeo {index}/{len(selected)}...")
        concatenate_videos(combination, output_file)
        results.append(output_file)
    progress.progress(1.0, text="Renderização concluída.")
    return results


if not st.session_state.get("auth_ok"):
    login_screen()
    st.stop()

st.sidebar.title("📁 AI Creative Engine")
st.sidebar.caption(st.session_state.get("user_email", ""))
st.sidebar.success(f"Plano: {st.session_state.get('user_plan', 'user').upper()}")
if st.sidebar.button("🚪 Sair", use_container_width=True):
    clear_auth()
    st.rerun()

projects = list_projects()
selected_project = st.sidebar.selectbox("Projeto ativo", projects, key="active_project")
new_project = st.sidebar.text_input("Novo projeto")
if st.sidebar.button("➕ Criar projeto", use_container_width=True):
    project_path(safe_name(new_project))
    st.rerun()

active_path = project_path(selected_project)

st.title(APP_TITLE)
st.caption("Versão estável: upload, combinação e renderização de vídeos em 9:16.")
st.info("Os vídeos são processados localmente no ambiente Streamlit. Esta versão prioriza estabilidade e não executa transcrição automática de legendas.")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.subheader("🪝 Ganchos")
    hook_uploads = st.file_uploader("Enviar ganchos", type=["mp4", "mov", "m4v", "avi", "mkv"], accept_multiple_files=True, key="hooks_upload")
    if hook_uploads:
        save_uploads(hook_uploads, active_path / "ganchos")
        st.success(f"{len(hook_uploads)} arquivo(s) salvo(s).")
    st.write(f"Arquivos: {len(list_videos(active_path / 'ganchos'))}")

with col_b:
    st.subheader("🎥 Corpos")
    body_uploads = st.file_uploader("Enviar corpos", type=["mp4", "mov", "m4v", "avi", "mkv"], accept_multiple_files=True, key="bodies_upload")
    if body_uploads:
        save_uploads(body_uploads, active_path / "corpos")
        st.success(f"{len(body_uploads)} arquivo(s) salvo(s).")
    st.write(f"Arquivos: {len(list_videos(active_path / 'corpos'))}")

with col_c:
    st.subheader("📣 CTAs")
    cta_uploads = st.file_uploader("Enviar CTAs", type=["mp4", "mov", "m4v", "avi", "mkv"], accept_multiple_files=True, key="ctas_upload")
    if cta_uploads:
        save_uploads(cta_uploads, active_path / "ctas")
        st.success(f"{len(cta_uploads)} arquivo(s) salvo(s).")
    st.write(f"Arquivos: {len(list_videos(active_path / 'ctas'))}")

st.divider()
render_count = st.number_input("Quantidade de vídeos", min_value=1, max_value=30, value=3, step=1)
if st.button("🚀 GERAR VÍDEOS", type="primary", use_container_width=True):
    try:
        with st.spinner("Processando os vídeos..."):
            generated = render_project(selected_project, int(render_count))
        st.success(f"{len(generated)} vídeo(s) gerado(s) com sucesso.")
        for file in generated:
            st.video(str(file))
            st.download_button(
                f"⬇️ Baixar {file.name}",
                data=file.read_bytes(),
                file_name=file.name,
                mime="video/mp4",
                key=f"download_{file.name}",
            )
        zip_file = active_path / "output" / "videos_gerados.zip"
        create_zip(generated, zip_file)
        st.download_button(
            "📦 Baixar todos em ZIP",
            data=zip_file.read_bytes(),
            file_name=zip_file.name,
            mime="application/zip",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Não foi possível gerar os vídeos: {exc}")

with st.expander("📂 Arquivos do projeto"):
    for category, label in (("ganchos", "Ganchos"), ("corpos", "Corpos"), ("ctas", "CTAs"), ("output", "Saídas")):
        st.markdown(f"**{label}**")
        files = list_videos(active_path / category)
        if files:
            for file in files:
                st.write(f"• {file.name}")
        else:
            st.caption("Nenhum arquivo")
