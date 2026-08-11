import streamlit as st
import itertools
import os
import re
import shutil
import subprocess
import random
import zipfile
import tempfile

from faster_whisper import WhisperModel
from supabase import create_client
import imageio_ffmpeg


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="AI Creative Engine",
    page_icon="🎬",
    layout="wide"
)


# ============================================================
# FFmpeg
# ============================================================

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def executar_ffmpeg(comando):
    """
    Executa o FFmpeg e retorna:
    sucesso, mensagem
    """

    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if resultado.returncode != 0:
            return False, resultado.stderr

        return True, resultado.stdout

    except Exception as e:
        return False, str(e)


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")


if not SUPABASE_URL or not SUPABASE_KEY:

    st.error("❌ Supabase não configurado.")

    st.info(
        "Abra os Secrets do Streamlit e confira se existem "
        "SUPABASE_URL e SUPABASE_KEY."
    )

    st.stop()


try:

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as e:

    st.error("❌ Erro ao conectar ao Supabase.")

    st.code(str(e))

    st.stop()


# ============================================================
# SESSÃO
# ============================================================

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "usuario_email" not in st.session_state:
    st.session_state["usuario_email"] = ""


# ============================================================
# LOGIN
# ============================================================

def verificar_login():

    if st.session_state.get("autenticado", False):
        return True

    st.title("🔐 AI Creative Engine")

    st.caption(
        "Entre para acessar o gerador de vídeos."
    )

    email = st.text_input(
        "📧 E-mail",
        placeholder="Digite seu e-mail"
    )

    senha = st.text_input(
        "🔑 Senha",
        type="password",
        placeholder="Digite sua senha"
    )

    entrar = st.button(
        "🚀 ENTRAR",
        type="primary",
        use_container_width=True
    )

    if entrar:

        if not email.strip():

            st.warning(
                "⚠️ Digite seu e-mail."
            )

            return False

        if not senha:

            st.warning(
                "⚠️ Digite sua senha."
            )

            return False

        try:

            resposta = supabase.auth.sign_in_with_password(
                {
                    "email": email.strip(),
                    "password": senha
                }
            )

            usuario = getattr(
                resposta,
                "user",
                None
            )

            sessao = getattr(
                resposta,
                "session",
                None
            )

            if usuario is not None and sessao is not None:

                st.session_state[
                    "autenticado"
                ] = True

                st.session_state[
                    "usuario_email"
                ] = email.strip()

                st.rerun()

            else:

                st.error(
                    "❌ O Supabase não retornou uma sessão."
                )

                st.info(
                    "Verifique se o usuário existe no "
                    "Authentication > Users."
                )

        except Exception as e:

            st.error(
                "❌ ERRO REAL DO LOGIN:"
            )

            st.code(
                str(e)
            )

    return False


# ============================================================
# PARAR SE NÃO ESTIVER LOGADO
# ============================================================

if not verificar_login():
    st.stop()


# ============================================================
# LOGOUT
# ============================================================

if st.sidebar.button(
    "🚪 Sair",
    use_container_width=True
):

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state[
        "autenticado"
    ] = False

    st.session_state.pop(
        "usuario_email",
        None
    )

    st.rerun()


# ============================================================
# PASTA PRINCIPAL
# ============================================================

BASE_DIR = os.path.abspath(
    "projetos"
)

os.makedirs(
    BASE_DIR,
    exist_ok=True
)


# ============================================================
# LISTAR PROJETOS
# ============================================================

def listar_projetos():

    return sorted(
        [
            nome
            for nome in os.listdir(BASE_DIR)
            if os.path.isdir(
                os.path.join(
                    BASE_DIR,
                    nome
                )
            )
        ]
    )


# ============================================================
# LIMPAR NOME
# ============================================================

def limpar_nome(nome):

    nome = nome.strip()

    nome = re.sub(
        r"[^\w\s-]",
        "",
        nome
    )

    nome = nome.replace(
        " ",
        "_"
    )

    return nome


# ============================================================
# CRIAR PROJETO
# ============================================================

st.sidebar.title("📁 Projetos")

novo_projeto = st.sidebar.text_input(
    "Novo Projeto:"
)

if st.sidebar.button(
    "➕ Criar Projeto",
    use_container_width=True
):

    nome_limpo = limpar_nome(
        novo_projeto
    )

    if not nome_limpo:

        st.sidebar.warning(
            "Digite um nome para o projeto."
        )

    else:

        caminho_novo = os.path.join(
            BASE_DIR,
            nome_limpo
        )

        os.makedirs(
            os.path.join(
                caminho_novo,
                "ganchos"
            ),
            exist_ok=True
        )

        os.makedirs(
            os.path.join(
                caminho_novo,
                "corpos"
            ),
            exist_ok=True
        )

        os.makedirs(
            os.path.join(
                caminho_novo,
                "ctas"
            ),
            exist_ok=True
        )

        os.makedirs(
            os.path.join(
                caminho_novo,
                "output"
            ),
            exist_ok=True
        )

        st.sidebar.success(
            f"Projeto '{nome_limpo}' criado."
        )

        st.rerun()


# ============================================================
# PROJETOS
# ============================================================

st.sidebar.divider()

projetos = listar_projetos()


if not projetos:

    st.warning(
        "⚠️ Nenhum projeto criado."
    )

    st.info(
        "Crie um projeto no menu lateral."
    )

    st.stop()


# ============================================================
# PROJETO ATUAL
# ============================================================

projeto_atual = st.sidebar.selectbox(
    "Selecione o Projeto Ativo:",
    projetos
)


PROJ_PATH = os.path.join(
    BASE_DIR,
    projeto_atual
)


PATH_GANCHOS = os.path.join(
    PROJ_PATH,
    "ganchos"
)

PATH_CORPOS = os.path.join(
    PROJ_PATH,
    "corpos"
)

PATH_CTAS = os.path.join(
    PROJ_PATH,
    "ctas"
)

PATH_OUTPUT = os.path.join(
    PROJ_PATH,
    "output"
)


# Garantir pastas

for pasta in [
    PATH_GANCHOS,
    PATH_CORPOS,
    PATH_CTAS,
    PATH_OUTPUT
]:

    os.makedirs(
        pasta,
        exist_ok=True
    )


# ============================================================
# DELETAR PROJETO
# ============================================================

st.sidebar.divider()

if st.sidebar.button(
    "🗑️ Deletar Projeto Atual",
    type="primary",
    use_container_width=True
):

    try:

        if os.path.exists(
            PROJ_PATH
        ):

            shutil.rmtree(
                PROJ_PATH
            )

        st.session_state.pop(
            "projeto_confirmado",
            None
        )

        st.sidebar.success(
            f"Projeto '{projeto_atual}' deletado."
        )

        st.rerun()

    except Exception as e:

        st.sidebar.error(
            "❌ Não foi possível deletar."
        )

        st.code(
            str(e)
        )


# ============================================================
# CABEÇALHO
# ============================================================

st.title(
    f"🎬 AI Creative Engine — {projeto_atual}"
)

st.caption(
    f"Usuário: {st.session_state.get('usuario_email', '')}"
)

st.caption(
    "Multiplicador Modular de Vídeos"
)

st.divider()


# ============================================================
# FUNÇÕES DE ARQUIVOS
# ============================================================

EXTENSOES_VIDEO = (
    ".mp4",
    ".mov",
    ".m4v"
)


def listar_videos(pasta):

    if not os.path.exists(pasta):
        return []

    return sorted(
        [
            f
            for f in os.listdir(pasta)
            if f.lower().endswith(
                EXTENSOES_VIDEO
            )
        ]
    )


def salvar_uploads(
    arquivos,
    destino
):

    os.makedirs(
        destino,
        exist_ok=True
    )

    nomes_salvos = []

    for arquivo in arquivos:

        nome = limpar_nome(
            os.path.splitext(
                arquivo.name
            )[0]
        )

        extensao = os.path.splitext(
            arquivo.name
        )[1].lower()

        nome_final = (
            f"{nome}{extensao}"
        )

        caminho = os.path.join(
            destino,
            nome_final
        )

        contador = 1

        while os.path.exists(caminho):

            nome_final = (
                f"{nome}_{contador}"
                f"{extensao}"
            )

            caminho = os.path.join(
                destino,
                nome_final
            )

            contador += 1

        with open(
            caminho,
            "wb"
        ) as f:

            f.write(
                arquivo.getbuffer()
            )

        nomes_salvos.append(
            nome_final
        )

    return nomes_salvos


def limpar_pasta(pasta):

    if not os.path.exists(pasta):
        return

    for nome in os.listdir(pasta):

        caminho = os.path.join(
            pasta,
            nome
        )

        try:

            if os.path.isfile(
                caminho
            ) or os.path.islink(
                caminho
            ):

                os.remove(
                    caminho
                )

            elif os.path.isdir(
                caminho
            ):

                shutil.rmtree(
                    caminho
                )

        except Exception:
            pass


# ============================================================
# GERENCIADOR DE VÍDEOS
# ============================================================

st.subheader(
    "1. Gerenciamento dos Blocos de Vídeo"
)

col1, col2, col3 = st.columns(3)


# ============================================================
# GANCHOS
# ============================================================

with col1:

    st.markdown(
        "### 🪝 Ganchos"
    )

    upload_ganchos = st.file_uploader(
        "Subir Ganchos",
        type=[
            "mp4",
            "mov",
            "m4v"
        ],
        accept_multiple_files=True,
        key=f"gancho_{projeto_atual}"
    )

    if upload_ganchos:

        salvar_uploads(
            upload_ganchos,
            PATH_GANCHOS
        )

        st.success(
            "Vídeo(s) salvo(s)!"
        )

    arquivos_h = listar_videos(
        PATH_GANCHOS
    )

    if arquivos_h:

        st.success(
            f"✅ {len(arquivos_h)} Gancho(s)"
        )

        for nome in arquivos_h:

            st.caption(
                f"🎬 {nome}"
            )

            caminho = os.path.join(
                PATH_GANCHOS,
                nome
            )

            st.video(
                caminho
            )

        if st.button(
            "🗑️ Limpar Ganchos",
            key=f"limpar_h_{projeto_atual}"
        ):

            limpar_pasta(
                PATH_GANCHOS
            )

            st.rerun()

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


# ============================================================
# CORPOS
# ============================================================

with col2:

    st.markdown(
        "### 📹 Corpos"
    )

    upload_corpos = st.file_uploader(
        "Subir Corpos",
        type=[
            "mp4",
            "mov",
            "m4v"
        ],
        accept_multiple_files=True,
        key=f"corpo_{projeto_atual}"
    )

    if upload_corpos:

        salvar_uploads(
            upload_corpos,
            PATH_CORPOS
        )

        st.success(
            "Vídeo(s) salvo(s)!"
        )

    arquivos_m = listar_videos(
        PATH_CORPOS
    )

    if arquivos_m:

        st.success(
            f"✅ {len(arquivos_m)} Corpo(s)"
        )

        for nome in arquivos_m:

            st.caption(
                f"🎬 {nome}"
            )

            caminho = os.path.join(
                PATH_CORPOS,
                nome
            )

            st.video(
                caminho
            )

        if st.button(
            "🗑️ Limpar Corpos",
            key=f"limpar_m_{projeto_atual}"
        ):

            limpar_pasta(
                PATH_CORPOS
            )

            st.rerun()

    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


# ============================================================
# CTAS
# ============================================================

with col3:

    st.markdown(
        "### 📢 CTAs"
    )

    upload_ctas = st.file_uploader(
        "Subir CTAs",
        type=[
            "mp4",
            "mov",
            "m4v"
        ],
        accept_multiple_files=True,
        key=f"cta_{projeto_atual}"
    )

    if upload_ctas:

        salvar_uploads(
            upload_ctas,
            PATH_CTAS
        )

        st.success(
            "Vídeo(s) salvo(s)!"
        )

    arquivos_c = listar_videos(
        PATH_CTAS
    )

    if arquivos_c:

        st.success(
            f"✅ {len(arquivos_c)} CTA(s)"
        )

        for nome in arquivos_c:

            st.caption(
                f"🎬 {nome}"
            )

            caminho = os.path.join(
                PATH_CTAS,
                nome
            )

            st.video(
                caminho
            )

        if st.button(
            "🗑️ Limpar CTAs",
            key=f"limpar_c_{projeto_atual}"
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


if total_variacoes:

    st.info(
        f"📊 Combinação base: "
        f"**{len(arquivos_h)}** Gancho(s) × "
        f"**{len(arquivos_m)}** Corpo(s) × "
        f"**{len(arquivos_c)}** CTA(s) = "
        f"**{total_variacoes} vídeo(s)**"
    )

else:

    st.warning(
        "⚠️ Para gerar vídeos, coloque pelo menos "
        "1 Gancho, 1 Corpo e 1 CTA."
    )


st.divider()


# ============================================================
# OPÇÕES
# ============================================================

st.subheader(
    "2. Estilização & Modificadores"
)


# ============================================================
# ENCODER
# ============================================================

st.markdown(
    "#### ⚡ Renderização"
)

tipo_gpu = st.selectbox(
    "Escolha o modo de renderização:",
    [
        "CPU Padrão — Recomendado",
        "NVIDIA NVENC",
        "AMD AMF",
        "Intel QSV"
    ]
)


if tipo_gpu == "NVIDIA NVENC":

    encoder = "h264_nvenc"

elif tipo_gpu == "AMD AMF":

    encoder = "h264_amf"

elif tipo_gpu == "Intel QSV":

    encoder = "h264_qsv"

else:

    encoder = "libx264"


if encoder != "libx264":

    st.warning(
        "⚠️ No Streamlit Cloud, recomendamos "
        "CPU Padrão. GPU geralmente não está disponível."
    )


# ============================================================
# ESPELHAMENTO
# ============================================================

espelhar = st.checkbox(
    "🪞 Espelhamento aleatório por bloco",
    value=False
)


# ============================================================
# ANTI DUPLICIDADE
# ============================================================

anti_dup = st.checkbox(
    "🛡️ Aplicar pequena variação visual",
    value=True
)


# ============================================================
# HOOK
# ============================================================

st.markdown(
    "#### 📌 Hook"
)

hook_ativo = st.checkbox(
    "Ativar Hook no topo",
    value=False
)


if hook_ativo:

    texto_manchete = st.text_area(
        "Frases do Hook — uma por linha",
        placeholder=(
            "Exemplo:\n"
            "VOCÊ AINDA FAZ ISSO?\n"
            "OLHA ESSA DIFERENÇA!\n"
            "EU NÃO ACREDITAVA!"
        ),
        height=120
    )

    posicao_hook = st.slider(
        "Posição do Hook",
        50,
        1000,
        200,
        10
    )

    tamanho_hook = st.number_input(
        "Tamanho do Hook",
        30,
        200,
        80,
        5
    )

else:

    texto_manchete = ""

    posicao_hook = 200

    tamanho_hook = 80


# ============================================================
# LEGENDAS
# ============================================================

st.markdown(
    "#### 🗣️ Legendas Automáticas"
)

legenda_ativa = st.checkbox(
    "Ativar legendas automáticas",
    value=False
)


if legenda_ativa:

    posicao_legenda = st.slider(
        "Altura da legenda",
        100,
        1200,
        450,
        20
    )

    tamanho_legenda = st.number_input(
        "Tamanho da legenda",
        40,
        150,
        80,
        5
    )

else:

    posicao_legenda = 450
    tamanho_legenda = 80


# ============================================================
# FUNÇÃO PARA FORMATAR TEMPO ASS
# ============================================================

def formatar_ass(segundos):

    horas = int(
        segundos // 3600
    )

    minutos = int(
        (segundos % 3600) // 60
    )

    segundos_restantes = (
        segundos % 60
    )

    return (
        f"{horas}:"
        f"{minutos:02d}:"
        f"{segundos_restantes:05.2f}"
    )


# ============================================================
# GERAR HOOK ASS
# ============================================================

def gerar_hook_ass(
    texto,
    caminho
):

    conteudo = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,Arial,{tamanho_hook},&H00000000,&H00000000,&H00FFFFFF,&HFFFFFFFF,-1,0,0,0,100,100,0,0,3,15,0,8,30,30,{posicao_hook},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Hook,,0,0,0,,{texto}
"""

    with open(
        caminho,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            conteudo
        )


# ============================================================
# GERAR LEGENDAS
# ============================================================

def gerar_legendas(
    video,
    caminho_ass
):

    try:

        model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

        segments, _ = model.transcribe(
            video,
            word_timestamps=True,
            language="pt"
        )

        conteudo = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Legenda,Arial,80,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,30,30,450,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        for segment in segments:

            if not segment.words:
                continue

            for palavra in segment.words:

                texto = (
                    palavra.word
                    .strip()
                    .upper()
                )

                if not texto:
                    continue

                inicio = formatar_ass(
                    palavra.start
                )

                fim = formatar_ass(
                    palavra.end
                )

                conteudo += (
                    f"Dialogue: 0,"
                    f"{inicio},"
                    f"{fim},"
                    f"Legenda,,0,0,0,,"
                    f"{texto}\n"
                )

        with open(
            caminho_ass,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                conteudo
            )

        return True

    except Exception as e:

        st.warning(
            "⚠️ Não foi possível gerar "
            f"as legendas: {e}"
        )

        return False


# ============================================================
# NORMALIZAR VÍDEO
# ============================================================

def normalizar_video(
    entrada,
    saida,
    espelhar_video=False
):

    filtro = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=decrease,"
        "pad=1080:1920:"
        "(ow-iw)/2:(oh-ih)/2,"
        "setsar=1"
    )

    if espelhar_video:

        filtro += ",hflip"

    comando = [
        FFMPEG,
        "-y",
        "-i",
        entrada,
        "-vf",
        filtro,
        "-r",
        "30",
        "-c:v",
        encoder,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        saida
    ]

    return executar_ffmpeg(
        comando
    )


# ============================================================
# CONCATENAR
# ============================================================

def concatenar_videos(
    videos,
    saida
):

    lista = os.path.join(
        PROJ_PATH,
        f"concat_{random.randint(100000,999999)}.txt"
    )

    try:

        with open(
            lista,
            "w",
            encoding="utf-8"
        ) as f:

            for video in videos:

                caminho = (
                    video
                    .replace(
                        "\\",
                        "/"
                    )
                    .replace(
                        "'",
                        "'\\''"
                    )
                )

                f.write(
                    f"file '{caminho}'\n"
                )

        comando = [
            FFMPEG,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            lista,
            "-c:v",
            encoder,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            saida
        ]

        sucesso, erro = executar_ffmpeg(
            comando
        )

        return sucesso, erro

    finally:

        if os.path.exists(
            lista
        ):

            try:
                os.remove(
                    lista
                )
            except Exception:
                pass


# ============================================================
# APLICAR FILTRO VISUAL
# ============================================================

def aplicar_variacao_visual(
    entrada,
    saida
):

    brilho = round(
        random.uniform(
            -0.015,
            0.025
        ),
        3
    )

    contraste = round(
        random.uniform(
            1.01,
            1.06
        ),
        3
    )

    saturacao = round(
        random.uniform(
            0.97,
            1.06
        ),
        3
    )

    filtro = (
        f"eq="
        f"brightness={brilho}:"
        f"contrast={contraste}:"
        f"saturation={saturacao}"
    )

    comando = [
        FFMPEG,
        "-y",
        "-i",
        entrada,
        "-vf",
        filtro,
        "-c:v",
        encoder,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        saida
    ]

    return executar_ffmpeg(
        comando
    )


# ============================================================
# APLICAR ASS
# ============================================================

def aplicar_ass(
    entrada,
    ass,
    saida
):

    caminho = (
        ass
        .replace(
            "\\",
            "/"
        )
        .replace(
            ":",
            "\\:"
        )
    )

    filtro = (
        f"subtitles='{caminho}'"
    )

    comando = [
        FFMPEG,
        "-y",
        "-i",
        entrada,
        "-vf",
        filtro,
        "-c:v",
        encoder,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        saida
    ]

    return executar_ffmpeg(
        comando
    )


# ============================================================
# GERAR VÍDEOS
# ============================================================

st.divider()

st.subheader(
    "3. Geração dos Vídeos"
)


if st.button(
    "🚀 MULTIPLICAR E GERAR TODOS OS VÍDEOS",
    type="primary",
    use_container_width=True
):

    arquivos_h = listar_videos(
        PATH_GANCHOS
    )

    arquivos_m = listar_videos(
        PATH_CORPOS
    )

    arquivos_c = listar_videos(
        PATH_CTAS
    )

    if (
        not arquivos_h
        or not arquivos_m
        or not arquivos_c
    ):

        st.error(
            "❌ Você precisa ter pelo menos "
            "1 Gancho + 1 Corpo + 1 CTA."
        )

        st.stop()


    combos = list(
        itertools.product(
            arquivos_h,
            arquivos_m,
            arquivos_c
        )
    )


    st.success(
        f"🔥 Serão gerados "
        f"{len(combos)} vídeo(s)."
    )


    progresso = st.progress(
        0
    )

    status = st.empty()


    lista_hooks = [
        linha.strip()
        for linha in texto_manchete.splitlines()
        if linha.strip()
    ]


    for indice, combo in enumerate(
        combos
    ):

        nome_h, nome_m, nome_c = combo


        status.info(
            f"🎬 Processando vídeo "
            f"{indice + 1}/{len(combos)}..."
        )


        caminho_h = os.path.join(
            PATH_GANCHOS,
            nome_h
        )

        caminho_m = os.path.join(
            PATH_CORPOS,
            nome_m
        )

        caminho_c = os.path.join(
            PATH_CTAS,
            nome_c
        )


        temp_dir = os.path.join(
            PROJ_PATH,
            "temp"
        )

        os.makedirs(
            temp_dir,
            exist_ok=True
        )


        h_tmp = os.path.join(
            temp_dir,
            f"h_{indice}.mp4"
        )

        m_tmp = os.path.join(
            temp_dir,
            f"m_{indice}.mp4"
        )

        c_tmp = os.path.join(
            temp_dir,
            f"c_{indice}.mp4"
        )


        saida_base = os.path.join(
            PATH_OUTPUT,
            f"video_final_{indice + 1}.mp4"
        )


        # ----------------------------------------
        # ESPELHAMENTO
        # ----------------------------------------

        esp_h = (
            random.choice(
                [True, False]
            )
            if espelhar
            else False
        )

        esp_m = (
            random.choice(
                [True, False]
            )
            if espelhar
            else False
        )

        esp_c = (
            random.choice(
                [True, False]
            )
            if espelhar
            else False
        )


        # ----------------------------------------
        # NORMALIZAR
        # ----------------------------------------

        ok, erro = normalizar_video(
            caminho_h,
            h_tmp,
            esp_h
        )

        if not ok:

            st.error(
                f"Erro no Gancho:\n{erro}"
            )

            continue


        ok, erro = normalizar_video(
            caminho_m,
            m_tmp,
            esp_m
        )

        if not ok:

            st.error(
                f"Erro no Corpo:\n{erro}"
            )

            continue


        ok, erro = normalizar_video(
            caminho_c,
            c_tmp,
            esp_c
        )

        if not ok:

            st.error(
                f"Erro no CTA:\n{erro}"
            )

            continue


        # ----------------------------------------
        # CONCATENAR
        # ----------------------------------------

        ok, erro = concatenar_videos(
            [
                h_tmp,
                m_tmp,
                c_tmp
            ],
            saida_base
        )


        if not ok:

            st.error(
                f"❌ Erro ao juntar "
                f"o vídeo {indice + 1}:"
            )

            st.code(
                erro
            )

            continue


        arquivo_atual = saida_base


        # ----------------------------------------
        # LEGENDAS
        # ----------------------------------------

        if legenda_ativa:

            ass = os.path.join(
                temp_dir,
                f"legenda_{indice}.ass"
            )

            legenda_ok = gerar_legendas(
                arquivo_atual,
                ass
            )

            if legenda_ok:

                saida_legenda = os.path.join(
                    temp_dir,
                    f"legenda_video_{indice}.mp4"
                )

                ok, erro = aplicar_ass(
                    arquivo_atual,
                    ass,
                    saida_legenda
                )

                if ok:

                    shutil.move(
                        saida_legenda,
                        arquivo_atual
                    )


        # ----------------------------------------
        # HOOK
        # ----------------------------------------

        if (
            hook_ativo
            and lista_hooks
        ):

            texto_hook = (
                lista_hooks[
                    indice
                    % len(lista_hooks)
                ]
            )

            ass_hook = os.path.join(
                temp_dir,
                f"hook_{indice}.ass"
            )

            gerar_hook_ass(
                texto_hook,
                ass_hook
            )

            saida_hook = os.path.join(
                temp_dir,
                f"hook_video_{indice}.mp4"
            )

            ok, erro = aplicar_ass(
                arquivo_atual,
                ass_hook,
                saida_hook
            )

            if ok:

                shutil.move(
                    saida_hook,
                    arquivo_atual
                )


        # ----------------------------------------
        # ANTI DUPLICIDADE
        # ----------------------------------------

        if anti_dup:

            saida_variacao = os.path.join(
                temp_dir,
                f"variacao_{indice}.mp4"
            )

            ok, erro = aplicar_variacao_visual(
                arquivo_atual,
                saida_variacao
            )

            if ok:

                shutil.move(
                    saida_variacao,
                    arquivo_atual
                )


        # ----------------------------------------
        # LIMPEZA
        # ----------------------------------------

        for arquivo_temp in [
            h_tmp,
            m_tmp,
            c_tmp
        ]:

            if os.path.exists(
                arquivo_temp
            ):

                try:

                    os.remove(
                        arquivo_temp
                    )

                except Exception:
                    pass


        progresso.progress(
            (indice + 1)
            / len(combos)
        )


    status.success(
        "🎉 Geração concluída!"
    )


    st.balloons()

    st.rerun()


# ============================================================
# GALERIA
# ============================================================

st.divider()

st.subheader(
    "4. Vídeos Prontos"
)


videos_gerados = sorted(
    [
        nome
        for nome in os.listdir(
            PATH_OUTPUT
        )
        if nome.lower().endswith(
            ".mp4"
        )
    ]
)


if not videos_gerados:

    st.info(
        "ℹ️ Nenhum vídeo gerado ainda."
    )

else:

    st.success(
        f"✅ {len(videos_gerados)} vídeo(s) disponíveis."
    )


    # ========================================
    # ZIP
    # ========================================

    zip_path = os.path.join(
        PATH_OUTPUT,
        f"{projeto_atual}_videos.zip"
    )


    try:

        with zipfile.ZipFile(
            zip_path,
            "w",
            zipfile.ZIP_DEFLATED
        ) as zipf:

            for video in videos_gerados:

                caminho = os.path.join(
                    PATH_OUTPUT,
                    video
                )

                zipf.write(
                    caminho,
                    arcname=video
                )

        with open(
            zip_path,
            "rb"
        ) as arquivo_zip:

            st.download_button(
                "📦 BAIXAR TODOS OS VÍDEOS (.ZIP)",
                data=arquivo_zip,
                file_name=(
                    f"{projeto_atual}_videos.zip"
                ),
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

    except Exception as e:

        st.warning(
            f"Não foi possível criar o ZIP: {e}"
        )


    st.write("")


    # ========================================
    # GALERIA
    # ========================================

    colunas = st.columns(3)


    for indice, video in enumerate(
        videos_gerados
    ):

        caminho_video = os.path.join(
            PATH_OUTPUT,
            video
        )

        with colunas[
            indice % 3
        ]:

            st.markdown(
                f"### 🎬 Vídeo {indice + 1}"
            )

            st.caption(
                video
            )

            st.video(
                caminho_video
            )

            try:

                tamanho = os.path.getsize(
                    caminho_video
                )

                tamanho_mb = round(
                    tamanho / 1024 / 1024,
                    2
                )

                st.caption(
                    f"📦 {tamanho_mb} MB"
                )

            except Exception:
                pass


            with open(
                caminho_video,
                "rb"
            ) as arquivo_video:

                st.download_button(
                    "⬇️ Baixar Este Vídeo",
                    data=arquivo_video,
                    file_name=video,
                    mime="video/mp4",
                    use_container_width=True,
                    key=(
                        f"download_"
                        f"{projeto_atual}_"
                        f"{indice}"
                    )
                )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "🎬 AI Creative Engine • "
    "Gerador de criativos em vídeo"
)
