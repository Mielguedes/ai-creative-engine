import streamlit as st
import itertools
import os
import tempfile
import subprocess
import zipfile
import imageio_ffmpeg

st.set_page_config(
    page_title="AI Creative Engine",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Creative Engine")
st.caption("Gerador automático de vídeos")

st.sidebar.header("📁 Projetos")

projeto = st.sidebar.selectbox(
    "Projeto ativo",
    [
        "WOMAN_SHOP",
        "RODO_CLEAN",
        "NOVO_PRODUTO"
    ]
)

st.sidebar.success(f"Projeto ativo: {projeto}")

st.header("1. Gerenciamento dos Blocos")

col1, col2, col3 = st.columns(3)

with col1:

    st.subheader("🎣 Ganchos")

    ganchos = st.file_uploader(
        "Enviar Ganchos",
        type=["mp4", "mov"],
        accept_multiple_files=True,
        key="ganchos"
    )

with col2:

    st.subheader("👤 Corpos")

    corpos = st.file_uploader(
        "Enviar Corpos",
        type=["mp4", "mov"],
        accept_multiple_files=True,
        key="corpos"
    )

with col3:

    st.subheader("📢 CTAs")

    ctas = st.file_uploader(
        "Enviar CTAs",
        type=["mp4", "mov"],
        accept_multiple_files=True,
        key="ctas"
    )

st.divider()

qtd_ganchos = len(ganchos)
qtd_corpos = len(corpos)
qtd_ctas = len(ctas)

total = qtd_ganchos * qtd_corpos * qtd_ctas

st.info(
    f"🎬 {qtd_ganchos} Gancho(s) × "
    f"{qtd_corpos} Corpo(s) × "
    f"{qtd_ctas} CTA(s) = "
    f"{total} vídeo(s)"
)


def salvar_upload(arquivo, pasta, nome):

    caminho = os.path.join(pasta, nome)

    with open(caminho, "wb") as f:
        f.write(arquivo.getbuffer())

    return caminho


def juntar_videos(gancho, corpo, cta, saida):

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    pasta = tempfile.mkdtemp()

    arquivos = []

    for numero, arquivo in enumerate(
        [gancho, corpo, cta],
        start=1
    ):

        caminho = salvar_upload(
            arquivo,
            pasta,
            f"parte_{numero}.mp4"
        )

        arquivos.append(caminho)

    lista = os.path.join(
        pasta,
        "lista.txt"
    )

    with open(lista, "w", encoding="utf-8") as f:

        for arquivo in arquivos:

            caminho_abs = os.path.abspath(
                arquivo
            ).replace("\\", "/")

            f.write(
                f"file '{caminho_abs}'\n"
            )

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

        saida
    ]

    resultado = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if resultado.returncode != 0:

        raise Exception(
            resultado.stderr[-3000:]
        )

    return saida


if ganchos and corpos and ctas:

    st.divider()

    st.subheader("🚀 Geração")

    if st.button(
        "🚀 GERAR VÍDEOS",
        use_container_width=True
    ):

        combinacoes = list(
            itertools.product(
                ganchos,
                corpos,
                ctas
            )
        )

        st.write(
            f"Serão gerados {len(combinacoes)} vídeo(s)."
        )

        pasta_saida = tempfile.mkdtemp()

        videos_gerados = []

        barra = st.progress(0)

        status = st.empty()

        for numero, (gancho, corpo, cta) in enumerate(
            combinacoes,
            start=1
        ):

            nome_saida = os.path.join(
                pasta_saida,
                f"{numero:03d}.mp4"
            )

            status.write(
                f"🎬 Gerando vídeo {numero} "
                f"de {len(combinacoes)}..."
            )

            try:

                juntar_videos(
                    gancho,
                    corpo,
                    cta,
                    nome_saida
                )

                videos_gerados.append(
                    nome_saida
                )

                barra.progress(
                    numero / len(combinacoes)
                )

            except Exception as erro:

                st.error(
                    f"Erro no vídeo {numero}: "
                    f"{erro}"
                )

                break

        if videos_gerados:

            status.success(
                f"✅ {len(videos_gerados)} vídeo(s) gerado(s)!"
            )

            zip_path = os.path.join(
                pasta_saida,
                "videos_gerados.zip"
            )

            with zipfile.ZipFile(
                zip_path,
                "w",
                zipfile.ZIP_DEFLATED
            ) as zipf:

                for video in videos_gerados:

                    zipf.write(
                        video,
                        os.path.basename(video)
                    )

            st.download_button(
                label="📦 BAIXAR TODOS OS VÍDEOS",
                data=open(
                    zip_path,
                    "rb"
                ).read(),
                file_name="videos_gerados.zip",
                mime="application/zip",
                use_container_width=True
            )

            st.success(
                "🎉 Processo concluído!"
            )

else:

    st.warning(
        "Envie pelo menos 1 Gancho, "
        "1 Corpo e 1 CTA."
    )
