import streamlit as st
import itertools
import os
import json
import subprocess
import shutil
import zipfile
import re
import random
from faster_whisper import WhisperModel

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
st.set_page_config(page_title="AI Creative Engine Local", layout="wide")

# --- ESTRUTURA DE PASTAS E PROJETOS ---
BASE_DIR = os.path.abspath("projetos")
os.makedirs(BASE_DIR, exist_ok=True)

def listar_projetos():
    return [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]

# --- SIDEBAR: GERENCIADOR DE PROJETOS ---
st.sidebar.title("📁 Projetos")

novo_proj_nome = st.sidebar.text_input("Novo Projeto:")
if st.sidebar.button("➕ Criar Projeto", use_container_width=True):
    if novo_proj_nome.strip():
        nome_limpo = re.sub(r'[^\w\s-]', '', novo_proj_nome.strip()).replace(" ", "_")
        proj_path = os.path.join(BASE_DIR, nome_limpo)
        os.makedirs(os.path.join(proj_path, "ganchos"), exist_ok=True)
        os.makedirs(os.path.join(proj_path, "corpos"), exist_ok=True)
        os.makedirs(os.path.join(proj_path, "ctas"), exist_ok=True)
        os.makedirs(os.path.join(proj_path, "output"), exist_ok=True)
        st.sidebar.success(f"Projeto '{nome_limpo}' criado!")
        st.rerun()

st.sidebar.divider()

projetos_disponiveis = listar_projetos()
if not projetos_disponiveis:
    st.warning("⚠️ Nenhum projeto encontrado. Crie um projeto no menu lateral para começar!")
    st.stop()

projeto_atual = st.sidebar.selectbox("Selecione o Projeto Ativo:", projetos_disponiveis)
PROJ_PATH = os.path.join(BASE_DIR, projeto_atual)

PATH_GANCHOS = os.path.join(PROJ_PATH, "ganchos")
PATH_CORPOS = os.path.join(PROJ_PATH, "corpos")
PATH_CTAS = os.path.join(PROJ_PATH, "ctas")
PATH_OUTPUT = os.path.join(PROJ_PATH, "output")

st.sidebar.divider()

if st.sidebar.button("🗑️ Deletar Projeto Atual", type="primary", use_container_width=True):
    shutil.rmtree(PROJ_PATH)
    st.sidebar.error(f"Projeto '{projeto_atual}' foi apagado!")
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
def executar_ffmpeg(cmd):
    """Executa FFmpeg e devolve sucesso + mensagem de erro."""
    try:
        resultado = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if resultado.returncode != 0:
            erro = (resultado.stderr or resultado.stdout or "Erro desconhecido").strip()
            return False, erro[-6000:]
        return True, ""
    except Exception as e:
        return False, str(e)


def video_tem_audio(caminho):
    """Verifica se o arquivo possui pelo menos uma faixa de áudio."""
    cmd = (
        f'ffprobe -v error -select_streams a:0 '
        f'-show_entries stream=index -of csv=p=0 "{caminho}"'
    )
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace"
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def processar_bloco_individual(
    caminho_entrada,
    caminho_saida,
    encoder_video="libx264",
    deve_espelhar=False
):
    """Normaliza cada bloco para 1080x1920, H.264 + AAC, pronto para concatenação."""

    filtros = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        "setsar=1"
    ]

    if deve_espelhar:
        filtros.insert(0, "hflip")

    vf = ",".join(filtros)

    # Se o bloco não tiver áudio, cria áudio silencioso com a mesma duração.
    if video_tem_audio(caminho_entrada):
        cmd = (
            f'ffmpeg -y -i "{caminho_entrada}" '
            f'-vf "{vf}" '
            f'-c:v {encoder_video} -preset fast -pix_fmt yuv420p '
            f'-c:a aac -ar 44100 -ac 2 '
            f'-movflags +faststart "{caminho_saida}"'
        )
    else:
        cmd = (
            f'ffmpeg -y -i "{caminho_entrada}" '
            f'-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 '
            f'-map 0:v:0 -map 1:a:0 '
            f'-vf "{vf}" '
            f'-c:v {encoder_video} -preset fast -pix_fmt yuv420p '
            f'-c:a aac -ar 44100 -ac 2 -shortest '
            f'-movflags +faststart "{caminho_saida}"'
        )

    return executar_ffmpeg(cmd)


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
    list_h = sorted([
        os.path.join(PATH_GANCHOS, f)
        for f in os.listdir(PATH_GANCHOS)
        if f.lower().endswith((".mp4", ".mov"))
    ])
    list_m = sorted([
        os.path.join(PATH_CORPOS, f)
        for f in os.listdir(PATH_CORPOS)
        if f.lower().endswith((".mp4", ".mov"))
    ])
    list_c = sorted([
        os.path.join(PATH_CTAS, f)
        for f in os.listdir(PATH_CTAS)
        if f.lower().endswith((".mp4", ".mov"))
    ])

    if not list_h or not list_m or not list_c:
        st.error("❌ Adicione pelo menos 1 vídeo em cada coluna: Gancho, Corpo e CTA.")
    else:
        lista_hooks = [
            linha.strip().upper()
            for linha in texto_manchete.split("\n")
            if linha.strip()
        ]

        combos = list(itertools.product(list_h, list_m, list_c))
        total = len(combos)

        st.info(
            f"🎬 **{len(list_h)} Hook(s) × {len(list_m)} Corpo(s) × "
            f"{len(list_c)} CTA(s) = {total} vídeo(s)**"
        )

        prog = st.progress(0)
        status = st.empty()
        erros = []
        gerados = 0

        # Remove MP4 antigos para a galeria representar somente esta geração.
        for antigo in os.listdir(PATH_OUTPUT):
            if antigo.lower().endswith(".mp4"):
                try:
                    os.remove(os.path.join(PATH_OUTPUT, antigo))
                except Exception:
                    pass

        for idx, (h, m, c) in enumerate(combos):
            numero = idx + 1
            status.write(f"⏳ Gerando **{numero}/{total}**...")

            out_final = os.path.abspath(
                os.path.join(PATH_OUTPUT, f"video_final_{numero:03d}.mp4")
            )

            h_tmp = os.path.abspath(os.path.join(PROJ_PATH, f"tmp_h_{idx}.mp4"))
            m_tmp = os.path.abspath(os.path.join(PROJ_PATH, f"tmp_m_{idx}.mp4"))
            c_tmp = os.path.abspath(os.path.join(PROJ_PATH, f"tmp_c_{idx}.mp4"))
            concat_list = os.path.abspath(os.path.join(PROJ_PATH, f"list_{idx}.txt"))

            try:
                esp_h = random.choice([True, False]) if espelhar_blocos_rand else False
                esp_m = random.choice([True, False]) if espelhar_blocos_rand else False
                esp_c = random.choice([True, False]) if espelhar_blocos_rand else False

                ok, erro = processar_bloco_individual(h, h_tmp, encoder_escolhido, esp_h)
                if not ok:
                    raise RuntimeError(f"HOOK: {erro}")

                ok, erro = processar_bloco_individual(m, m_tmp, encoder_escolhido, esp_m)
                if not ok:
                    raise RuntimeError(f"CORPO: {erro}")

                ok, erro = processar_bloco_individual(c, c_tmp, encoder_escolhido, esp_c)
                if not ok:
                    raise RuntimeError(f"CTA: {erro}")

                # Os três arquivos já estão normalizados para o mesmo padrão.
                with open(concat_list, "w", encoding="utf-8") as f:
                    for caminho in (h_tmp, m_tmp, c_tmp):
                        f.write(f"file '{caminho.replace(chr(92), '/')}'\n")

                cmd_concat = (
                    f'ffmpeg -y -f concat -safe 0 -i "{concat_list}" '
                    f'-c:v {encoder_escolhido} -preset fast -pix_fmt yuv420p '
                    f'-c:a aac -ar 44100 -ac 2 -movflags +faststart '
                    f'"{out_final}"'
                )

                ok, erro = executar_ffmpeg(cmd_concat)
                if not ok or not os.path.exists(out_final):
                    raise RuntimeError(f"CONCATENAÇÃO: {erro}")

                # Legendas automáticas
                ass_file = os.path.abspath(os.path.join(PROJ_PATH, f"temp_{idx}.ass"))

                if legenda_ativa:
                    has_leg = gerar_legenda_ass(
                        out_final,
                        ass_file,
                        posicao_v=posicao_legenda_v,
                        tamanho_fonte=tamanho_legenda
                    )

                    if has_leg and os.path.exists(ass_file):
                        temp_leg = os.path.abspath(
                            os.path.join(PROJ_PATH, f"temp_leg_{idx}.mp4")
                        )
                        ass_path_clean = ass_file.replace("\\", "/").replace(":", "\\:")

                        cmd_leg = (
                            f'ffmpeg -y -i "{out_final}" '
                            f'-vf "subtitles=\'{ass_path_clean}\'" '
                            f'-c:v {encoder_escolhido} -preset fast '
                            f'-pix_fmt yuv420p -c:a aac -ar 44100 -ac 2 '
                            f'-movflags +faststart "{temp_leg}"'
                        )

                        ok_leg, erro_leg = executar_ffmpeg(cmd_leg)

                        if ok_leg and os.path.exists(temp_leg):
                            os.replace(temp_leg, out_final)
                        elif not ok_leg:
                            st.warning(
                                f"⚠️ Legenda não aplicada no vídeo {numero}: {erro_leg}"
                            )

                # Hook escrito no topo
                if hook_ativo and lista_hooks:
                    hook_selecionado = lista_hooks[idx % len(lista_hooks)]
                    hook_ass_file = os.path.abspath(
                        os.path.join(PROJ_PATH, f"temp_hook_{idx}.ass")
                    )

                    gerar_hook_ass(
                        hook_selecionado,
                        hook_ass_file,
                        posicao_y=posicao_hook_y,
                        tamanho_fonte=tamanho_hook
                    )

                    if os.path.exists(hook_ass_file):
                        temp_hk = os.path.abspath(
                            os.path.join(PROJ_PATH, f"temp_hk_{idx}.mp4")
                        )
                        hook_path_clean = hook_ass_file.replace("\\", "/").replace(":", "\\:")

                        cmd_hk = (
                            f'ffmpeg -y -i "{out_final}" '
                            f'-vf "subtitles=\'{hook_path_clean}\'" '
                            f'-c:v {encoder_escolhido} -preset fast '
                            f'-pix_fmt yuv420p -c:a aac -ar 44100 -ac 2 '
                            f'-movflags +faststart "{temp_hk}"'
                        )

                        ok_hk, erro_hk = executar_ffmpeg(cmd_hk)

                        if ok_hk and os.path.exists(temp_hk):
                            os.replace(temp_hk, out_final)
                        elif not ok_hk:
                            st.warning(
                                f"⚠️ Hook não aplicado no vídeo {numero}: {erro_hk}"
                            )

                # Anti-duplicidade
                if auto_ultra_anti_dup and os.path.exists(out_final):
                    factor = round(random.uniform(0.85, 0.95), 2)

                    filtros_v = [
                        f"crop=iw*{factor}:ih*{factor}",
                        "scale=1080:1920",
                        random.choice([
                            "eq=brightness=0.02:contrast=1.05:saturation=1.04",
                            "eq=brightness=-0.015:contrast=1.07:saturation=0.96",
                            "eq=brightness=0.01:contrast=1.03:saturation=1.08",
                            "eq=brightness=-0.005:contrast=1.06:saturation=1.00",
                            "eq=brightness=0.025:contrast=1.02:saturation=0.95",
                            "eq=brightness=-0.02:contrast=1.04:saturation=1.05"
                        ])
                    ]

                    temp_filt = os.path.abspath(
                        os.path.join(PROJ_PATH, f"temp_filt_{idx}.mp4")
                    )

                    cmd_filt = (
                        f'ffmpeg -y -i "{out_final}" '
                        f'-vf "{",".join(filtros_v)}" '
                        f'-c:v {encoder_escolhido} -preset fast '
                        f'-pix_fmt yuv420p -c:a aac -ar 44100 -ac 2 '
                        f'-movflags +faststart "{temp_filt}"'
                    )

                    ok_filt, erro_filt = executar_ffmpeg(cmd_filt)

                    if ok_filt and os.path.exists(temp_filt):
                        os.replace(temp_filt, out_final)
                    elif not ok_filt:
                        st.warning(
                            f"⚠️ Anti-duplicidade não aplicado no vídeo {numero}: "
                            f"{erro_filt}"
                        )

                if not os.path.exists(out_final) or os.path.getsize(out_final) < 1000:
                    raise RuntimeError("FFmpeg terminou sem criar um MP4 válido.")

                gerados += 1
                status.write(f"✅ **{numero}/{total}** concluído.")

            except Exception as e:
                erros.append(f"Vídeo {numero}: {e}")
                st.error(f"❌ Vídeo {numero} falhou.")
                with st.expander(f"🔎 Ver erro do vídeo {numero}"):
                    st.code(str(e))

            finally:
                temporarios = [
                    h_tmp, m_tmp, c_tmp, concat_list,
                    os.path.join(PROJ_PATH, f"temp_{idx}.ass"),
                    os.path.join(PROJ_PATH, f"temp_hook_{idx}.ass"),
                    os.path.join(PROJ_PATH, f"temp_leg_{idx}.mp4"),
                    os.path.join(PROJ_PATH, f"temp_hk_{idx}.mp4"),
                    os.path.join(PROJ_PATH, f"temp_filt_{idx}.mp4")
                ]

                for t_file in temporarios:
                    if os.path.exists(t_file):
                        try:
                            os.remove(t_file)
                        except Exception:
                            pass

            prog.progress(numero / total)

        status.empty()

        if gerados == total:
            st.balloons()
            st.success(f"🎉 **{gerados}/{total} vídeos gerados com sucesso!**")
        elif gerados > 0:
            st.warning(f"⚠️ **{gerados}/{total} vídeos foram gerados.**")
            with st.expander("🔎 Ver todos os erros"):
                for erro in erros:
                    st.code(erro)
        else:
            st.error("❌ **Nenhum vídeo foi gerado.**")
            st.write("Veja o erro exibido em cada vídeo acima para identificar exatamente o problema.")

        # Não força rerun aqui: assim os erros ficam visíveis na tela.

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
