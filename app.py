import streamlit as st
import itertools
import os
import re
import random
import subprocess
import tempfile
import zipfile
from pathlib import Path
import imageio_ffmpeg

# ============================================================
# AI CREATIVE ENGINE
# ============================================================

st.set_page_config(
    page_title="AI Creative Engine",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>
    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 4px;
    }

    .subtitle {
        color: #9ca3af;
        font-size: 17px;
        margin-bottom: 28px;
    }

    .block-title {
        font-size: 25px;
        font-weight: 700;
        margin-top: 18px;
    }

    .info-box {
        padding: 16px;
        border-radius: 12px;
        background: #17324f;
        margin: 10px 0 18px 0;
        font-size: 17px;
    }

    .success-box {
        padding: 16px;
        border-radius: 12px;
        background: #103d28;
        margin: 10px 0 18px 0;
        font-size: 17px;
    }

    .warning-box {
        padding: 16px;
        border-radius: 12px;
        background: #4a4214;
        margin: 10px 0 18px 0;
        font-size: 17px;
    }

    .small-muted {
        color: #9ca3af;
        font-size: 14px;
    }

    div.stButton > button {
        width: 100%;
        min-height: 48px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

VIDEO_TYPES = ["mp4", "mov", "m4v", "avi", "webm"]


def safe_name(text):
    text = str(text or "").strip()
    text = re.sub(r"[^A-Za-z0-9À-ÿ_-]+", "_", text)
    text = text.strip("_")
    return text[:80] or "PROJETO"


def get_ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args):
    ffmpeg = get_ffmpeg()

    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
    ] + args

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr[-3000:]
            or "Erro desconhecido do FFmpeg."
        )

    return result


def save_uploaded_file(uploaded_file, folder, prefix):
    original = Path(uploaded_file.name)
    extension = original.suffix.lower()

    if extension not in [f".{x}" for x in VIDEO_TYPES]:
        extension = ".mp4"

    filename = safe_name(prefix) + extension
    destination = Path(folder) / filename

    with open(destination, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return destination


def normalize_video(input_path, output_path):
    """
    Converte o vídeo para um padrão comum:
    1080x1920, 30 FPS, H264 e AAC.
    """

    vf = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,"
        "fps=30,"
        "format=yuv420p"
    )

    run_ffmpeg(
        [
            "-i",
            str(input_path),
            "-vf",
            vf,
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
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def concatenate_videos(video_paths, output_path):

    list_file = (
        output_path.parent
        / f"{output_path.stem}_concat.txt"
    )

    with open(
        list_file,
        "w",
        encoding="utf-8"
    ) as f:

        for video in video_paths:

            safe_path = (
                str(video)
                .replace("\\", "/")
                .replace("'", "'\\''")
            )

            f.write(
                f"file '{safe_path}'\n"
            )

    try:

        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )

    finally:

        try:
            list_file.unlink()
        except Exception:
            pass


def build_combinations(
    ganchos,
    corpos,
    ctas,
    shuffle=False,
    limit=None
):

    combinations = list(
        itertools.product(
            ganchos,
            corpos,
            ctas
        )
    )

    if shuffle:
        random.shuffle(combinations)

    if limit and limit > 0:
        combinations = combinations[:limit]

    return combinations


# ============================================================
# ESTADO DA SESSÃO
# ============================================================

if "projects" not in st.session_state:

    st.session_state.projects = [
        "WOMAN_SHOP",
        "RODO_CLEAN",
        "NOVO_PRODUTO",
    ]


if "generated_files" not in st.session_state:

    st.session_state.generated_files = []


if "zip_bytes" not in st.session_state:

    st.session_state.zip_bytes = None


if "last_project" not in st.session_state:

    st.session_state.last_project = "RODO_CLEAN"


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("📁 Projetos")

new_project = st.sidebar.text_input(
    "Novo projeto",
    placeholder="Ex.: RODO_CLEAN_02",
)

if st.sidebar.button("➕ Criar Projeto"):

    project = safe_name(
        new_project
    ).upper()

    if (
        project
        and project not in st.session_state.projects
    ):

        st.session_state.projects.append(
            project
        )

        st.session_state.last_project = project

        st.sidebar.success(
            f"Projeto criado: {project}"
        )

        st.rerun()

    elif project in st.session_state.projects:

        st.sidebar.warning(
            "Esse projeto já existe."
        )

    else:

        st.sidebar.warning(
            "Digite um nome para o projeto."
        )


project = st.sidebar.selectbox(
    "Projeto ativo",
    st.session_state.projects,
    index=(
        st.session_state.projects.index(
            st.session_state.last_project
        )
        if st.session_state.last_project
        in st.session_state.projects
        else 0
    ),
)

st.session_state.last_project = project

st.sidebar.success(
    f"Projeto ativo: {project}"
)

st.sidebar.markdown("---")

st.sidebar.markdown(
    """
    **AI Creative Engine**

    Combina automaticamente:

    🎣 Ganchos

    👤 Corpos

    📣 CTAs
    """
)


# ============================================================
# CABEÇALHO
# ============================================================

st.markdown(
    '<div class="main-title">'
    '🎬 AI Creative Engine'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    'Gerador automático de criativos em vídeo'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# 1. GERENCIAMENTO
# ============================================================

st.markdown(
    '<div class="block-title">'
    '1. Gerenciamento dos Blocos'
    '</div>',
    unsafe_allow_html=True,
)

st.caption(
    "Envie vídeos de Gancho, Corpo e CTA. "
    "O sistema combina todas as possibilidades."
)


col1, col2, col3 = st.columns(3)


# ============================================================
# GANCHOS
# ============================================================

with col1:

    st.subheader("🎣 Ganchos")

    ganchos = st.file_uploader(
        "Enviar Ganchos",
        type=VIDEO_TYPES
