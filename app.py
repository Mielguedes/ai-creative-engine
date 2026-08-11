import streamlit as st
import itertools
import re
import shutil
import subprocess
import tempfile
import zipfile
import random
from pathlib import Path

import imageio_ffmpeg
from supabase import create_client, Client


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
# SUPABASE
# ============================================================

SUPABASE_URL = str(
    st.secrets.get("SUPABASE_URL", "")
).strip().rstrip("/")

SUPABASE_KEY = str(
    st.secrets.get("SUPABASE_KEY", "")
).strip()


# Se colocou a URL terminando em /rest/v1/,
# o código corrige automaticamente.
if SUPABASE_URL.endswith("/rest/v1"):
    SUPABASE_URL = SUPABASE_URL[:-8].rstrip("/")


if not SUPABASE_URL:
    st.error("❌ SUPABASE_URL não configurada nos Secrets.")
    st.stop()


if not SUPABASE_KEY:
    st.error("❌ SUPABASE_KEY não configurada nos Secrets.")
    st.stop()


if not SUPABASE_URL.startswith("https://"):
    st.error("❌ SUPABASE_URL inválida.")
    st.code(SUPABASE_URL)
    st.stop()


try:

    supabase: Client = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

except Exception as erro:

    st.error("❌ Erro ao conectar ao Supabase.")
    st.code(str(erro))
    st.stop()


# ============================================================
# FUNÇÃO PARA RESTAURAR SESSÃO
# ============================================================

def restaurar_sessao():

    access_token = st.session_state.get(
        "access_token"
    )

    refresh_token = st.session_state.get(
        "refresh_token"
    )

    if not access_token or not refresh_token:
        return False

    try:

        supabase.auth.set_session(
            access_token,
            refresh_token
        )

        resposta = supabase.auth.get_user()

        if resposta and resposta.user:

            st.session_state[
                "autenticado"
            ] = True

            st.session_state[
                "usuario_id"
            ] = str(
                resposta.user.id
            )

            st.session_state[
                "usuario_email"
            ] = (
                resposta.user.email
                or ""
            )

            return True

    except Exception:

        return False

    return False


# ============================================================
# LOGIN
# ============================================================

def fazer_login():

    # Primeiro tenta restaurar uma sessão existente.
    if restaurar_sessao():

        return True


    st.markdown(
        """
        <h1>🔐 AI Creative Engine</h1>
        """,
        unsafe_allow_html=True
    )

    st.caption(
        "Entre para acessar o gerador de vídeos."
    )


    email = st.text_input(
        "📧 E-mail",
        placeholder="Digite seu e-mail",
        key="login_email"
    )


    senha = st.text_input(
        "🔑 Senha",
        type="password",
        placeholder="Digite sua senha",
        key="login_senha"
    )


    entrar = st.button(
        "🚀 ENTRAR",
        type="primary",
        use_container_width=True
    )


    if entrar:

        email = email.strip()


        if not email:

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

            resposta = (
                supabase.auth
                .sign_in_with_password(
                    {
                        "email": email,
                        "password": senha
                    }
                )
            )


            if not resposta:

                st.error(
                    "❌ Não foi possível autenticar."
                )

                return False


            if not resposta.user:

                st.error(
                    "❌ E-mail ou senha incorretos."
                )

                return False


            # ==================================================
            # SALVAR A SESSÃO
            # ==================================================

            if resposta.session:

                st.session_state[
                    "access_token"
                ] = resposta.session.access_token

                st.session_state[
                    "refresh_token"
                ] = resposta.session.refresh_token


            # ==================================================
            # SALVAR USUÁRIO
            # ==================================================

            st.session_state[
                "autenticado"
            ] = True


            st.session_state[
                "usuario_id"
            ] = str(
                resposta.user.id
            )


            st.session_state[
                "usuario_email"
            ] = (
                resposta.user.email
                or email
            )


            st.session_state.pop(
                "projeto_ativo",
                None
            )


            st.rerun()


        except Exception as erro:

            mensagem = str(erro)


            if (
                "Invalid login credentials"
                in mensagem
            ):

                st.error(
                    "❌ E-mail ou senha incorretos."
                )

            else:

                st.error(
                    "❌ ERRO REAL DO LOGIN:"
                )

                st.code(
                    mensagem
                )


    return False


# ============================================================
# BLOQUEAR APP SEM LOGIN
# ============================================================

if not fazer_login():

    st.stop()


# ============================================================
# USUÁRIO ATUAL
# ============================================================

USUARIO_ID = str(
    st.session_state.get(
        "usuario_id",
        ""
    )
).strip()


USUARIO_EMAIL = str(
    st.session_state.get(
        "usuario_email",
        ""
    )
).strip()


if not USUARIO_ID:

    st.error(
        "❌ Não foi possível identificar o usuário logado."
    )

    st.stop()


# ============================================================
# ESTRUTURA DE PASTAS
# ============================================================

# Cada usuário possui sua própria pasta.
#
# projetos/
#    ID_DO_USUARIO/
#        Projeto A/
#        Projeto B/
#
# Assim os arquivos locais também ficam separados.

BASE_DIR = (
    Path("projetos")
    / USUARIO_ID
)

BASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# NOME SEGURO
# ============================================================

def safe_name(nome):

    nome = re.sub(
        r"[^\w\-. ]",
        "_",
        str(nome),
        flags=re.UNICODE
    )

    nome = nome.strip()

    return nome or "arquivo"


# ============================================================
# PROJETOS NO SUPABASE
# ============================================================

def listar_projetos():

    try:

        resposta = (
            supabase
            .table("projects")
            .select(
                "id,name,created_at"
            )
            .eq(
                "user_id",
                USUARIO_ID
            )
            .order(
                "created_at",
                desc=False
            )
            .execute()
        )


        projetos = []


        for item in (
            resposta.data or []
        ):

            nome = item.get(
                "name"
            )


            if nome:

                projetos.append(
                    safe_name(nome)
                )


        return projetos


    except Exception as erro:

        st.error(
            "❌ Erro ao carregar os projetos."
        )

        st.code(
            str(erro)
        )

        return []


# ============================================================
# VERIFICAR SE PROJETO EXISTE
# ============================================================

def projeto_existe(nome):

    nome = safe_name(
        nome
    )


    try:

        resposta = (
            supabase
            .table("projects")
            .select("id")
            .eq(
                "user_id",
                USUARIO_ID
            )
            .eq(
                "name",
                nome
            )
            .limit(1)
            .execute()
        )


        return bool(
            resposta.data
        )


    except Exception as erro:

        st.error(
            "❌ Erro ao verificar projeto."
        )

        st.code(
            str(erro)
        )

        return False


# ============================================================
# CRIAR PROJETO
# ============================================================

def criar_projeto(nome):

    nome = safe_name(
        nome
    )


    if not nome:

        return None


    # ------------------------------------------
    # CRIAR NO SUPABASE
    # ------------------------------------------

    if not projeto_existe(nome):

        try:

            supabase.table(
                "projects"
            ).insert(
                {
                    "user_id": USUARIO_ID,
                    "name": nome
                }
            ).execute()


        except Exception as erro:

            st.error(
                "❌ Erro ao criar projeto no Supabase."
            )

            st.code(
                str(erro)
            )

            return None


    # ------------------------------------------
    # CRIAR PASTAS
    # ------------------------------------------

    projeto = (
        BASE_DIR
        / nome
    )


    for pasta in [
        "ganchos",
        "corpos",
        "ctas",
        "output"
    ]:

        (
            projeto
            / pasta
        ).mkdir(
            parents=True,
            exist_ok=True
        )


    return projeto


# ============================================================
# DELETAR PROJETO
# ============================================================

def deletar_projeto(nome):

    nome = safe_name(
        nome
    )


    caminho = (
        BASE_DIR
        / nome
    )


    # Apagar arquivos locais.
    if caminho.exists():

        shutil.rmtree(
            caminho
        )


    # Apagar somente o projeto
    # pertencente ao usuário atual.
    (
        supabase
        .table("projects")
        .delete()
        .eq(
            "user_id",
            USUARIO_ID
        )
        .eq(
            "name",
            nome
        )
        .execute()
    )


# ============================================================
# LIMPAR ESTADO DOS UPLOADS
# ============================================================

def limpar_estado_upload():

    chaves = list(
        st.session_state.keys()
    )


    for chave in chaves:

        if chave.startswith(
            "upload_"
        ):

            try:

                del st.session_state[
                    chave
                ]

            except Exception:

                pass


# ============================================================
# VÍDEOS DA PASTA
# ============================================================

def videos_da_pasta(pasta):

    if not pasta.exists():

        return []


    return sorted(
        [
            arquivo
            for arquivo in pasta.iterdir()
            if (
                arquivo.is_file()
                and arquivo.suffix.lower()
                in [
                    ".mp4",
                    ".mov"
                ]
            )
        ]
    )


# ============================================================
# SALVAR UPLOAD
# ============================================================

def salvar_uploads(
    arquivos,
    pasta
):

    pasta.mkdir(
        parents=True,
        exist_ok=True
    )


    salvos = []


    for arquivo in arquivos or []:

        if arquivo is None:

            continue


        extensao = Path(
            arquivo.name
        ).suffix.lower()


        if extensao not in [
            ".mp4",
            ".mov"
        ]:

            continue


        nome_base = safe_name(
            Path(
                arquivo.name
            ).stem
        )


        destino = (
            pasta
            / f"{nome_base}{extensao}"
        )


        try:

            with open(
                destino,
                "wb"
            ) as f:

                f.write(
                    arquivo.getbuffer()
                )


            salvos.append(
                destino
            )


        except Exception as erro:

            st.error(
                f"❌ Erro ao salvar "
                f"{arquivo.name}: {erro}"
            )


    return salvos


# ============================================================
# CRIAR PROJETO PADRÃO
# ============================================================

projetos = listar_projetos()


if not projetos:

    criar_projeto(
        "NOVO_PROJETO"
    )

    projetos = listar_projetos()


if not projetos:

    st.error(
        "❌ Não foi possível criar o projeto inicial."
    )

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "📁 Projetos"
)


st.sidebar.caption(
    f"👤 {USUARIO_EMAIL}"
)


# ============================================================
# SAIR
# ============================================================

if st.sidebar.button(
    "🚪 Sair",
    use_container_width=True
):

    try:

        supabase.auth.sign_out()

    except Exception:

        pass


    # Limpar sessão.
    chaves = [
        "autenticado",
        "usuario_id",
        "usuario_email",
        "access_token",
        "refresh_token",
        "projeto_ativo"
    ]


    for chave in chaves:

        st.session_state.pop(
            chave,
            None
        )


    st.rerun()


# ============================================================
# NOVO PROJETO
# ============================================================

novo_projeto = st.sidebar.text_input(
    "Novo Projeto:",
    key="novo_projeto_input"
)


if st.sidebar.button(
    "➕ Criar Projeto",
    use_container_width=True
):

    if novo_projeto.strip():

        nome = safe_name(
            novo_projeto.strip()
        )


        resultado = criar_projeto(
            nome
        )


        if resultado:

            st.session_state[
                "projeto_ativo"
            ] = nome


            st.session_state[
                "novo_projeto_input"
            ] = ""


            st.rerun()


    else:

        st.sidebar.warning(
            "Digite o nome do projeto."
        )


# ============================================================
# ATUALIZAR PROJETOS
# ============================================================

projetos = listar_projetos()


if not projetos:

    criar_projeto(
        "NOVO_PROJETO"
    )

    projetos = listar_projetos()


if not projetos:

    st.error(
        "❌ Nenhum projeto disponível."
    )

    st.stop()


# ============================================================
# PROJETO ATIVO
# ============================================================

projeto_padrao = st.session_state.get(
    "projeto_ativo",
    projetos[0]
)


if projeto_padrao not in projetos:

    projeto_padrao = projetos[0]


projeto_ativo = st.sidebar.selectbox(
    "Selecione o Projeto Ativo:",
    projetos,
    index=projetos.index(
        projeto_padrao
    )
)


st.session_state[
    "projeto_ativo"
] = projeto_ativo


# ============================================================
# DELETAR PROJETO
# ============================================================

if st.sidebar.button(
    "🗑️ Deletar Projeto Atual",
    type="primary",
    use_container_width=True
):

    try:

        deletar_projeto(
            projeto_ativo
        )


        limpar_estado_upload()


        st.session_state.pop(
            "projeto_ativo",
            None
        )


        st.rerun()


    except Exception as erro:

        st.sidebar.error(
            f"❌ Erro ao deletar: {erro}"
        )


# ============================================================
# ESTRUTURA DO PROJETO
# ============================================================

PROJETO = criar_projeto(
    projeto_ativo
)


if PROJETO is None:

    st.stop()


PATH_GANCHOS = (
    PROJETO
    / "ganchos"
)


PATH_CORPOS = (
    PROJETO
    / "corpos"
)


PATH_CTAS = (
    PROJETO
    / "ctas"
)


PATH_OUTPUT = (
    PROJETO
    / "output"
)


# ============================================================
# FFMPEG
# ============================================================

def executar_ffmpeg(
    argumentos
):

    ffmpeg = (
        imageio_ffmpeg
        .get_ffmpeg_exe()
    )


    resultado = subprocess.run(
        [ffmpeg] + argumentos,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )


    if resultado.returncode != 0:

        raise RuntimeError(
            resultado.stderr[-5000:]
        )


    return resultado


# ============================================================
# NORMALIZAR VÍDEO
# ============================================================

def normalizar_video(
    origem,
    destino
):

    filtro = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=decrease,"
        "pad=1080:1920:"
        "(ow-iw)/2:"
        "(oh-ih)/2,"
        "setsar=1,"
        "fps=30"
    )


    argumentos = [

        "-y",

        "-i",
        str(origem),

        "-vf",
        filtro,

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

        str(destino)
    ]


    try:

        executar_ffmpeg(
            argumentos
        )


    except Exception:

        # Caso o vídeo não tenha áudio,
        # adiciona áudio silencioso.

        argumentos = [

            "-y",

            "-i",
            str(origem),

            "-f",
            "lavfi",

            "-i",
            "anullsrc="
            "channel_layout=stereo:"
            "sample_rate=48000",

            "-vf",
            filtro,

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

            str(destino)
        ]


        executar_ffmpeg(
            argumentos
        )


# ============================================================
# JUNTAR VÍDEOS
# ============================================================

def juntar_videos(
    videos,
    arquivo_saida
):

    with tempfile.TemporaryDirectory() as temp:

        temp_path = Path(
            temp
        )


        normalizados = []


        for indice, video in enumerate(
            videos
        ):

            destino = (
                temp_path
                / f"clip_{indice:03d}.mp4"
            )


            normalizar_v
