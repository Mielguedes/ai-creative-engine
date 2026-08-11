import streamlit as st
import itertools

st.set_page_config(
    page_title="AI Creative Engine",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 AI Creative Engine")
st.caption("Gerador de combinações para vídeos")

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
        accept_multiple_files=True
    )

with col2:
    st.subheader("👤 Corpos")

    corpos = st.file_uploader(
        "Enviar Corpos",
        type=["mp4", "mov"],
        accept_multiple_files=True
    )

with col3:
    st.subheader("📢 CTAs")

    ctas = st.file_uploader(
        "Enviar CTAs",
        type=["mp4", "mov"],
        accept_multiple_files=True
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

if ganchos and corpos and ctas:

    if st.button(
        "🚀 GERAR COMBINAÇÕES",
        use_container_width=True
    ):

        combinacoes = list(
            itertools.product(
                ganchos,
                corpos,
                ctas
            )
        )

        st.success(
            f"✅ {len(combinacoes)} combinações criadas!"
        )

        for numero, (gancho, corpo, cta) in enumerate(
            combinacoes,
            start=1
        ):

            st.write(
                f"🎬 {numero:03d} — "
                f"{gancho.name} + "
                f"{corpo.name} + "
                f"{cta.name}"
            )

else:

    st.warning(
        "Envie pelo menos 1 Gancho, 1 Corpo e 1 CTA."
        )
