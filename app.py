import streamlit as st
import itertools
import os
import tempfile
import subprocess
import zipfile
import shutil
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
# ESTILO
# ============================================================

st.markdown("""
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
    font-size: 25px;
    font-weight: 700;
}

.result-box {
    padding: 18px;
    border-radius: 12px;
    background: #172b42;
    margin-top: 15px;
}

.success-box {
    padding: 18px;
    border-radius: 12px;
    background: #123c29;
    margin-top: 15px;
}

.warning-box {
    padding: 18px;
    border-radius: 12px;
    background: #414514;
    margin-top: 15px;
}

.footer {
    color: #777;
    text-align: center;
    margin-top: 50px;
    padding: 20px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# TÍTULO
# ============================================================

st.markdown(
    '<div class="main-title">🎬 AI Creative Engine</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">Gerador automático de criativos para vídeos</div>',
    unsafe_allow_html=True
)


# ============================================================
# FUNÇÕES
# ============================================================

def get_ffmpeg():
   
