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
    initial_sidebar_state="expanded",
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


# Aceita URL normal ou URL terminando em /rest/v1/
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
# LOGIN
# ============================================================

def carregar_usuario():

    try:

        resposta = supabase.auth.get_user()

        if resposta and resposta.user:

            st.session_state["autenticado"] = True

            st.session_state["usuario_id"] = str(
                resposta.user.id
            )

            st.session_state["usuario_email"] = (
                resposta.user.email or ""
            )

            return resposta.user

    except Exception:

        pass

    return None


def fazer_login():

    usuario = carregar_usuario()

    if usuario:

        return True


    st.markdown(
        "<h1>🔐 AI Creative Engine</h1>",
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


    if st.button(
        "🚀 ENTRAR",
        type="primary",
        use_container_width=True
    ):

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

            resposta = supabase.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": senha
                }
            )


            if resposta.user:

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


            else:

                st.error(
                    "❌ Não foi possível autenticar."
                )


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
# USUÁRIO AUTENTICADO
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
        "❌ Não foi possível identificar o usuário autenticado."
    )

    st.stop()


# ============================================================
# PERFIL DO USUÁRIO
# ============================================================

def garantir_perfil():

    try:

        consulta = (
            supabase
            .table("profiles")
            .select(
                "id,email,nome,plano,ativo"
            )
            .eq(
                "email",
                USUARIO_EMAIL
            )
            .limit(1)
            .execute()
        )


        if not consulta.data:

            nome = (
                USUARIO_EMAIL.split("@")[0]
                if "@" in USUARIO_EMAIL
                else "Usuário"
            )


            supabase.table(
                "profiles"
            ).insert(
                {
                    "email": USUARIO_EMAIL,
                    "nome": nome,
                    "plano": "user",
                    "ativo": True,
                }
            ).execute()


    except Exception as erro:

        # O perfil não impede o funcionamento
        # do restante do aplicativo.
        st.session_state[
            "erro_perfil"
        ] = str(erro)


garantir_perfil()


# ============================================================
# PASTA EXCLUSIVA DO USUÁRIO
# ============================================================

BASE_DIR = (
    Path("projetos")
    / USUARIO_ID
)


BASE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FUNÇÃO PARA LIMPAR NOMES
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
# PROJETOS - SUPABASE
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
            resposta.data
            or []
        ):

            nome = safe_name(
                item.get(
                    "name",
                    ""
                )
            )


            if nome:

                projetos.append(
                    nome
                )


        return projetos


    except Exception as erro:

        st.error(
            "❌ Não foi possível carregar seus projetos."
        )

        st.code(
            str(erro)
        )

        return []


def projeto_existe(nome):

    nome = safe_name(
        nome
    )


    try:

        resposta = (
            supabase
            .table("projects")
            .select(
                "id,name"
            )
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


def criar_projeto(nome):

    nome = safe_name(
        nome
    )


    if not nome:

        return None


    # Cria no Supabase somente se ainda não existir.
    if not projeto_existe(nome):

        try:

            supabase.table(
                "projects"
            ).insert(
                {
                    "user_id": USUARIO_ID,
                    "name": nome,
                }
            ).execute()


        except Exception as erro:

            st.error(
                f"❌ Não foi possível criar o projeto '{nome}'."
            )

            st.code(
                str(erro)
            )

            return None


    # Cria as pastas físicas.
    pasta = (
        BASE_DIR
        / nome
    )


    for subpasta in [
        "ganchos",
        "corpos",
        "ctas",
        "output"
    ]:

        (
            pasta
            / subpasta
        ).mkdir(
            parents=True,
            exist_ok=True
        )


    return pasta


def deletar_projeto(nome):

    nome = safe_name(
        nome
    )


    pasta = (
        BASE_DIR
        / nome
    )


    # Apaga arquivos locais.
    if pasta.exists():

        shutil.rmtree(
            pasta
        )


    # Apaga somente o projeto
    # pertencente ao usuário logado.
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
# VÍDEOS
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
                in [".mp4", ".mov"]
            )
        ]
    )


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
                f"❌ Erro ao salvar {arquivo.name}: {erro}"
            )


    return salvos


def limpar_upload_state():

    for chave in list(
        st.session_state.keys()
    ):

        if chave.startswith(
            "upload_"
        ):

            st.session_state.pop(
                chave,
                None
            )


# ============================================================
# CRIAR PROJETO PADRÃO
# ============================================================

projetos = listar_projetos()


if not projetos:

    if criar_projeto(
        "NOVO_PROJETO"
    ):

        projetos = listar_projetos()


if not projetos:

    st.error(
        "❌ Nenhum projeto disponível."
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


    for chave in [
        "autenticado",
        "usuario_id",
        "usuario_email",
        "projeto_ativo"
    ]:

        st.session_state.pop(
            chave,
            None
        )


    st.rerun()


# ============================================================
# NOVO PROJETO
# ============================================================

novo_projeto = st.sidebar.text_input(
    "Novo Projeto",
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


        if criar_projeto(
            nome
        ):

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
# PROJETO ATIVO
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


projeto_padrao = (
    st.session_state.get(
        "projeto_ativo",
        projetos[0]
    )
)


if projeto_padrao not in projetos:

    projeto_padrao = projetos[0]


projeto_ativo = st.sidebar.selectbox(
    "Selecione o Projeto Ativo",
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


        limpar_upload_state()


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
# CAMINHOS DO PROJETO
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

        # Se o vídeo não tiver áudio,
        # cria áudio silencioso.
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


            normalizar_video(
                video,
                destino
            )


            normalizados.append(
                destino
            )


        lista = (
            temp_path
            / "lista.txt"
        )


        with open(
            lista,
            "w",
            encoding="utf-8"
        ) as arquivo:

            for video in normalizados:

                caminho = (
                    str(video)
                    .replace(
                        "\\",
                        "/"
                    )
                )


                arquivo.write(
                    f"file '{caminho}'\n"
                )


        executar_ffmpeg(
            [
                "-y",

                "-f",
                "concat",

                "-safe",
                "0",

                "-i",
                str(lista),

                "-c",
                "copy",

                "-movflags",
                "+faststart",

                str(arquivo_saida)
            ]
        )


# ============================================================
# ZIP
# ============================================================

def criar_zip(
    pasta_saida,
    arquivo_zip
):

    videos = sorted(
        pasta_saida.glob(
            "*.mp4"
        )
    )


    with zipfile.ZipFile(
        arquivo_zip,
        "w",
        zipfile.ZIP_DEFLATED
    ) as zipado:

        for video in videos:

            zipado.write(
                video,
                arcname=video.name
            )


# ============================================================
# TÍTULO
# ============================================================

st.title(
    "🎬 AI Creative Engine"
)


st.caption(
    "Multiplicador modular de vídeos • "
    "9:16 • Geração local"
)


# ============================================================
# GERENCIAMENTO
# ============================================================

st.header(
    "1. Gerenciamento dos Blocos de Vídeo"
)


col1, col2, col3 = st.columns(
    3
)


# ============================================================
# GANCHOS
# ============================================================

with col1:

    st.subheader(
        "🪝 Ganchos"
    )


    uploads_ganchos = st.file_uploader(
        "Subir Ganchos",

        type=[
            "mp4",
            "mov"
        ],

        accept_multiple_files=True,

        key=(
            f"upload_ganchos_"
            f"{USUARIO_ID}_"
            f"{projeto_ativo}"
        )
    )


    if uploads_ganchos:

        salvar_uploads(
            uploads_ganchos,
            PATH_GANCHOS
        )


    ganchos = videos_da_pasta(
        PATH_GANCHOS
    )


    if ganchos:

        st.success(
            f"✅ {len(ganchos)} Gancho(s)"
        )


        for video in ganchos:

            st.caption(
                f"🎬 {video.name}"
            )


    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


    if st.button(
        "🗑️ Limpar Ganchos",

        key=(
            f"limpar_ganchos_"
            f"{USUARIO_ID}_"
            f"{projeto_ativo}"
        )
    ):

        for video in videos_da_pasta(
            PATH_GANCHOS
        ):

            video.unlink(
                missing_ok=True
            )


        limpar_upload_state()

        st.rerun()


# ============================================================
# CORPOS
# ============================================================

with col2:

    st.subheader(
        "📹 Corpos"
    )


    uploads_corpos = st.file_uploader(
        "Subir Corpos",

        type=[
            "mp4",
            "mov"
        ],

        accept_multiple_files=True,

        key=(
            f"upload_corpos_"
            f"{USUARIO_ID}_"
            f"{projeto_ativo}"
        )
    )


    if uploads_corpos:

        salvar_uploads(
            uploads_corpos,
            PATH_CORPOS
        )


    corpos = videos_da_pasta(
        PATH_CORPOS
    )


    if corpos:

        st.success(
            f"✅ {len(corpos)} Corpo(s)"
        )


        for video in corpos:

            st.caption(
                f"🎬 {video.name}"
            )


    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


    if st.button(
        "🗑️ Limpar Corpos",

        key=(
            f"limpar_corpos_"
            f"{USUARIO_ID}_"
            f"{projeto_ativo}"
        )
    ):

        for video in videos_da_pasta(
            PATH_CORPOS
        ):

            video.unlink(
                missing_ok=True
            )


        limpar_upload_state()

        st.rerun()


# ============================================================
# CTAS
# ============================================================

with col3:

    st.subheader(
        "📣 CTAs"
    )


    uploads_ctas = st.file_uploader(
        "Subir CTAs",

        type=[
            "mp4",
            "mov"
        ],

        accept_multiple_files=True,

        key=(
            f"upload_ctas_"
            f"{USUARIO_ID}_"
            f"{projeto_ativo}"
        )
    )


    if uploads_ctas:

        salvar_uploads(
            uploads_ctas,
            PATH_CTAS
        )


    ctas = videos_da_pasta(
        PATH_CTAS
    )


    if ctas:

        st.success(
            f"✅ {len(ctas)} CTA(s)"
        )


        for video in ctas:

            st.caption(
                f"🎬 {video.name}"
            )


    else:

        st.warning(
            "⚠️ Nenhum vídeo"
        )


    if st.button(
        "🗑️ Limpar CTAs",

        key=(
            f"limpar_ctas_"
            f"{USUARIO_ID}_"
            f"{projeto_ativo}"
        )
    ):

        for video in videos_da_pasta(
            PATH_CTAS
        ):

            video.unlink(
                missing_ok=True
            )


        limpar_upload_state()

        st.rerun()


# ============================================================
# ATUALIZAR LISTAS
# ============================================================

ganchos = videos_da_pasta(
    PATH_GANCHOS
)


corpos = videos_da_pasta(
    PATH_CORPOS
)


ctas = videos_da_pasta(
    PATH_CTAS
)


quantidade_combinacoes = (
    len(ganchos)
    *
    len(corpos)
    *
    len(ctas)
)


st.divider()


st.info(
    f"🎬 "
    f"{len(ganchos)} Gancho(s) × "
    f"{len(corpos)} Corpo(s) × "
    f"{len(ctas)} CTA(s) "
    f"= {quantidade_combinacoes} vídeo(s)"
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

        value=max(
            1,
            min(
                100,
                quantidade_combinacoes
            )
        ),

        step=1
    )


with op2:

    embaralhar = st.checkbox(
        "🔀 Embaralhar combinações"
    )


with op3:

    nome_arquivos = st.text_input(
        "Nome dos arquivos",
        value=projeto_ativo
    )


# ============================================================
# AVISO
# ============================================================

if quantidade_combinacoes:

    st.success(
        f"🔥 Serão processados até "
        f"{min(quantidade_combinacoes, int(max_videos))} vídeo(s)."
    )

else:

    st.warning(
        "Envie pelo menos 1 Gancho, "
        "1 Corpo e 1 CTA."
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
        quantidade_combinacoes == 0
    )
)


if gerar:

    combinacoes = list(
        itertools.product(
            ganchos,
            corpos,
            ctas
        )
    )


    if embaralhar:

        random.shuffle(
            combinacoes
        )


    combinacoes = combinacoes[
        :int(max_videos)
    ]


    # Limpa vídeos antigos
    # SOMENTE deste projeto.
    for antigo in PATH_OUTPUT.glob(
        "*.mp4"
    ):

        antigo.unlink(
            missing_ok=True
        )


    for antigo in PATH_OUTPUT.glob(
        "*.zip"
    ):

        antigo.unlink(
            missing_ok=True
        )


    st.success(
        f"🔥 Serão gerados "
        f"{len(combinacoes)} vídeo(s)."
    )


    progresso = st.progress(
        0
    )


    gerados = []

    erros = []


    for indice, combinacao in enumerate(
        combinacoes,
        start=1
    ):

        st.write(
            f"🎬 Processando vídeo "
            f"{indice}/{len(combinacoes)}..."
        )


        nome_saida = (
            f"{safe_name(nome_arquivos)}_"
            f"{indice:03d}.mp4"
        )


        arquivo_saida = (
            PATH_OUTPUT
            / nome_saida
        )


        try:

            juntar_videos(
                combinacao,
                arquivo_saida
            )


            gerados.append(
                arquivo_saida
            )


        except Exception as erro:

            erros.append(
                (
                    nome_saida,
                    str(erro)
                )
            )


        progresso.progress(
            indice
            /
            len(combinacoes)
        )


    if gerados:

        st.success(
            f"🎉 {len(gerados)} vídeo(s) "
            f"gerado(s) com sucesso!"
        )


    if erros:

        st.error(
            f"❌ {len(erros)} vídeo(s) "
            f"apresentaram erro."
        )


        for nome, erro in erros:

            with st.expander(
                f"Detalhes: {nome}"
            ):

                st.code(
                    erro
                )


    st.rerun()


# ============================================================
# GALERIA
# ============================================================

videos_prontos = sorted(
    PATH_OUTPUT.glob(
        "*.mp4"
    )
)


if videos_prontos:

    st.divider()


    st.header(
        "🎬 Galeria de Vídeos Prontos"
    )


    colunas = st.columns(
        3
    )


    for indice, video in enumerate(
        videos_prontos
    ):

        with colunas[
            indice % 3
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
            ) as arquivo:

                dados = arquivo.read()


            st.download_button(
                "⬇️ Baixar Este Vídeo",

                data=dados,

                file_name=video.name,

                mime="video/mp4",

                use_container_width=True,

                key=(
                    f"download_"
                    f"{USUARIO_ID}_"
                    f"{projeto_ativo}_"
                    f"{indice}"
                )
            )


    # ========================================================
    # ZIP
    # ========================================================

    arquivo_zip = (
        PATH_OUTPUT
        /
        f"{safe_name(projeto_ativo)}_videos.zip"
    )


    criar_zip(
        PATH_OUTPUT,
        arquivo_zip
    )


    with open(
        arquivo_zip,
        "rb"
    ) as arquivo:

        dados_zip = arquivo.read()


    st.download_button(
        "📦 BAIXAR TODOS OS VÍDEOS",

        data=dados_zip,

        file_name=arquivo_zip.name,

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
