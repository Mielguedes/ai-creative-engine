"""Ponto de entrada do Streamlit.

A aplicação principal foi migrada para app_com_login.py, que concentra
login Supabase, controle de acesso e o multiplicador de vídeos.
Este arquivo permanece como compatibilidade com o caminho app.py já
configurado no Streamlit Cloud.
"""

from app_com_login import *  # noqa: F401,F403
