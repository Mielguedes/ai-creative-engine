import streamlit as st
import itertools
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import imageio_ffmpeg


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="AI Creative Engine",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# PASTA PRINCIPAL
# ============================================================

BASE_DIR = Path("projetos")
BASE_DIR.mkdir(exist_ok=True)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def safe_name(name):
    """
    Remove caracteres problemáticos dos nomes.
    """
    name = re.sub(
        r"[^\w\-. ]",
        "_",
        name,
        flags=re.UNICODE
    ).strip()

    return name or "arquivo"


def list_projects():
    """
    Lista os projetos existentes.
    """
    return sorted(
        [
            p.name
            for p in BASE_DIR.iterdir()
            if p.is_dir()
        ]
    )


def ensure_project(name):
    """
    Cria a estrutura completa do projeto.
    """

    project = BASE_DIR / safe_name(name)

    folders = [
        "ganchos",
        "corpos",
        "ctas",
        "output"
    ]

    for folder in folders:
        (
            project / folder
        ).mkdir(
            parents=True,
            exist_ok=True
        )

    return project


def video_files(folder):
    """
    Retorna somente vídeos MP4 e MOV.
    """

    if not folder.exists():
        return []

    return sorted(
        [
            p
            for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() in [
                ".mp4",
                ".mov"
            ]
        ]
    )


def save_uploads(files, folder):
    """
    Salva os vídeos enviados pelo usuário.
    """

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    saved = []

    for uploaded in files or []:

        if uploaded is None:
            continue

        suffix = Path(
            uploaded.name
        ).suffix.lower()

        if suffix not in [
            ".mp4",
            ".mov"
        ]:
            continue

        filename = (
            safe_name(
                Path(
                    uploaded.name
                ).stem
            )
            + suffix
        )

        target = folder / filename

        with open(
            target,
            "wb"
        ) as f:

            f.write(
                uploaded.getbuffer()
            )

        saved.append(target)

    return saved


def clear_uploader_state():

    """
    Limpa estados dos uploaders.
    """

    for key in list(
        st.session_state.keys()
    ):

        if key.startswith(
            "upload_"
        ):

            del st.session_state[key]


# ============================================================
# FFMPEG
# ============================================================

def run_ffmpeg(args):

    """
    Executa o FFmpeg.
    """

    ffmpeg_exe = (
        imageio_ffmpeg
        .get_ffmpeg_exe()
    )

    result = subprocess.run(
        [ffmpeg_exe] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:

        raise RuntimeError(
            result.stderr[-5000:]
        )

    return result


# ============================================================
# NORMALIZAÇÃO DOS VÍDEOS
# ============================================================

def normalize_clip(
    source,
    destination
):

    """
    Converte cada vídeo para:

    1080x1920
    9:16
    30 FPS
    H264
    AAC
    """

    args = [

        "-y",

        "-i",
        str(source),

        "-vf",
        (
            "scale=1080:1920:"
            "force_original_aspect_ratio=decrease,"
            "pad=1080:1920:"
            "(ow-iw)/2:"
            "(oh-ih)/2,"
            "setsar=1,"
            "fps=30"
        ),

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "23",

        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-ar",
        "48000",

        "-ac",
        "2",

        "-movflags",
        "+faststart",

        str(destination)
    ]

    try:

        run_ffmpeg(
            args
        )

    except RuntimeError:

        # Caso o vídeo original não tenha áudio,
        # adiciona áudio silencioso.

        args = [

            "-y",

            "-i",
            str(source),

            "-f",
            "lavfi",

            "-i",
            "anullsrc="
            "channel_layout=stereo:"
            "sample_rate=48000",

            "-vf",
            (
                "scale=1080:1920:"
                "force_original_aspect_ratio=decrease,"
                "pad=1080:1920:"
                "(ow-iw)/2:"
                "(oh-ih)/2,"
                "setsar=1,"
                "fps=30"
            ),

            "-map",
            "0:v:0",

            "-map",
            "1:a:0",

            "-shortest",

            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-crf",
            "23",

            "-pix_fmt",
            "yuv420p",

            "-c:a",
            "aac",

            "-b:a",
            "128k",

            "-ar",
            "48000",

            "-ac",
            "2",

            "-movflags",
            "+faststart",

            str(destination)
        ]

        run_ffmpeg(
            args
        )


# ============================================================
# JUNTAR OS 3 BLOCOS
# ============================================================

def concat_clips(
    clips,
    output_file
):

    """
    Junta:

    Gancho
    +
    Corpo
    +
    CTA

    em um único MP4.
    """

    with tempfile.TemporaryDirectory() as temp:

        temp_path = Path(temp)

        normalized = []

        # ----------------------------------------
        # NORMALIZA CADA CLIPE
        # ----------------------------------------

        for i, clip in enumerate(clips):

            destination = (
                temp_path
                / f"clip_{i:03d}.mp4"
            )

            normalize_clip(
                clip,
                destination
            )

            normalized.append(
                destination
            )

        # ----------------------------------------
        # CRIA LISTA PARA O FFMPEG
        # ----------------------------------------

        concat_file = (
            temp_path
            / "concat.txt"
        )

        with open(
            concat_file,
            "w",
            encoding="utf-8"
        ) as f:

            for clip in normalized:

                path = (
                    str(clip)
                    .replace("\\", "/")
                    .replace(
                        "'",
                        "'\\''"
                    )
                )

                f.write(
                    f"file '{path}'\n"
                )

        # ----------------------------------------
        # JUNTA OS VÍDEOS
        # ----------------------------------------

        args = [

            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            str(concat_file),

            "-c",
            "copy",

            "-movflags",
            "+faststart",

            str(output_file)
        ]

        run_ffmpeg(
            args
        )


# ============================================================
# DELETAR PROJETO
# ============================================================

def delete_project(name):

    project = (
        BASE_DIR
        / safe_name(name)
    )

    if project.exists():

        shutil.rmtree(
            project
        )


# ============================================================
# CRIAR ZIP
# ============================================================

def zip_outputs(
    output_folder,
    zip_path
):

    files = sorted(
        output_folder.glob(
            "*.mp4"
        )
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED
    ) as z:

        for file in files:

            z.write(
                file,
                arcname=file.name
            )


# ============================================================
# LOGIN
# ============================================================

def login():

    if st.session_state.get(
        "authenticated",
        False
    ):

        return True

    st.markdown(
        "# 🔐 AI Creative Engine"
    )

    st.caption(
        "Entre para acessar o gerador de vídeos."
    )

    usuario = st.text_input(
        "👤 Usuário",
        key="login_user"
    )

    senha = st.text_input(
        "🔑 Senha",
        type="password",
        key="login_password"
    )

    if st.button(
        "🚀 ENTRAR",
        type="primary",
        use_container_width=True
    ):

        # Lê os dados dos Secrets do Streamlit.
        #
        # Se ainda não tiver configurado,
        # usa admin / admin123 somente para teste.

        usuario_correto = (
            st.secrets.get(
                "LOGIN_USUARIO",
                "admin"
            )
        )

        senha_correta = (
            st.secrets.get(
                "LOGIN_SENHA",
                "admin123"
            )
        )

        if (
            usuario == usuario_correto
            and
            senha == senha_correta
        ):

            st.session_state[
                "authenticated"
            ] = True

            st.rerun()

        else:

            st.error(
                "❌ Usuário ou senha incorretos."
            )

    return False


# ============================================================
# VERIFICA LOGIN
# ============================================================

if not login():

    st.stop()


# ============================================================
# CRIA PROJETO PADRÃO
# ============================================================

projects = list_projects()

if not projects:

    ensure_project(
        "NOVO_PROJETO"
    )

    projects = list_projects()


# ============================================================
# BARRA LATERAL
# ============================================================

st.sidebar.markdown(
    "## 📁 Projetos"
)


# ----------------------------------------
# SAIR
# ----------------------------------------

if st.sidebar.button(
    "🚪 Sair",
    use_container_width=True
):

    st.session_state[
        "authenticated"
    ] = False

    st.rerun()


# ----------------------------------------
# NOVO PROJETO
# ----------------------------------------

novo_projeto = st.sidebar.text_input(
    "Novo Projeto",
    key="new_project"
)


if st.sidebar.button(
    "➕ Criar Projeto",
    use_container_width=True
):

    if novo_projeto.strip():

        nome = safe_name(
            novo_projeto.strip()
        )

        ensure_project(
            nome
        )

        st.session_state[
            "active_project"
        ] = nome

        st.rerun()

    else:

        st.sidebar.warning(
            "Digite um nome para o projeto."
        )


# ----------------------------------------
# LISTA DE PROJETOS
# ----------------------------------------

projects = list_projects()

active_default = (
    st.session_state.get(
        "active_project",
        projects[0]
    )
)

if active_default not in projects:

    active_default = projects[0]


project_name = st.sidebar.selectbox(
    "Selecione o Projeto Ativo",
    projects,
    index=projects.index(
        active_default
    )
)

st.session_state[
    "active_project"
] = project_name


# ============================================================
# DELETAR PROJETO
# ============================================================

if st.sidebar.button(
    "🗑️ Deletar Projeto Atual",
    type="primary",
    use_container_width=True
):

    projeto_deletado = project_name

    delete_project(
        projeto_deletado
    )

    clear_uploader_state()

    st.session_state.pop(
        "active_project",
        None
    )

    st.session_state.pop(
        "generated_files",
        None
    )

    st.session_state.pop(
        "generation_done",
        None
    )

    # Se apagou tudo, cria um projeto novo.
    if not list_projects():

        ensure_project(
            "NOVO_PROJETO"
        )

        st.session_state[
            "active_project"
        ] = "NOVO_PROJETO"

    st.rerun()


# ============================================================
# ESTRUTURA DO PROJETO
# ============================================================

PROJECT = ensure_project(
    project_name
)

PATH_GANCHOS = (
    PROJECT / "ganchos"
)

PATH_CORPOS = (
    PROJECT / "corpos"
)

PATH_CTAS = (
    PROJECT / "ctas"
)

PATH_OUTPUT = (
    PROJECT / "output"
)


# ============================================================
# TÍTULO
# ============================================================

st.title(
    "🎬 AI Creative Engine"
)

st.caption(
    "Multiplicador modular de vídeos • 9:16 • Geração local"
)


# ============================================================
# GERENCIAMENTO
# ============================================================

st.header(
    "1. Gerenciamento dos Blocos de Vídeo"
)


col1, col2, col3 = st.columns(3)


# ============================================================
# GANCHOS
# ============================================================

with col1:

    st.subheader(
        "🪝 Ganchos"
    )

    uploads_h = st.file_uploader(
        "Subir Ganchos",
        type=[
            "mp4",
            "mov"
        ],
        accept_multiple_files=True,
        key=f"upload_h_{project_name}"
    )

    if uploads_h:

        save_uploads(
            uploads_h,
            PATH_GANCHOS
        )

    current_h = video_files(
        PATH_GANCHOS
    )

    if current_h:

        st.success(
            f"✅ {len(current_h)} Gancho(s)"
        )

        for file in current_h:

            st.caption(
                f"🎬 {file.name}"
            )

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )

    if st.button(
        "🗑️ Limpar Ganchos",
        key="clear_h"
    ):

        for file in video_files(
            PATH_GANCHOS
        ):

            file.unlink(
                missing_ok=True
            )

        clear_uploader_state()

        st.rerun()


# ============================================================
# CORPOS
# ============================================================

with col2:

    st.subheader(
        "📹 Corpos"
    )

    uploads_m = st.file_uploader(
        "Subir Corpos",
        type=[
            "mp4",
            "mov"
        ],
        accept_multiple_files=True,
        key=f"upload_m_{project_name}"
    )

    if uploads_m:

        save_uploads(
            uploads_m,
            PATH_CORPOS
        )

    current_m = video_files(
        PATH_CORPOS
    )

    if current_m:

        st.success(
            f"✅ {len(current_m)} Corpo(s)"
        )

        for file in current_m:

            st.caption(
                f"🎬 {file.name}"
            )

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )

    if st.button(
        "🗑️ Limpar Corpos",
        key="clear_m"
    ):

        for file in video_files(
            PATH_CORPOS
        ):

            file.unlink(
                missing_ok=True
            )

        clear_uploader_state()

        st.rerun()


# ============================================================
# CTAs
# ============================================================

with col3:

    st.subheader(
        "📣 CTAs"
    )

    uploads_c = st.file_uploader(
        "Subir CTAs",
        type=[
            "mp4",
            "mov"
        ],
        accept_multiple_files=True,
        key=f"upload_c_{project_name}"
    )

    if uploads_c:

        save_uploads(
            uploads_c,
            PATH_CTAS
        )

    current_c = video_files(
        PATH_CTAS
    )

    if current_c:

        st.success(
            f"✅ {len(current_c)} CTA(s)"
        )

        for file in current_c:

            st.caption(
                f"🎬 {file.name}"
            )

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )

    if st.button(
        "🗑️ Limpar CTAs",
        key="clear_c"
    ):

        for file in video_files(
            PATH_CTAS
        ):

            file.unlink(
                missing_ok=True
            )

        clear_uploader_state()

        st.rerun()


# ============================================================
# ATUALIZA LISTAS
# ============================================================

current_h = video_files(
    PATH_GANCHOS
)

current_m = video_files(
    PATH_CORPOS
)

current_c = video_files(
    PATH_CTAS
)


# ============================================================
# COMBINAÇÕES
# ============================================================

base_count = (
    len(current_h)
    *
    len(current_m)
    *
    len(current_c)
)


st.divider()


st.info(
    f"🎬 "
    f"{len(current_h)} Gancho(s) × "
    f"{len(current_m)} Corpo(s) × "
    f"{len(current_c)} CTA(s) "
    f"= {base_count} vídeo(s)"
)


# ============================================================
# OPÇÕES
# ============================================================

st.header(
    "⚙️ Opções da geração"
)


op1, op2, op3 = st.columns(
    [1, 1, 2]
)


with op1:

    max_videos = st.number_input(
        "Quantidade máxima de vídeos",
        min_value=1,
        max_value=100,
        value=min(
            100,
            max(
                1,
                base_count
            )
        ),
        step=1
    )


with op2:

    shuffle = st.checkbox(
        "🔀 Embaralhar combinações"
    )


with op3:

    file_prefix = st.text_input(
        "Nome dos arquivos",
        value=project_name
    )


# ============================================================
# AVISO
# ============================================================

if base_count > 0:

    st.success(
        f"🔥 Serão processados "
        f"até {min(base_count, int(max_videos))} vídeo(s)."
    )

else:

    st.warning(
        "Envie pelo menos "
        "1 Gancho, 1 Corpo e 1 CTA."
    )


# ============================================================
# GERAÇÃO
# ============================================================

st.header(
    "2. Geração dos Vídeos"
)


gerar = st.button(
    "🚀 MULTIPLICAR E GERAR TODOS OS VÍDEOS",
    type="primary",
    use_container_width=True,
    disabled=(
        base_count == 0
    )
)


if gerar:

    combinations = list(
        itertools.product(
            current_h,
            current_m,
            current_c
        )
    )


    # ----------------------------------------
    # EMBARALHAR
    # ----------------------------------------

    if shuffle:

        import random

        random.shuffle(
            combinations
        )


    # ----------------------------------------
    # LIMITAR
    # ----------------------------------------

    combinations = combinations[
        :int(max_videos)
    ]


    # ----------------------------------------
    # LIMPAR VÍDEOS ANTIGOS
    # ----------------------------------------

    for old in PATH_OUTPUT.glob(
        "*.mp4"
    ):

        old.unlink(
            missing_ok=True
        )


    for old in PATH_OUTPUT.glob(
        "*.zip"
    ):

        old.unlink(
            missing_ok=True
        )


    st.success(
        f"🔥 Serão gerados "
        f"{len(combinations)} vídeo(s)."
    )


    progress = st.progress(
        0
    )


    generated = []

    errors = []


    # ========================================================
    # PROCESSA CADA COMBINAÇÃO
    # ========================================================

    for idx, combo in enumerate(
        combinations,
        start=1
    ):

        st.write(
            f"🎬 Processando vídeo "
            f"{idx}/{len(combinations)}..."
        )


        output_name = (
            f"{safe_name(file_prefix)}_"
            f"{idx:03d}.mp4"
        )


        output_file = (
            PATH_OUTPUT
            / output_name
        )


        try:

            concat_clips(
                combo,
                output_file
            )

            generated.append(
                output_file
            )


        except Exception as error:

            errors.append(
                (
                    output_name,
                    str(error)
                )
            )


        progress.progress(
            idx / len(combinations)
        )


    # ========================================================
    # RESULTADO
    # ========================================================

    st.session_state[
        "generated_files"
    ] = [
        str(file)
        for file in generated
    ]


    st.session_state[
        "generation_done"
    ] = True


    if generated:

        st.success(
            f"🎉 {len(generated)} vídeo(s) "
            f"gerado(s) com sucesso!"
        )


    if errors:

        st.error(
            f"❌ {len(errors)} vídeo(s) "
            f"apresentaram erro."
        )


        for name, error in errors:

            with st.expander(
                f"Detalhes: {name}"
            ):

                st.code(
                    error
                )


    st.rerun()


# ============================================================
# GALERIA
# ============================================================

ready_videos = sorted(
    PATH_OUTPUT.glob(
        "*.mp4"
    )
)


if ready_videos:

    st.divider()

    st.header(
        "🎬 Galeria de Vídeos Prontos"
    )


    cols = st.columns(3)


    for idx, video in enumerate(
        ready_videos
    ):

        with cols[
            idx % 3
        ]:

            st.markdown(
                f"**🎬 {video.name}**"
            )


            st.video(
                str(video)
            )


            with open(
                video,
                "rb"
            ) as file:

                st.download_button(
                    "⬇️ Baixar Este Vídeo",
                    data=file.read(),
                    file_name=video.name,
                    mime="video/mp4",
                    use_container_width=True,
                    key=f"download_{idx}"
                )


    # ========================================================
    # ZIP
    # ========================================================

    zip_file = (
        PATH_OUTPUT
        / f"{safe_name(project_name)}_videos.zip"
    )


    zip_outputs(
        PATH_OUTPUT,
        zip_file
    )


    with open(
        zip_file,
        "rb"
    ) as file:

        st.download_button(
            "📦 BAIXAR TODOS OS VÍDEOS",
            data=file.read(),
            file_name=zip_file.name,
            mime="application/zip",
            use_container_width=True
        )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "🎬 AI Creative Engine • "
    "Gerador de criativos em vídeo"
)
