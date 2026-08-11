import streamlit as st
import itertools
import os
import re
import random
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
import imageio_ffmpeg

# ============================================================
# AI CREATIVE ENGINE
# Gerador de combinações de vídeos
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
# FUNÇÕES AUXILIARES
# ============================================================

VIDEO_TYPES = ["mp4", "mov", "m4v", "avi", "webm"]


def safe_name(text):
    """Transforma texto em nome seguro para arquivo."""
    text = str(text or "").strip()
    text = re.sub(r"[^A-Za-z0-9À-ÿ_-]+", "_", text)
    text = text.strip("_")
    return text[:80] or "PROJETO"


def get_ffmpeg():
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args):
    """Executa FFmpeg e retorna stdout/stderr em caso de erro."""
    ffmpeg = get_ffmpeg()

    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:] or "Erro desconhecido do FFmpeg.")

    return result


def save_uploaded_file(uploaded_file, folder, prefix):
    """Salva um arquivo enviado pelo usuário."""
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
    Normaliza o vídeo para facilitar a combinação.
    Saída: MP4 H.264, 1080x1920, 30fps, áudio AAC.
    """
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,fps=30,format=yuv420p"
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
    """
    Junta vídeos já normalizados.
    Usa o demuxer concat do FFmpeg.
    """
    list_file = output_path.parent / f"{output_path.stem}_concat.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for video in video_paths:
            safe_path = str(video).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

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


def create_zip(files, zip_path):
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as z:
        for file in files:
            z.write(file, arcname=file.name)


def build_combinations(ganchos, corpos, ctas, shuffle=False, limit=None):
    combinations = list(itertools.product(ganchos, corpos, ctas))

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
# SIDEBAR / PROJETOS
# ============================================================

st.sidebar.header("📁 Projetos")

new_project = st.sidebar.text_input(
    "Novo projeto",
    placeholder="Ex.: RODO_CLEAN_02",
)

if st.sidebar.button("➕ Criar Projeto"):
    project = safe_name(new_project).upper()

    if project and project not in st.session_state.projects:
        st.session_state.projects.append(project)
        st.session_state.last_project = project
        st.sidebar.success(f"Projeto criado: {project}")
        st.rerun()
    elif project in st.session_state.projects:
        st.sidebar.warning("Esse projeto já existe.")
    else:
        st.sidebar.warning("Digite um nome para o projeto.")

project = st.sidebar.selectbox(
    "Projeto ativo",
    st.session_state.projects,
    index=(
        st.session_state.projects.index(st.session_state.last_project)
        if st.session_state.last_project in st.session_state.projects
        else 0
    ),
)

st.session_state.last_project = project

st.sidebar.success(f"Projeto ativo: {project}")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **AI Creative Engine**

    Combina:
    - 🎣 Ganchos
    - 👤 Corpos
    - 📣 CTAs

    e cria os vídeos automaticamente.
    """
)

# ============================================================
# CABEÇALHO
# ============================================================

st.markdown(
    '<div class="main-title">🎬 AI Creative Engine</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Gerador automático de criativos em vídeo</div>',
    unsafe_allow_html=True,
)

# ============================================================
# 1. GERENCIAMENTO DOS BLOCOS
# ============================================================

st.markdown(
    '<div class="block-title">1. Gerenciamento dos Blocos</div>',
    unsafe_allow_html=True,
)

st.caption(
    "Envie vídeos de Gancho, Corpo e CTA. "
    "O sistema combina todas as possibilidades."
)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🎣 Ganchos")

    ganchos = st.file_uploader(
        "Enviar Ganchos",
        type=VIDEO_TYPES,
        accept_multiple_files=True,
        key=f"ganchos_{project}",
        help="Você pode enviar vários vídeos.",
    )

    st.success(f"✅ {len(ganchos)} Gancho(s)")

with col2:
    st.subheader("👤 Corpos")

    corpos = st.file_uploader(
        "Enviar Corpos",
        type=VIDEO_TYPES,
        accept_multiple_files=True,
        key=f"corpos_{project}",
        help="Você pode enviar vários vídeos.",
    )

    st.success(f"✅ {len(corpos)} Corpo(s)")

with col3:
    st.subheader("📣 CTAs")

    ctas = st.file_uploader(
        "Enviar CTAs",
        type=VIDEO_TYPES,
        accept_multiple_files=True,
        key=f"ctas_{project}",
        help="Você pode enviar vários vídeos.",
    )

    st.success(f"✅ {len(ctas)} CTA(s)")


# ============================================================
# OPÇÕES
# ============================================================

st.markdown("---")
st.subheader("⚙️ Opções da geração")

opt1, opt2, opt3 = st.columns(3)

with opt1:
    max_videos = st.number_input(
        "Quantidade máxima de vídeos",
        min_value=1,
        max_value=500,
        value=100,
        step=1,
    )

with opt2:
    shuffle = st.checkbox(
        "🔀 Embaralhar combinações",
        value=False,
    )

with opt3:
    filename_prefix = st.text_input(
        "Nome dos arquivos",
        value=project,
        help="Ex.: RODO_CLEAN",
    )

filename_prefix = safe_name(filename_prefix).upper()


# ============================================================
# COMBINAÇÕES
# ============================================================

total = len(ganchos) * len(corpos) * len(ctas)

if total > 0:
    combinations = build_combinations(
        ganchos,
        corpos,
        ctas,
        shuffle=shuffle,
        limit=int(max_videos),
    )
else:
    combinations = []

st.markdown("---")

if total == 0:
    st.info(
        "🎬 0 Gancho(s) × 0 Corpo(s) × 0 CTA(s) = 0 vídeo(s)"
    )
else:
    st.markdown(
        f"""
        <div class="info-box">
        🎬 <b>{len(ganchos)} Gancho(s)</b> ×
        <b>{len(corpos)} Corpo(s)</b> ×
        <b>{len(ctas)} CTA(s)</b>
        = <b>{total} combinação(ões)</b><br><br>
        Serão processadas <b>{len(combinations)}</b>
        combinação(ões), conforme o limite escolhido.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if total > max_videos:
        st.warning(
            f"⚠️ Existem {total} combinações, mas o limite está em "
            f"{max_videos}. Serão geradas somente {max_videos}."
        )


# ============================================================
# 2. GERAÇÃO DOS VÍDEOS
# ============================================================

st.markdown(
    '<div class="block-title">2. Geração dos Vídeos</div>',
    unsafe_allow_html=True,
)

if not combinations:
    st.warning("Envie pelo menos 1 Gancho, 1 Corpo e 1 CTA.")
else:
    if st.button("🚀 GERAR VÍDEOS", type="primary"):

        st.session_state.generated_files = []
        st.session_state.zip_bytes = None

        progress = st.progress(0)
        status = st.empty()

        generated = []

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp = Path(temp_dir)

                upload_dir = temp / "uploads"
                normalized_dir = temp / "normalized"
                output_dir = temp / "output"

                upload_dir.mkdir()
                normalized_dir.mkdir()
                output_dir.mkdir()

                status.info("📥 Preparando os arquivos enviados...")

                # Salvar uploads
                gancho_paths = []
                corpo_paths = []
                cta_paths = []

                for i, file in enumerate(ganchos, start=1):
                    gancho_paths.append(
                        save_uploaded_file(
                            file,
                            upload_dir,
                            f"gancho_{i}",
                        )
                    )

                for i, file in enumerate(corpos, start=1):
                    corpo_paths.append(
                        save_uploaded_file(
                            file,
                            upload_dir,
                            f"corpo_{i}",
                        )
                    )

                for i, file in enumerate(ctas, start=1):
                    cta_paths.append(
                        save_uploaded_file(
                            file,
                            upload_dir,
                            f"cta_{i}",
                        )
                    )

                # Normalizar somente os arquivos usados
                all_originals = gancho_paths + corpo_paths + cta_paths
                normalized = {}

                status.info("🎞️ Preparando os vídeos para combinação...")

                for index, original in enumerate(all_originals, start=1):
                    normalized_file = (
                        normalized_dir /
                        f"normalized_{index:03d}.mp4"
                    )

                    normalize_video(
                        original,
                        normalized_file,
                    )

                    normalized[str(original)] = normalized_file

                total_to_process = len(combinations)

                for idx, combo in enumerate(combinations, start=1):
                    gancho_file, corpo_file, cta_file = combo

                    g = normalized[str(gancho_paths[ganchos.index(gancho_file)])]
                    c = normalized[str(corpo_paths[corpos.index(corpo_file)])]
                    t = normalized[str(cta_paths[ctas.index(cta_file)])]

                    gancho_index = ganchos.index(gancho_file) + 1
                    corpo_index = corpos.index(corpo_file) + 1
                    cta_index = ctas.index(cta_file) + 1

                    output_name = (
                        f"{filename_prefix}_"
                        f"{idx:03d}_"
                        f"G{gancho_index}_"
                        f"C{corpo_index}_"
                        f"CTA{cta_index}.mp4"
                    )

                    output_file = output_dir / output_name

                    status.info(
                        f"🎬 Gerando vídeo {idx} de "
                        f"{total_to_process}: {output_name}"
                    )

                    concatenate_videos(
                        [g, c, t],
                        output_file,
                    )

                    # Copiar para memória da sessão
                    generated.append(
                        (
                            output_name,
                            output_file.read_bytes(),
                        )
                    )

                    progress.progress(
                        int(idx / total_to_process * 100)
                    )

                # Criar ZIP
                status.info("📦 Criando arquivo ZIP...")

                zip_file = temp / f"{filename_prefix}_VIDEOS.zip"

                with zipfile.ZipFile(
                    zip_file,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as z:
                    for name, data in generated:
                        z.writestr(name, data)

                st.session_state.generated_files = generated
                st.session_state.zip_bytes = zip_file.read_bytes()

                progress.progress(100)

                status.success(
                    f"🎉 {len(generated)} vídeo(s) gerado(s) com sucesso!"
                )

        except Exception as e:
            progress.empty()
            status.error("❌ Ocorreu um erro durante a geração.")
            st.exception(e)


# ============================================================
# RESULTADOS
# ============================================================

if st.session_state.generated_files:

    st.markdown("---")
    st.subheader("🎉 Vídeos gerados")

    st.success(
        f"✅ {len(st.session_state.generated_files)} "
        f"vídeo(s) gerado(s)!"
    )

    for number, (name, data) in enumerate(
        st.session_state.generated_files,
        start=1,
    ):
        with st.expander(f"🎬 {number:03d} — {name}"):

            st.video(data)

            st.download_button(
                "⬇️ Baixar este vídeo",
                data=data,
                file_name=name,
                mime="video/mp4",
                key=f"download_{number}_{name}",
            )

    st.markdown("---")

    if st.session_state.zip_bytes:
        zip_name = f"{safe_name(project)}_VIDEOS.zip"

        st.success(
            f"📦 ZIP pronto com "
            f"{len(st.session_state.generated_files)} vídeo(s)."
        )

        st.download_button(
            "📦 BAIXAR TODOS OS VÍDEOS",
            data=st.session_state.zip_bytes,
            file_name=zip_name,
            mime="application/zip",
            type="primary",
            key="download_all_zip",
        )


# ============================================================
# RODAPÉ
# ============================================================

st.markdown("---")

st.caption(
    "🎬 AI Creative Engine • Gerador de criativos em vídeo"
)
