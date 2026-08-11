import streamlit as st
import itertools
import os
import re
import random
import shutil
import zipfile
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="AI Creative Engine",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# FFmpeg fornecido pelo imageio-ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


# ============================================================
# LOGIN
# ============================================================

def verificar_login():
    if st.session_state.get("autenticado", False):
        return True

    st.title("🔐 AI Creative Engine")
    st.caption("Entre para acessar o gerador de vídeos.")

    usuario = st.text_input("👤 Usuário")
    senha = st.text_input("🔑 Senha", type="password")

    if st.button(
        "🚀 ENTRAR",
        type="primary",
        use_container_width=True,
    ):
        import hmac

        usuario_correto = st.secrets.get("LOGIN_USUARIO", "")
        senha_correta = st.secrets.get("LOGIN_SENHA", "")

        if (
            usuario_correto
            and senha_correta
            and hmac.compare_digest(usuario, usuario_correto)
            and hmac.compare_digest(senha, senha_correta)
        ):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("❌ Usuário ou senha incorretos.")

    return False


if not verificar_login():
    st.stop()


# ============================================================
# LOGOUT
# ============================================================

if st.sidebar.button(
    "🚪 Sair",
    use_container_width=True,
):
    st.session_state["autenticado"] = False
    st.rerun()


# ============================================================
# PASTAS
# ============================================================

BASE_DIR = Path("projetos")
BASE_DIR.mkdir(exist_ok=True)


def nome_seguro(nome):
    nome = nome.strip()
    nome = re.sub(r"[^\w\s-]", "", nome)
    nome = nome.replace(" ", "_")

    if not nome:
        nome = "PROJETO"

    return nome


def criar_estrutura_projeto(projeto_path):
    for pasta in [
        "ganchos",
        "corpos",
        "ctas",
        "output",
        "temp",
    ]:
        (projeto_path / pasta).mkdir(
            parents=True,
            exist_ok=True,
        )


def listar_projetos():
    return sorted(
        [
            p.name
            for p in BASE_DIR.iterdir()
            if p.is_dir()
        ]
    )


# ============================================================
# CRIAÇÃO DE PROJETO
# ============================================================

st.sidebar.title("📁 Projetos")

novo_projeto = st.sidebar.text_input(
    "Novo Projeto:"
)

if st.sidebar.button(
    "➕ Criar Projeto",
    use_container_width=True,
):

    if novo_projeto.strip():

        nome = nome_seguro(novo_projeto)

        caminho = BASE_DIR / nome

        criar_estrutura_projeto(caminho)

        st.sidebar.success(
            f"Projeto '{nome}' criado!"
        )

        st.rerun()


st.sidebar.divider()


# ============================================================
# PROJETOS EXISTENTES
# ============================================================

projetos = listar_projetos()

# Criar projeto inicial automaticamente
if not projetos:

    caminho_teste = BASE_DIR / "TESTE"

    criar_estrutura_projeto(caminho_teste)

    projetos = ["TESTE"]


projeto_atual = st.sidebar.selectbox(
    "Selecione o Projeto Ativo:",
    projetos,
)


PROJ_PATH = BASE_DIR / projeto_atual

PATH_GANCHOS = PROJ_PATH / "ganchos"
PATH_CORPOS = PROJ_PATH / "corpos"
PATH_CTAS = PROJ_PATH / "ctas"
PATH_OUTPUT = PROJ_PATH / "output"
PATH_TEMP = PROJ_PATH / "temp"

criar_estrutura_projeto(PROJ_PATH)


# ============================================================
# EXCLUIR PROJETO
# ============================================================

st.sidebar.divider()

if st.sidebar.button(
    "🗑️ Deletar Projeto Atual",
    type="primary",
    use_container_width=True,
):

    shutil.rmtree(PROJ_PATH)

    st.sidebar.success(
        "Projeto excluído."
    )

    st.rerun()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

EXTENSOES = (
    ".mp4",
    ".mov",
    ".m4v",
)


def listar_videos(pasta):

    return sorted(
        [
            p
            for p in pasta.iterdir()
            if p.is_file()
            and p.suffix.lower() in EXTENSOES
        ]
    )


def salvar_uploads(arquivos, destino):

    if not arquivos:
        return

    destino.mkdir(
        parents=True,
        exist_ok=True,
    )

    for arquivo in arquivos:

        nome = re.sub(
            r"[^\w\.-]",
            "_",
            arquivo.name,
        )

        caminho = destino / nome

        with open(
            caminho,
            "wb",
        ) as f:

            f.write(
                arquivo.getbuffer()
            )


def limpar_pasta(pasta):

    pasta.mkdir(
        parents=True,
        exist_ok=True,
    )

    for item in pasta.iterdir():

        try:

            if item.is_file():
                item.unlink()

            elif item.is_dir():
                shutil.rmtree(item)

        except Exception:
            pass


def executar_ffmpeg(
    argumentos,
    descricao="FFmpeg",
):

    comando = [
        FFMPEG
    ] + argumentos

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if resultado.returncode != 0:

        raise RuntimeError(
            f"{descricao} falhou.\n\n"
            f"FFmpeg:\n{FFMPEG}\n\n"
            f"Erro:\n{resultado.stderr[-5000:]}"
        )

    return resultado


def possui_audio(caminho):

    # Usa ffmpeg para testar se existe uma faixa de áudio.
    comando = [
        FFMPEG,
        "-hide_banner",
        "-i",
        str(caminho),
    ]

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    texto = resultado.stderr.lower()

    return "audio:" in texto


# ============================================================
# NORMALIZAÇÃO DOS VÍDEOS
# ============================================================

def normalizar_video(
    entrada,
    saida,
    espelhar=False,
):

    entrada = Path(entrada)
    saida = Path(saida)

    tem_audio = possui_audio(
        entrada
    )

    filtro_video = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=decrease,"
        "pad=1080:1920:"
        "(ow-iw)/2:"
        "(oh-ih)/2,"
        "setsar=1"
    )

    if espelhar:

        filtro_video += ",hflip"

    if tem_audio:

        argumentos = [
            "-y",
            "-i",
            str(entrada),

            "-vf",
            filtro_video,

            "-r",
            "30",

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

            str(saida),
        ]

    else:

        argumentos = [
            "-y",
            "-i",
            str(entrada),

            "-f",
            "lavfi",

            "-i",
            "anullsrc="
            "channel_layout=stereo:"
            "sample_rate=48000",

            "-map",
            "0:v:0",

            "-map",
            "1:a:0",

            "-vf",
            filtro_video,

            "-r",
            "30",

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

            "-shortest",

            "-movflags",
            "+faststart",

            str(saida),
        ]

    executar_ffmpeg(
        argumentos,
        "Normalização do vídeo",
    )


# ============================================================
# CONCATENAÇÃO
# ============================================================

def concatenar_videos(
    videos,
    saida,
):

    lista = saida.parent / (
        saida.stem + "_lista.txt"
    )

    with open(
        lista,
        "w",
        encoding="utf-8",
    ) as f:

        for video in videos:

            caminho = str(
                video.resolve()
            )

            caminho = caminho.replace(
                "\\",
                "/",
            )

            caminho = caminho.replace(
                "'",
                "'\\''",
            )

            f.write(
                f"file '{caminho}'\n"
            )

    try:

        argumentos = [
            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            str(lista),

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

            str(saida),
        ]

        executar_ffmpeg(
            argumentos,
            "Concatenação",
        )

    finally:

        if lista.exists():
            lista.unlink()


# ============================================================
# SCORE
# ============================================================

def calcular_score(texto):

    if not texto.strip():
        return 75

    palavras = len(
        texto.split()
    )

    score = 70

    if 3 <= palavras <= 12:
        score += 15

    if re.search(
        r"\d",
        texto,
    ):
        score += 8

    if "?" in texto or "!" in texto:
        score += 7

    return min(
        98,
        max(
            65,
            score,
        ),
    )


# ============================================================
# ZIP
# ============================================================

def criar_zip(
    arquivos,
    caminho_zip,
):

    with zipfile.ZipFile(
        caminho_zip,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zipf:

        for arquivo in arquivos:

            zipf.write(
                arquivo,
                arcname=arquivo.name,
            )


# ============================================================
# INTERFACE
# ============================================================

st.title(
    f"🎬 AI Creative Engine — {projeto_atual}"
)

st.caption(
    "Multiplicador modular de vídeos"
)

st.divider()


# ============================================================
# 1. UPLOAD
# ============================================================

st.header(
    "1. Gerenciamento dos Blocos de Vídeo"
)

col1, col2, col3 = st.columns(3)


# ------------------------------------------------------------
# GANCHOS
# ------------------------------------------------------------

with col1:

    st.subheader(
        "🪝 Ganchos"
    )

    uploads_h = st.file_uploader(
        "Subir Ganchos",
        type=[
            "mp4",
            "mov",
        ],
        accept_multiple_files=True,
        key="upload_ganchos",
    )

    if uploads_h:

        salvar_uploads(
            uploads_h,
            PATH_GANCHOS,
        )

        st.rerun()

    arquivos_h = listar_videos(
        PATH_GANCHOS
    )

    if arquivos_h:

        st.success(
            f"✅ {len(arquivos_h)} Gancho(s)"
        )

        for arquivo in arquivos_h:

            st.caption(
                arquivo.name
            )

        if st.button(
            "🗑️ Limpar Ganchos",
            key="limpar_ganchos",
        ):

            limpar_pasta(
                PATH_GANCHOS
            )

            st.rerun()

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


# ------------------------------------------------------------
# CORPOS
# ------------------------------------------------------------

with col2:

    st.subheader(
        "📹 Corpos"
    )

    uploads_m = st.file_uploader(
        "Subir Corpos",
        type=[
            "mp4",
            "mov",
        ],
        accept_multiple_files=True,
        key="upload_corpos",
    )

    if uploads_m:

        salvar_uploads(
            uploads_m,
            PATH_CORPOS,
        )

        st.rerun()

    arquivos_m = listar_videos(
        PATH_CORPOS
    )

    if arquivos_m:

        st.success(
            f"✅ {len(arquivos_m)} Corpo(s)"
        )

        for arquivo in arquivos_m:

            st.caption(
                arquivo.name
            )

        if st.button(
            "🗑️ Limpar Corpos",
            key="limpar_corpos",
        ):

            limpar_pasta(
                PATH_CORPOS
            )

            st.rerun()

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


# ------------------------------------------------------------
# CTAS
# ------------------------------------------------------------

with col3:

    st.subheader(
        "📢 CTAs"
    )

    uploads_c = st.file_uploader(
        "Subir CTAs",
        type=[
            "mp4",
            "mov",
        ],
        accept_multiple_files=True,
        key="upload_ctas",
    )

    if uploads_c:

        salvar_uploads(
            uploads_c,
            PATH_CTAS,
        )

        st.rerun()

    arquivos_c = listar_videos(
        PATH_CTAS
    )

    if arquivos_c:

        st.success(
            f"✅ {len(arquivos_c)} CTA(s)"
        )

        for arquivo in arquivos_c:

            st.caption(
                arquivo.name
            )

        if st.button(
            "🗑️ Limpar CTAs",
            key="limpar_ctas",
        ):

            limpar_pasta(
                PATH_CTAS
            )

            st.rerun()

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


# ============================================================
# COMBINAÇÕES
# ============================================================

total_variacoes = (
    len(arquivos_h)
    * len(arquivos_m)
    * len(arquivos_c)
)

st.divider()

if total_variacoes:

    st.info(
        f"🎬 {len(arquivos_h)} Gancho(s) × "
        f"{len(arquivos_m)} Corpo(s) × "
        f"{len(arquivos_c)} CTA(s) = "
        f"**{total_variacoes} vídeo(s)**"
    )

else:

    st.warning(
        "Envie pelo menos 1 Gancho, "
        "1 Corpo e 1 CTA."
    )


# ============================================================
# 2. OPÇÕES
# ============================================================

st.header(
    "2. Opções da Geração"
)

col_a, col_b = st.columns(2)

with col_a:

    embaralhar = st.checkbox(
        "🔀 Embaralhar combinações",
        value=False,
    )

with col_b:

    espelhamento = st.checkbox(
        "↔️ Espelhamento aleatório",
        value=False,
    )


hook_ativo = st.checkbox(
    "📝 Ativar Hook de texto",
    value=False,
)

if hook_ativo:

    texto_hook = st.text_area(
        "Digite os Hooks — um por linha",
        placeholder=(
            "Exemplo:\n"
            "VOCÊ PRECISA VER ISSO!\n"
            "OLHA O RESULTADO!"
        ),
    )

else:

    texto_hook = ""


st.divider()


# ============================================================
# 3. GERAR
# ============================================================

st.header(
    "3. Geração dos Vídeos"
)


if st.button(
    "🚀 MULTIPLICAR E GERAR TODOS OS VÍDEOS",
    type="primary",
    use_container_width=True,
):

    if not arquivos_h:

        st.error(
            "❌ Adicione pelo menos 1 Gancho."
        )

        st.stop()

    if not arquivos_m:

        st.error(
            "❌ Adicione pelo menos 1 Corpo."
        )

        st.stop()

    if not arquivos_c:

        st.error(
            "❌ Adicione pelo menos 1 CTA."
        )

        st.stop()


    # Limpa outputs antigos
    limpar_pasta(
        PATH_OUTPUT
    )


    combos = list(
        itertools.product(
            arquivos_h,
            arquivos_m,
            arquivos_c,
        )
    )


    if embaralhar:

        random.shuffle(
            combos
        )


    st.success(
        f"🔥 Serão gerados "
        f"{len(combos)} vídeo(s)."
    )


    progress = st.progress(0)


    videos_finalizados = []


    try:

        for idx, (
            gancho,
            corpo,
            cta,
        ) in enumerate(combos):

            numero = idx + 1

            st.write(
                f"🎬 Processando "
                f"vídeo {numero}/{len(combos)}..."
            )


            pasta_temp = (
                PATH_TEMP
                / f"video_{numero}"
            )

            pasta_temp.mkdir(
                parents=True,
                exist_ok=True,
            )


            # ------------------------------------------------
            # NORMALIZA GANCHO
            # ------------------------------------------------

            gancho_norm = (
                pasta_temp
                / "01_gancho.mp4"
            )

            normalizar_video(
                gancho,
                gancho_norm,
                (
                    random.choice(
                        [True, False]
                    )
                    if espelhamento
                    else False
                ),
            )


            # ------------------------------------------------
            # NORMALIZA CORPO
            # ------------------------------------------------

            corpo_norm = (
                pasta_temp
                / "02_corpo.mp4"
            )

            normalizar_video(
                corpo,
                corpo_norm,
                (
                    random.choice(
                        [True, False]
                    )
                    if espelhamento
                    else False
                ),
            )


            # ------------------------------------------------
            # NORMALIZA CTA
            # ------------------------------------------------

            cta_norm = (
                pasta_temp
                / "03_cta.mp4"
            )

            normalizar_video(
                cta,
                cta_norm,
                (
                    random.choice(
                        [True, False]
                    )
                    if espelhamento
                    else False
                ),
            )


            # ------------------------------------------------
            # CONCATENA
            # ------------------------------------------------

            nome_saida = (
                f"video_{numero:03d}.mp4"
            )

            saida = (
                PATH_OUTPUT
                / nome_saida
            )


            concatenar_videos(
                [
                    gancho_norm,
                    corpo_norm,
                    cta_norm,
                ],
                saida,
            )


            # ------------------------------------------------
            # HOOK DE TEXTO
            # ------------------------------------------------

            if (
                hook_ativo
                and texto_hook.strip()
            ):

                st.info(
                    "ℹ️ Hook de texto "
                    "será aplicado em "
                    "uma próxima etapa."
                )


            if saida.exists():

                videos_finalizados.append(
                    saida
                )

            else:

                raise RuntimeError(
                    f"O arquivo {saida.name} "
                    "não foi criado."
                )


            progress.progress(
                numero / len(combos)
            )


        # ----------------------------------------------------
        # FINAL
        # ----------------------------------------------------

        limpar_pasta(
            PATH_TEMP
        )

        st.balloons()

        st.success(
            f"🎉 {len(videos_finalizados)} "
            "vídeo(s) gerado(s) com sucesso!"
        )

        st.rerun()


    except Exception as erro:

        st.error(
            "❌ Ocorreu um erro durante "
            "a geração."
        )

        st.code(
            str(erro),
            language="text",
        )

        st.warning(
            "O erro acima é mostrado para "
            "identificarmos exatamente o "
            "problema do FFmpeg."
        )


# ============================================================
# 4. VÍDEOS PRONTOS
# ============================================================

st.divider()

st.header(
    "4. Vídeos Prontos"
)


videos_gerados = sorted(
    listar_videos(
        PATH_OUTPUT
    ),
    key=lambda p: p.name,
)


if not videos_gerados:

    st.info(
        "ℹ️ Nenhum vídeo gerado ainda."
    )

else:

    st.success(
        f"✅ {len(videos_gerados)} "
        "vídeo(s) disponível(is)."
    )


    # --------------------------------------------------------
    # ZIP
    # --------------------------------------------------------

    zip_path = (
        PATH_OUTPUT
        / f"{projeto_atual}_videos.zip"
    )


    criar_zip(
        videos_gerados,
        zip_path,
    )


    with open(
        zip_path,
        "rb",
    ) as arquivo_zip:

        st.download_button(
            label=(
                f"📦 BAIXAR TODOS "
                f"OS {len(videos_gerados)} "
                f"VÍDEOS"
            ),

            data=arquivo_zip,

            file_name=(
                f"{projeto_atual}_videos.zip"
            ),

            mime="application/zip",

            type="primary",

            use_container_width=True,
        )


    st.divider()


    # --------------------------------------------------------
    # GALERIA
    # --------------------------------------------------------

    colunas = st.columns(3)


    for idx, video in enumerate(
        videos_gerados
    ):

        coluna = colunas[
            idx % 3
        ]


        with coluna:

            st.markdown(
                f"### 🎬 {video.name}"
            )


            st.video(
                str(video)
            )


            score = calcular_score(
                texto_hook
            )


            st.metric(
                "🎯 Hook Score",
                f"{score}/100",
            )


            with open(
                video,
                "rb",
            ) as arquivo:

                st.download_button(
                    label=(
                        "⬇️ Baixar Este Vídeo"
                    ),

                    data=arquivo,

                    file_name=video.name,

                    mime="video/mp4",

                    use_container_width=True,

                    key=f"download_{idx}",
                )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "🎬 AI Creative Engine • "
    "Gerador de criativos em vídeo"
)
