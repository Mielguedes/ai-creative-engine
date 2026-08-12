import streamlit as st
import itertools
import os
import json
import subprocess
import shutil
import zipfile
import re
import random
import requests
from faster_whisper import WhisperModel

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="AI Creative Engine Local",
    layout="wide"
)

# ============================================================
# SUPABASE / LOGIN
# ============================================================
def normalizar_supabase_url(url):
    url = (url or "").strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[:-7]
    return url.rstrip("/")

try:
    SUPABASE_URL = normalizar_supabase_url(st.secrets["SUPABASE_URL"])
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("❌ Configure SUPABASE_URL e SUPABASE_KEY em Settings → Secrets.")
    st.stop()

def supabase_auth(email, senha):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    resposta = requests.post(
        url,
        headers=headers,
        json={"email": email.strip(), "password": senha},
        timeout=20,
    )
    try:
        dados = resposta.json()
    except Exception:
        dados = {}

    if resposta.status_code != 200:
        mensagem = dados.get("error_description") or dados.get("msg") or "E-mail ou senha incorretos."
        return None, mensagem

    return dados, None

def buscar_perfil(access_token, email):
    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {access_token}",
    }
    params = {
        "select": "id,email,nome,ativo,plano",
        "email": f"eq.{email}",
        "limit": "1",
    }
    resposta = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20,
    )

    if resposta.status_code != 200:
        return None, resposta.text

    registros = resposta.json()
    if not registros:
        return None, "Perfil não encontrado na tabela profiles."

    return registros[0], None

def fazer_logout():
    for chave in [
        "auth_ok",
        "access_token",
        "refresh_token",
        "user_id",
        "user_email",
        "user_name",
        "user_plano",
        "user_ativo",
    ]:
        st.session_state.pop(chave, None)
    st.rerun()

def tela_login():
    st.markdown(
        """
        <style>
        .login-title {
            font-size: 42px;
            font-weight: 800;
            color: #183153;
            margin-bottom: 4px;
        }
        .login-subtitle {
            color: #7b8190;
            font-size: 15px;
            margin-bottom: 24px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="login-title">🔐 AI Creative Engine</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="login-subtitle">Entre para acessar o gerador de vídeos.</div>',
        unsafe_allow_html=True,
    )

    email = st.text_input("📧 E-mail", key="login_email")
    senha = st.text_input("🔑 Senha", type="password", key="login_password")

    if st.button(
        "🚀 ENTRAR",
        type="primary",
        use_container_width=True,
        key="btn_login",
    ):
        if not email.strip() or not senha:
            st.error("❌ Informe e-mail e senha.")
            return

        with st.spinner("Entrando..."):
            dados, erro = supabase_auth(email, senha)

        if erro:
            st.error(f"❌ {erro}")
            return

        access_token = dados.get("access_token")
        refresh_token = dados.get("refresh_token")
        user = dados.get("user") or {}
        user_id = user.get("id")

        if not access_token or not user_id:
            st.error("❌ O Supabase não retornou os dados de autenticação.")
            return

        perfil, erro_perfil = buscar_perfil(access_token, email.strip())

        if erro_perfil:
            st.error(f"❌ Não foi possível carregar seu perfil: {erro_perfil}")
            return

        if not bool(perfil.get("ativo", True)):
            st.error("🔒 Este usuário está desativado.")
            return

        st.session_state["auth_ok"] = True
        st.session_state["access_token"] = access_token
        st.session_state["refresh_token"] = refresh_token
        st.session_state["user_id"] = user_id
        st.session_state["user_email"] = email.strip()
        st.session_state["user_name"] = perfil.get("nome") or email.strip()
        st.session_state["user_plano"] = (perfil.get("plano") or "user").lower()
        st.session_state["user_ativo"] = bool(perfil.get("ativo", True))

        st.rerun()

if not st.session_state.get("auth_ok", False):
    tela_login()
    st.stop()

# ============================================================
# DADOS DO USUÁRIO LOGADO
# ============================================================
USER_ID = st.session_state["user_id"]
USER_EMAIL = st.session_state["user_email"]
USER_NAME = st.session_state.get("user_name") or USER_EMAIL
USER_PLANO = st.session_state.get("user_plano", "user").lower()
IS_ADMIN = USER_PLANO == "admin"

# ============================================================
# ESTRUTURA DE PASTAS E PROJETOS
# Cada usuário possui sua própria pasta pelo UID do Supabase.
# ============================================================
BASE_DIR = os.path.abspath(
    os.path.join("projetos", USER_ID)
)
os.makedirs(BASE_DIR, exist_ok=True)

def listar_projetos():
    return sorted(
        [
            d
            for d in os.listdir(BASE_DIR)
            if os.path.isdir(os.path.join(BASE_DIR, d))
        ]
    )

# ============================================================
# PAINEL ADMINISTRATIVO
# ============================================================
def buscar_todos_perfis_admin():
    if not IS_ADMIN:
        return None, "Acesso restrito ao administrador."

    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {st.session_state['access_token']}",
    }
    params = {
        "select": "id,email,nome,ativo,plano,created_at",
        "order": "created_at.desc",
    }

    resposta = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=20,
    )

    if resposta.status_code != 200:
        return None, resposta.text

    return resposta.json(), None

def atualizar_perfil_admin(profile_id, ativo, plano):
    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {st.session_state['access_token']}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    params = {"id": f"eq.{profile_id}"}
    dados = {
        "ativo": bool(ativo),
        "plano": plano,
    }

    resposta = requests.patch(
        url,
        headers=headers,
        params=params,
        json=dados,
        timeout=20,
    )
    return resposta.status_code in (200, 204), resposta.text

def painel_admin():
    if not IS_ADMIN:
        return

    st.sidebar.divider()
    with st.sidebar.expander("👑 Painel Administrativo", expanded=False):
        st.markdown("**Controle de usuários**")

        perfis, erro = buscar_todos_perfis_admin()

        if erro:
            st.warning(
                "⚠️ O painel administrativo precisa de uma policy "
                "para o admin consultar todos os perfis."
            )
            st.caption("Configure a policy no Supabase e recarregue o app.")
            return

        if not perfis:
            st.info("Nenhum usuário encontrado.")
            return

        for perfil in perfis:
            email = perfil.get("email") or ""
            nome = perfil.get("nome") or email
            plano_atual = (perfil.get("plano") or "user").lower()
            ativo_atual = bool(perfil.get("ativo", True))
            profile_id = perfil.get("id")

            st.markdown(f"**👤 {nome}**")
            st.caption(email)

            novo_plano = st.selectbox(
                "Plano",
                ["user", "admin"],
                index=0 if plano_atual != "admin" else 1,
                key=f"admin_plano_{profile_id}",
            )

            novo_ativo = st.checkbox(
                "Usuário ativo",
                value=ativo_atual,
                key=f"admin_ativo_{profile_id}",
            )

            if st.button(
                "💾 Salvar",
                key=f"admin_salvar_{profile_id}",
                use_container_width=True,
            ):
                ok, detalhe = atualizar_perfil_admin(
                    profile_id,
                    novo_ativo,
                    novo_plano,
                )

                if ok:
                    st.success("Salvo!")
                    if profile_id == st.session_state.get("user_id"):
                        st.session_state["user_plano"] = novo_plano
                        st.session_state["user_ativo"] = novo_ativo
                    st.rerun()
                else:
                    st.error(f"Erro ao salvar: {detalhe}")

            st.divider()

# ============================================================
# SIDEBAR: GERENCIADOR DE PROJETOS
# ============================================================
st.sidebar.title("📁 Projetos")
st.sidebar.caption(f"👤 {USER_NAME}")
st.sidebar.caption(USER_EMAIL)

if IS_ADMIN:
    st.sidebar.success("👑 Administrador")
else:
    st.sidebar.info("👤 Usuário")

if st.sidebar.button(
    "🚪 Sair",
    use_container_width=True,
    key="btn_logout",
):
    fazer_logout()

painel_admin()

novo_proj_nome = st.sidebar.text_input(
    "Novo Projeto:",
    key="novo_projeto_nome",
)

if st.sidebar.button(
    "➕ Criar Projeto",
    use_container_width=True,
    key="criar_projeto",
):
    if novo_proj_nome.strip():
        nome_limpo = re.sub(
            r'[^\w\s-]',
            '',
            novo_proj_nome.strip()
        ).replace(" ", "_")

        if not nome_limpo:
            st.sidebar.error("Nome de projeto inválido.")
        else:
            proj_path = os.path.join(
                BASE_DIR,
                nome_limpo
            )

            os.makedirs(
                os.path.join(proj_path, "ganchos"),
                exist_ok=True
            )
            os.makedirs(
                os.path.join(proj_path, "corpos"),
                exist_ok=True
            )
            os.makedirs(
                os.path.join(proj_path, "ctas"),
                exist_ok=True
            )
            os.makedirs(
                os.path.join(proj_path, "output"),
                exist_ok=True
            )

            st.sidebar.success(
                f"Projeto '{nome_limpo}' criado!"
            )
            st.rerun()

st.sidebar.divider()

projetos_disponiveis = listar_projetos()

if not projetos_disponiveis:
    st.warning(
        "⚠️ Nenhum projeto encontrado. "
        "Crie um projeto no menu lateral para começar!"
    )
    st.stop()

projeto_atual = st.sidebar.selectbox(
    "Selecione o Projeto Ativo:",
    projetos_disponiveis,
    key="projeto_ativo",
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

for pasta in [
    PATH_GANCHOS,
    PATH_CORPOS,
    PATH_CTAS,
    PATH_OUTPUT,
]:
    os.makedirs(pasta, exist_ok=True)

st.sidebar.divider()

if st.sidebar.button(
    "🗑️ Deletar Projeto Atual",
    type="primary",
    use_container_width=True,
    key="deletar_projeto",
):
    shutil.rmtree(PROJ_PATH, ignore_errors=True)
    st.sidebar.error(
        f"Projeto '{projeto_atual}' foi apagado!"
    )
    st.rerun()


# --- FUNÇÃO: CÁLCULO DE SCORE LOCAL ---
def calcular_score_local(texto):
    if not texto.strip(): return 75
    palavras = len(texto.split())
    score = 70
    if 3 <= palavras <= 12: score += 15
    if bool(re.search(r'\d', texto)): score += 8
    if '?' in texto or '!' in texto: score += 7
    return min(98, max(65, score))

# --- FUNÇÃO: GERAR LEGENDA DO HOOK INCLINADO (.ASS NO TOPO) ---
def gerar_hook_ass(texto_hook, caminho_saida_ass, posicao_y=200, tamanho_fonte=100):
    borda_padding = max(15, int(tamanho_fonte * 0.25))
    
    estilo_ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookStyle,The Bold Font,{tamanho_fonte},&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,{borda_padding},0,8,30,30,{posicao_y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:04.50,HookStyle,,0,0,0,,{{\\frz-2.5}}{texto_hook}
Dialogue: 0,0:00:04.50,0:00:05.00,HookStyle,,0,0,0,,{{\\frz-2.5\\fad(0,500)}}{texto_hook}
"""
    with open(caminho_saida_ass, "w", encoding="utf-8") as f:
        f.write(estilo_ass)

# --- FUNÇÃO: LEGENDA WORD POP / ACTIVE HIGHLIGHT ---
def gerar_legenda_ass(caminho_video, caminho_saida_ass, posicao_v=450, tamanho_fonte=80):
    if not os.path.exists(caminho_video):
        return False
    try:
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(caminho_video, word_timestamps=True, language="pt")

        tamanho_destaque = int(tamanho_fonte * 1.30)

        estilo_ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,The Bold Font,{tamanho_fonte},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,2,2,30,30,{posicao_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        linhas = []
        def fmt(s):
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            return f"{int(h)}:{int(m):02d}:{s:05.2f}"

        for segment in segments:
            words = segment.words
            if not words: continue
            
            grupos = []
            grupo_atual = []
            tam_atual = 0
            
            for w in words:
                palavra_str = w.word.upper().strip()
                tam_necessario = tam_atual + (1 if tam_atual > 0 else 0) + len(palavra_str)
                
                if grupo_atual and tam_necessario > 18:
                    grupos.append(grupo_atual)
                    grupo_atual = [w]
                    tam_atual = len(palavra_str)
                else:
                    grupo_atual.append(w)
                    tam_atual = tam_necessario
            if grupo_atual:
                grupos.append(grupo_atual)

            for grupo in grupos:
                for i_destaque, w_foco in enumerate(grupo):
                    start_time = w_foco.start
                    end_time = w_foco.end

                    texto_linha = []
                    for j_palavra, w_item in enumerate(grupo):
                        palavra_txt = w_item.word.upper().strip()
                        if i_destaque == j_palavra:
                            texto_linha.append(f"{{\\fs{tamanho_destaque}\\c&H0000FFFF\\b1}}{palavra_txt}{{\\r}}")
                        else:
                            texto_linha.append(f"{{\\fs{tamanho_fonte}\\c&H00FFFFFF\\b1}}{palavra_txt}{{\\r}}")

                    frase_formatada = " ".join(texto_linha)
                    linha = f"Dialogue: 0,{fmt(start_time)},{fmt(end_time)},Hormozi,,0,0,0,,{frase_formatada}\n"
                    linhas.append(linha)

        with open(caminho_saida_ass, "w", encoding="utf-8") as f:
            f.writelines([estilo_ass] + linhas)
        return True
    except Exception as e:
        print(f"[ERRO WHISPER]: {e}")
        return False

# --- FUNÇÃO: PREPARAR/TRATAR VÍDEO INDIVIDUAL DE BLOCO ---
def processar_bloco_individual(caminho_entrada, caminho_saida, encoder_video="libx264", deve_espelhar=False):
    filtros = []
    if deve_espelhar:
        filtros.append("hflip")
    
    if filtros:
        cmd = f'ffmpeg -y -i "{caminho_entrada}" -vf "{",".join(filtros)}" -c:v {encoder_video} -pix_fmt yuv420p -c:a copy "{caminho_saida}"'
        subprocess.run(cmd, shell=True)
    else:
        shutil.copyfile(caminho_entrada, caminho_saida)

def criar_zip_projeto(pasta_output, caminho_zip):
    with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(pasta_output):
            for file in files:
                if file.endswith('.mp4'):
                    zipf.write(os.path.join(root, file), arcname=file)

def limpar_pasta(caminho_pasta):
    for f in os.listdir(caminho_pasta):
        fp = os.path.join(caminho_pasta, f)
        if os.path.isfile(fp):
            os.remove(fp)

# --- HEADER PRINCIPAL ---
st.title(f"🎬 AI Creative Engine — {projeto_atual}")
st.caption("Multiplicador Modular de Vídeos Localhost (Estável & Seguro)")

st.divider()

def salvar_arquivos(files, destino):
    for f in files:
        nome_limpo = re.sub(r'[^\w\.-]', '_', f.name)
        path = os.path.join(destino, nome_limpo)
        with open(path, "wb") as buffer:
            buffer.write(f.getbuffer())

# --- 1. UPLOAD E LIMPEZA DOS BLOCOS DE VÍDEO ---
st.subheader("1. Gerenciamento dos Blocos de Vídeo")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 🪝 Ganchos")
    files_h = st.file_uploader("Subir Ganchos", accept_multiple_files=True, type=["mp4", "mov"], key="u_h")
    if files_h: salvar_arquivos(files_h, PATH_GANCHOS)
    arquivos_h = [f for f in os.listdir(PATH_GANCHOS) if f.endswith(('mp4', 'mov'))]
    if len(arquivos_h) < 1: st.warning("⚠️ Nenhum vídeo")
    else: st.success(f"✅ {len(arquivos_h)} Ganchos")
    for f in arquivos_h: st.code(f, language="text")
    if arquivos_h and st.button("🗑️ Limpar Ganchos", key="del_h"):
        limpar_pasta(PATH_GANCHOS)
        st.rerun()

with col2:
    st.markdown("### 📹 Corpos")
    files_m = st.file_uploader("Subir Corpos", accept_multiple_files=True, type=["mp4", "mov"], key="u_m")
    if files_m: salvar_arquivos(files_m, PATH_CORPOS)
    arquivos_m = [f for f in os.listdir(PATH_CORPOS) if f.endswith(('mp4', 'mov'))]
    if len(arquivos_m) < 1: st.warning("⚠️ Nenhum vídeo")
    else: st.success(f"✅ {len(arquivos_m)} Corpos")
    for f in arquivos_m: st.code(f, language="text")
    if arquivos_m and st.button("🗑️ Limpar Corpos", key="del_m"):
        limpar_pasta(PATH_CORPOS)
        st.rerun()

with col3:
    st.markdown("### 📢 CTAs")
    files_c = st.file_uploader("Subir CTAs", accept_multiple_files=True, type=["mp4", "mov"], key="u_c")
    if files_c: salvar_arquivos(files_c, PATH_CTAS)
    arquivos_c = [f for f in os.listdir(PATH_CTAS) if f.endswith(('mp4', 'mov'))]
    if len(arquivos_c) < 1: st.warning("⚠️ Nenhum vídeo")
    else: st.success(f"✅ {len(arquivos_c)} CTAs")
    for f in arquivos_c: st.code(f, language="text")
    if arquivos_c and st.button("🗑️ Limpar CTAs", key="del_c"):
        limpar_pasta(PATH_CTAS)
        st.rerun()

total_variacoes = len(arquivos_h) * len(arquivos_m) * len(arquivos_c)
if total_variacoes > 0:
    st.info(f"📊 Combinação base: **{len(arquivos_h)}** Gancho(s) × **{len(arquivos_m)}** Corpo(s) × **{len(arquivos_c)}** CTA(s) = **{total_variacoes} Vídeo(s) Resultante(s)**!")

st.divider()

# --- 2. OPÇÕES DE EDIÇÃO EM LINHA ---
st.subheader("2. Estilização & Modificadores")

# SELEÇÃO DE HARDWARE (GPU / CPU)
st.markdown("#### ⚡ Aceleração por Hardware")
tipo_gpu = st.selectbox(
    "Escolha a Renderização (Se congelar no seu PC, troque para CPU Padrão):",
    ["CPU Padrão (libx264) - Mais Estável", "NVIDIA (h264_nvenc)", "AMD (h264_amf)", "Intel (h264_qsv)"]
)

if "NVIDIA" in tipo_gpu:
    encoder_escolhido = "h264_nvenc"
elif "AMD" in tipo_gpu:
    encoder_escolhido = "h264_amf"
elif "Intel" in tipo_gpu:
    encoder_escolhido = "h264_qsv"
else:
    encoder_escolhido = "libx264"

st.divider()

st.markdown("#### 🛡️ Modificadores Anti-Duplicidade Agressivos (Sem Alterar Voz)")
col_e1, col_e2 = st.columns(2)
with col_e1:
    auto_ultra_anti_dup = st.checkbox("Modo Ultra Anti-Duplicidade (Brilho/Contraste, Pan/Crop Estável)", value=True)
with col_e2:
    espelhar_blocos_rand = st.checkbox("Espelhamento Aleatório por Bloco (Gancho/Corpo/CTA)", value=True)

st.divider()

st.markdown("#### 📌 Hooks Alternativos (Texto Inclinado no topo)")
hook_ativo = st.checkbox("Ativar Hook no topo do vídeo", value=True)

if hook_ativo:
    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
    with col_h1:
        texto_manchete = st.text_area(
            "Escreva frases de Hook (Uma frase por linha para ser usada nas variações):",
            value="",
            placeholder="Digite suas frases aqui (uma por linha)...",
            height=120
        )
    with col_h2:
        posicao_hook_y = st.number_input("Posição do Hook (px do topo):", min_value=10, max_value=1200, value=200, step=10)
    with col_h3:
        tamanho_hook = st.number_input("Tamanho da Fonte do Hook:", min_value=20, max_value=250, value=100, step=5)
else:
    texto_manchete = ""
    posicao_hook_y = 200
    tamanho_hook = 100

st.divider()

st.markdown("#### 🗣️ Legendas Automáticas (Word Pop Zoom + Destaque Amarelo)")
legenda_ativa = st.checkbox("Ativar Legendas Automáticas no Vídeo", value=True)

if legenda_ativa:
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        posicao_legenda_v = st.slider("Altura da Legenda na Tela (px a partir de baixo):", min_value=100, max_value=1200, value=450, step=20)
    with col_l2:
        tamanho_legenda = st.number_input("Tamanho da Fonte da Legenda:", min_value=40, max_value=150, value=80, step=5)
else:
    posicao_legenda_v = 450
    tamanho_legenda = 80

st.divider()

# --- BOTÃO DE PROCESSAMENTO ---
if st.button("🚀 Multiplicar e Gerar Todos os Vídeos", type="primary", use_container_width=True):
    list_h = [os.path.join(PATH_GANCHOS, f) for f in os.listdir(PATH_GANCHOS) if f.endswith(('mp4', 'mov'))]
    list_m = [os.path.join(PATH_CORPOS, f) for f in os.listdir(PATH_CORPOS) if f.endswith(('mp4', 'mov'))]
    list_c = [os.path.join(PATH_CTAS, f) for f in os.listdir(PATH_CTAS) if f.endswith(('mp4', 'mov'))]

    if len(list_h) < 1 or len(list_m) < 1 or len(list_c) < 1:
        st.error("Adicione pelo menos 1 vídeo em cada uma das 3 colunas para gerar!")
    else:
        lista_hooks = [linha.strip().upper() for linha in texto_manchete.split('\n') if linha.strip()]

        combos = list(itertools.product(list_h, list_m, list_c))
        st.success(f"🔥 Gerando {len(combos)} vídeo(s) com Encoder [{encoder_escolhido}]...")
        prog = st.progress(0)

        for idx, (h, m, c) in enumerate(combos):
            print(f"\n=================== PROCESSANDO VARIAÇÃO {idx+1}/{len(combos)} ===================")
            out_final = os.path.abspath(os.path.join(PATH_OUTPUT, f"video_final_{idx+1}.mp4"))
            
            # Arquivos temporários dos blocos com espelhamento aleatório
            h_tmp = os.path.abspath(os.path.join(PROJ_PATH, f"tmp_h_{idx}.mp4"))
            m_tmp = os.path.abspath(os.path.join(PROJ_PATH, f"tmp_m_{idx}.mp4"))
            c_tmp = os.path.abspath(os.path.join(PROJ_PATH, f"tmp_c_{idx}.mp4"))

            # Sorteio de espelhamento por bloco
            esp_h = random.choice([True, False]) if espelhar_blocos_rand else False
            esp_m = random.choice([True, False]) if espelhar_blocos_rand else False
            esp_c = random.choice([True, False]) if espelhar_blocos_rand else False

            processar_bloco_individual(h, h_tmp, encoder_escolhido, esp_h)
            processar_bloco_individual(m, m_tmp, encoder_escolhido, esp_m)
            processar_bloco_individual(c, c_tmp, encoder_escolhido, esp_c)

            concat_list = os.path.abspath(os.path.join(PROJ_PATH, f"list_{idx}.txt"))
            with open(concat_list, "w", encoding="utf-8") as f:
                f.write(f"file '{h_tmp}'\nfile '{m_tmp}'\nfile '{c_tmp}'\n")

            # 1. PASSO 1: Concatenação segura com re-encodamento
            cmd_concat = f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" -c:v {encoder_escolhido} -pix_fmt yuv420p -c:a aac "{out_final}"'
            subprocess.run(cmd_concat, shell=True)

            # Remover blocos temporários
            for t_b in [h_tmp, m_tmp, c_tmp]:
                if os.path.exists(t_b): os.remove(t_b)

            if not os.path.exists(out_final):
                st.error(f"Erro ao concatenar variação {idx+1}. Mude para 'CPU Padrão' nas opções!")
                continue

            # 2. PASSO 2: Legendas Word Pop ASS
            ass_file = os.path.abspath(os.path.join(PROJ_PATH, f"temp_{idx}.ass"))
            if legenda_ativa:
                has_leg = gerar_legenda_ass(out_final, ass_file, posicao_v=posicao_legenda_v, tamanho_fonte=tamanho_legenda)
                if has_leg and os.path.exists(ass_file):
                    temp_leg = os.path.abspath(os.path.join(PROJ_PATH, f"temp_leg_{idx}.mp4"))
                    ass_path_clean = ass_file.replace("\\", "/").replace(":", "\\:")
                    cmd_leg = f'ffmpeg -y -i "{out_final}" -vf "subtitles=\'{ass_path_clean}\'" -c:v {encoder_escolhido} -pix_fmt yuv420p -c:a copy "{temp_leg}"'
                    subprocess.run(cmd_leg, shell=True)
                    if os.path.exists(temp_leg):
                        shutil.move(temp_leg, out_final)

            # 3. PASSO 3: Hook Inclinado no Topo
            if hook_ativo and lista_hooks:
                hook_selecionado = lista_hooks[idx % len(lista_hooks)]
                hook_ass_file = os.path.abspath(os.path.join(PROJ_PATH, f"temp_hook_{idx}.ass"))
                gerar_hook_ass(hook_selecionado, hook_ass_file, posicao_y=posicao_hook_y, tamanho_fonte=tamanho_hook)
                
                if os.path.exists(hook_ass_file):
                    temp_hk = os.path.abspath(os.path.join(PROJ_PATH, f"temp_hk_{idx}.mp4"))
                    hook_path_clean = hook_ass_file.replace("\\", "/").replace(":", "\\:")
                    cmd_hk = f'ffmpeg -y -i "{out_final}" -vf "subtitles=\'{hook_path_clean}\'" -c:v {encoder_escolhido} -pix_fmt yuv420p -c:a copy "{temp_hk}"'
                    subprocess.run(cmd_hk, shell=True)
                    if os.path.exists(temp_hk):
                        shutil.move(temp_hk, out_final)
                    if os.path.exists(hook_ass_file): os.remove(hook_ass_file)

            # 4. PASSO 4: MODIFICADORES VISUAIS ESTÁVEIS
            if auto_ultra_anti_dup:
                filtros_v = []

                # Pan & Scan seguro (Redimensiona sempre para 1080x1920 no final)
                factor = round(random.uniform(0.85, 0.95), 2)
                filtros_v.append(f"crop=iw*{factor}:ih*{factor}")
                filtros_v.append("scale=1080:1920")

                # GRADAÇÃO DINÂMICA DE COR ESTÁVEL
                color_preset = random.choice([
                    "eq=brightness=0.02:contrast=1.05:saturation=1.04",
                    "eq=brightness=-0.015:contrast=1.07:saturation=0.96",
                    "eq=brightness=0.01:contrast=1.03:saturation=1.08",
                    "eq=brightness=-0.005:contrast=1.06:saturation=1.00",
                    "eq=brightness=0.025:contrast=1.02:saturation=0.95",
                    "eq=brightness=-0.02:contrast=1.04:saturation=1.05",
                ])
                filtros_v.append(color_preset)

                temp_filt = os.path.abspath(os.path.join(PROJ_PATH, f"temp_filt_{idx}.mp4"))
                
                cmd_v_str = f'-vf "{",".join(filtros_v)}"'

                cmd_filt = (
                    f'ffmpeg -y -i "{out_final}" {cmd_v_str} -c:v {encoder_escolhido} -pix_fmt yuv420p -c:a copy '
                    f'-metadata title="" -metadata comment="" -metadata encoder="Apple iOS Camera 17.4.1" '
                    f'"{temp_filt}"'
                )
                print(f"Aplicando Modulação Visual Anti-Duplicidade: {cmd_filt}")
                subprocess.run(cmd_filt, shell=True)

                if os.path.exists(temp_filt):
                    shutil.move(temp_filt, out_final)

            # Limpeza de temporários
            for t_file in [concat_list, ass_file]:
                if os.path.exists(t_file): os.remove(t_file)

            prog.progress((idx + 1) / len(combos))

        st.balloons()
        st.success(f"🎉 {len(combos)} vídeo(s) gerados com sucesso!")
        st.rerun()

st.divider()

# --- 3. SEÇÃO DE VÍDEOS PRONTOS E BAIXAR TUDO INCLUSO ---
st.subheader("3. Vídeos Prontos & Downloads")

videos_gerados = sorted([f for f in os.listdir(PATH_OUTPUT) if f.endswith('.mp4')])

if not videos_gerados:
    st.info("ℹ️ Nenhum vídeo gerado ainda. Suba os arquivos nas colunas acima e clique no botão para gerar!")
else:
    zip_path = os.path.join(PROJ_PATH, f"{projeto_atual}_todos_os_videos.zip")
    criar_zip_projeto(PATH_OUTPUT, zip_path)
    
    with open(zip_path, "rb") as fp:
        st.download_button(
            label=f"📦 BAIXAR TODOS OS {len(videos_gerados)} VÍDEOS (.ZIP)",
            data=fp,
            file_name=f"{projeto_atual}_videos.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )
    
    st.write("")
    st.write("**Galeria de Vídeos Prontos:**")
    
    cols_grid = st.columns(3)
    score_geral = calcular_score_local(texto_manchete)
    
    for idx, vid_file in enumerate(videos_gerados):
        col_target = cols_grid[idx % 3]
        vid_path = os.path.join(PATH_OUTPUT, vid_file)
        
        with col_target:
            with st.container(border=True):
                st.markdown(f"**📹 {vid_file}**")
                st.video(vid_path)
                
                score_variacao = min(100, max(60, score_geral + (idx % 5) - 2))
                st.metric(label="🎯 Hook Score", value=f"{score_variacao} / 100")
                
                with open(vid_path, "rb") as f_vid:
                    st.download_button(
                        label="⬇️ Baixar Este Vídeo",
                        data=f_vid,
                        file_name=vid_file,
                        mime="video/mp4",
                        use_container_width=True,
                        key=f"btn_dl_{idx}"
                    )
