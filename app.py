import streamlit as st
import itertools
import os
import tempfile
import subprocess
import zipfile
import shutil
import random
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
# ESTILO
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    .subtitle {
        color: #9ca3af;
        font-size: 17px;
        margin-bottom: 30px;
    }

    .block-title {
        font-size: 24px;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TÍTULO
# ============================================================

st.markdown(
    '<div class="main-title">🎬 AI Creative Engine</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Gerador automático de criativos para vídeos'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("📁 Projetos")

projeto = st.sidebar.selectbox(
    "Projeto ativo",
    [
        "WOMAN_SHOP",
        "RODO_CLEAN",
        "ESPETO_GRILL",
        "SMARTWATCH",
        "NOVO_PRODUTO"
    ]
)

st.sidebar.success(
    f"Projeto ativo:\n{projeto}"
)

st.sidebar.divider()

st.sidebar.subheader("⚙️ Configurações")

embaralhar = st.sidebar.checkbox(
    "🔀 Embaralhar combinações",
    value=False
)

limite = st.sidebar.number_input(
    "Quantidade máxima de vídeos",
    min_value=1,
    max_value=1000,
    value=100,
    step=1
)

st.sidebar.divider()

st.sidebar.caption(
    "AI Creative Engine\n"
    "Gerador de combinações de vídeos"
)


# ============================================================
# UPLOADS
# ============================================================

st.header("1. Gerenciamento dos Blocos")

col1, col2, col3 = st.columns(3)


# ============================================================
# GANCHOS
# ============================================================

with col1:

    st.markdown(
        '<div class="block-title">🎣 Ganchos</div>',
        unsafe_allow_html=True
    )

    ganchos = st.file_uploader(
        "Enviar Ganchos",
        type=["mp4", "mov", "m4v"],
        accept_multiple_files=True,
        key="ganchos"
    )

    if ganchos:
        st.success(
            f"✅ {len(ganchos)} gancho(s)"
        )


# ============================================================
# CORPOS
# ============================================================

with col2:

    st.markdown(
        '<div class="block-title">👤 Corpos</div>',
        unsafe_allow_html=True
    )

    corpos = st.file_uploader(
        "Enviar Corpos",
        type=["mp4", "mov", "m4v"],
        accept_multiple_files=True,
        key="corpos"
    )

    if corpos:
        st.success(
            f"✅ {len(corpos)} corpo(s)"
        )


# ============================================================
# CTAs
# ============================================================

with col3:

    st.markdown(
        '<div class="block-title">📢 CTAs</div>',
        unsafe_allow_html=True
    )

    ctas = st.file_uploader(
        "Enviar CTAs",
        type=["mp4", "mov", "m4v"],
        accept_multiple_files=True,
        key="ctas"
    )

    if ctas:
        st.success(
            f"✅ {len(ctas)} CTA(s)"
        )


# ============================================================
# CONTAGEM
# ============================================================

qtd_ganchos = len(ganchos) if ganchos else 0
qtd_corpos = len(corpos) if corpos else 0
qtd_ctas = len(ctas) if ctas else 0

total_combinacoes = (
    qtd_ganchos
    * qtd_corpos
    * qtd_ctas
)


st.divider()

st.info(
    f"🎬 {qtd_ganchos} Gancho(s) × "
    f"{qtd_corpos} Corpo(s) × "
    f"{qtd_ctas} CTA(s) = "
    f"**{total_combinacoes} vídeo(s)**"
)


# ============================================================
# FUNÇÃO PARA SALVAR UPLOAD
# ============================================================

def salvar_upload(arquivo, pasta, nome):

    caminho = os.path.join(
        pasta,
        nome
    )

    with open(caminho, "wb") as destino:

        destino.write(
            arquivo.getbuffer()
        )

    return caminho


# ============================================================
# FUNÇÃO PARA NORMALIZAR VÍDEO
# ============================================================

def normalizar_video(
    ffmpeg,
    entrada,
    saida
):

    comando = [
        ffmpeg,

        "-y",

        "-i",
        entrada,

        # Vídeo
        "-vf",
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1",

        "-r",
        "30",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "23",

        # Áudio
        "-c:a",
        "aac",

        "-ar",
        "44100",

        "-ac",
        "2",

        "-movflags",
        "+faststart",

        saida
    ]

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if resultado.returncode != 0:

        raise RuntimeError(
            "Erro ao processar vídeo:\n\n"
            + resultado.stderr[-4000:]
        )


# ============================================================
# FUNÇÃO PARA JUNTAR 3 VÍDEOS
# ============================================================

def juntar_videos(
    ffmpeg,
    gancho,
    corpo,
    cta,
    saida
):

    pasta = tempfile.mkdtemp(
        prefix="creative_engine_"
    )

    try:

        entrada_gancho = os.path.join(
            pasta,
            "gancho_original.mp4"
        )

        entrada_corpo = os.path.join(
            pasta,
            "corpo_original.mp4"
        )

        entrada_cta = os.path.join(
            pasta,
            "cta_original.mp4"
        )


        # ----------------------------------------------------
        # SALVAR UPLOADS
        # ----------------------------------------------------

        with open(
            entrada_gancho,
            "wb"
        ) as f:

            f.write(
                gancho.getbuffer()
            )


        with open(
            entrada_corpo,
            "wb"
        ) as f:

            f.write(
                corpo.getbuffer()
            )


        with open(
            entrada_cta,
            "wb"
        ) as f:

            f.write(
                cta.getbuffer()
            )


        # ----------------------------------------------------
        # NORMALIZAR
        # ----------------------------------------------------

        normalizado_gancho = os.path.join(
            pasta,
            "gancho.mp4"
        )

        normalizado_corpo = os.path.join(
            pasta,
            "corpo.mp4"
        )

        normalizado_cta = os.path.join(
            pasta,
            "cta.mp4"
        )


        normalizar_video(
            ffmpeg,
            entrada_gancho,
            normalizado_gancho
        )


        normalizar_video(
            ffmpeg,
            entrada_corpo,
            normalizado_corpo
        )


        normalizar_video(
            ffmpeg,
            entrada_cta,
            normalizado_cta
        )


        # ----------------------------------------------------
        # LISTA PARA CONCATENAÇÃO
        # ----------------------------------------------------

        lista = os.path.join(
            pasta,
            "lista.txt"
        )


        with open(
            lista,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                "file '"
                + normalizado_gancho.replace(
                    "\\",
                    "/"
                )
                + "'\n"
            )

            f.write(
                "file '"
                + normalizado_corpo.replace(
                    "\\",
                    "/"
                )
                + "'\n"
            )

            f.write(
                "file '"
                + normalizado_cta.replace(
                    "\\",
                    "/"
                )
                + "'\n"
            )


        # ----------------------------------------------------
        # CONCATENAR
        # ----------------------------------------------------

        comando = [
            ffmpeg,

            "-y",

            "-f",
            "concat",

            "-safe",
            "0",

            "-i",
            lista,

            "-c",
            "copy",

            "-movflags",
            "+faststart",

            saida
        ]


        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )


        if resultado.returncode != 0:

            raise RuntimeError(
                "Erro ao juntar os vídeos:\n\n"
                + resultado.stderr[-4000:]
            )


    finally:

        shutil.rmtree(
            pasta,
            ignore_errors=True
        )


# ============================================================
# GERAÇÃO
# ============================================================

if (
    ganchos
    and corpos
    and ctas
):

    st.divider()

    st.header("2. Geração dos Vídeos")


    # --------------------------------------------------------
    # CRIAR COMBINAÇÕES
    # --------------------------------------------------------

    combinacoes = list(
        itertools.product(
            ganchos,
            corpos,
            ctas
        )
    )


    # --------------------------------------------------------
    # EMBARALHAR
    # --------------------------------------------------------

    if embaralhar:

        random.shuffle(
            combinacoes
        )


    # --------------------------------------------------------
    # LIMITAR QUANTIDADE
    # --------------------------------------------------------

    combinacoes = combinacoes[
        :limite
    ]


    st.info(
        f"🎬 Serão processadas "
        f"**{len(combinacoes)} combinação(ões)**."
    )


    # --------------------------------------------------------
    # BOTÃO
    # --------------------------------------------------------

    iniciar = st.button(
        "🚀 GERAR VÍDEOS",
        use_container_width=True,
        type="primary"
    )


    if iniciar:

        # ----------------------------------------------------
        # FFmpeg
        # ----------------------------------------------------

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()


        # ----------------------------------------------------
        # PASTA DE SAÍDA
        # ----------------------------------------------------

        pasta_saida = tempfile.mkdtemp(
            prefix="creative_output_"
        )


        videos_gerados = []


        # ----------------------------------------------------
        # PROGRESSO
        # ----------------------------------------------------

        progresso = st.progress(
            0
        )

        status = st.empty()

        contador = st.empty()


        # ----------------------------------------------------
        # PROCESSAMENTO
        # ----------------------------------------------------

        for numero, (
            gancho,
            corpo,
            cta
        ) in enumerate(
            combinacoes,
            start=1
        ):


            nome_saida = os.path.join(
                pasta_saida,
                f"{numero:03d}.mp4"
            )


            status.info(
                f"🎬 Processando "
                f"vídeo {numero} "
                f"de {len(combinacoes)}..."
            )


            contador.write(
                f"Gancho: {gancho.name}  |  "
                f"Corpo: {corpo.name}  |  "
                f"CTA: {cta.name}"
            )


            try:

                juntar_videos(
                    ffmpeg,
                    gancho,
                    corpo,
                    cta,
                    nome_saida
                )


                videos_gerados.append(
                    nome_saida
                )


                progresso.progress(
                    numero / len(combinacoes)
                )


            except Exception as erro:

                st.error(
                    f"❌ Erro no vídeo "
                    f"{numero}:"
                )

                st.code(
                    str(erro)
                )


                continue


        # ----------------------------------------------------
        # RESULTADO
        # ----------------------------------------------------

        if videos_gerados:

            status.success(
                f"🎉 {len(videos_gerados)} "
                f"vídeo(s) gerado(s)!"
            )


            # ------------------------------------------------
            # CRIAR ZIP
            # ------------------------------------------------

            zip_path = os.path.join(
                pasta_saida,
                f"{projeto}_videos.zip"
            )


            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zipf:


                for video in videos_gerados:

                    zipf.write(
                        video,
                        arcname=os.path.basename(
                            video
                        )
                    )


            # ------------------------------------------------
            # TAMANHO DO ZIP
            # ------------------------------------------------

            tamanho_mb = (
                os.path.getsize(
                    zip_path
                )
                / 1024
                / 1024
            )


            st.success(
                f"✅ Processo concluído!\n\n"
                f"🎬 Vídeos: "
                f"{len(videos_gerados)}\n\n"
                f"📦 ZIP: "
                f"{tamanho_mb:.2f} MB"
            )


            # ------------------------------------------------
            # DOWNLOAD
            # ------------------------------------------------

            with open(
                zip_path,
                "rb"
            ) as arquivo_zip:

                st.download_button(
                    label="📦 BAIXAR TODOS OS VÍDEOS",
                    data=arquivo_zip.read(),
                    file_name=f"{projeto}_videos.zip",
                    mime="application/zip",
                    use_container_width=True
                )


            # ------------------------------------------------
            # PRÉ-VISUALIZAÇÃO
            # ------------------------------------------------

            st.divider()

            st.subheader(
                "🎥 Pré-visualização"
            )


            primeiro_video = videos_gerados[0]


            st.video(
                primeiro_video
            )


            st.caption(
                "Pré-visualização do primeiro "
                "vídeo gerado."
            )


        else:

            st.error(
                "❌ Nenhum vídeo foi gerado."
            )


else:

    st.warning(
        "⚠️ Envie pelo menos "
        "1 Gancho, 1 Corpo e 1 CTA "
        "para começar."
    )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "🎬 AI Creative Engine • "
    "Gerador de criativos em vídeo"
)
