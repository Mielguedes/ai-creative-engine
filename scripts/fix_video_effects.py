from pathlib import Path
import re

APP = Path("app.py")
text = APP.read_text(encoding="utf-8")

# Add a safe FFmpeg runner once.
marker = "# --- FUNÇÃO: PREPARAR/TRATAR VÍDEO INDIVIDUAL DE BLOCO ---"
helper = r'''def executar_ffmpeg(args, etapa):
    """Executa FFmpeg sem shell e mostra o erro real na interface."""
    try:
        resultado = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        st.error(f"❌ Falha ao iniciar FFmpeg ({etapa}): {exc}")
        return False

    if resultado.returncode != 0:
        detalhe = (resultado.stderr or resultado.stdout or "Sem detalhes").strip()
        st.error(f"❌ FFmpeg falhou em {etapa} (código {resultado.returncode}).")
        st.code(detalhe[-4000:], language="text")
        return False
    return True


'''
if "def executar_ffmpeg(args, etapa):" not in text:
    text = text.replace(marker, helper + marker, 1)

# Replace the block-processing function with a shell-free implementation.
pattern = r"def processar_bloco_individual\(.*?\n\ndef criar_zip_projeto"
replacement = r'''def processar_bloco_individual(caminho_entrada, caminho_saida, encoder_video="libx264", deve_espelhar=False):
    filtros = ["hflip"] if deve_espelhar else []
    if not filtros:
        shutil.copyfile(caminho_entrada, caminho_saida)
        return True

    args = [
        "ffmpeg", "-y", "-i", str(caminho_entrada),
        "-vf", ",".join(filtros),
        "-c:v", encoder_video,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(caminho_saida),
    ]
    return executar_ffmpeg(args, "espelhamento do bloco")


def criar_zip_projeto'''
text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
if count != 1:
    raise SystemExit("Não foi possível localizar processar_bloco_individual")

# Replace subtitle FFmpeg invocation.
old_leg = r'''                    ass_path_clean = ass_file.replace("\\", "/").replace(":", "\\:")
                    cmd_leg = f'ffmpeg -y -i "{out_final}" -vf "subtitles=\'{ass_path_clean}\'" -c:v {encoder_escolhido} -pix_fmt yuv420p -c:a copy "{temp_leg}"'
                    subprocess.run(cmd_leg, shell=True)
                    if os.path.exists(temp_leg):
                        shutil.move(temp_leg, out_final)'''
new_leg = r'''                    ass_path_clean = ass_file.replace("\\", "/").replace(":", r"\:")
                    args_leg = [
                        "ffmpeg", "-y", "-i", out_final,
                        "-vf", f"subtitles={ass_path_clean}",
                        "-c:v", encoder_escolhido,
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        temp_leg,
                    ]
                    if executar_ffmpeg(args_leg, "legendas automáticas") and os.path.exists(temp_leg):
                        shutil.move(temp_leg, out_final)
                    elif os.path.exists(temp_leg):
                        os.remove(temp_leg)'''
if old_leg in text:
    text = text.replace(old_leg, new_leg, 1)

# Replace hook FFmpeg invocation.
old_hook = r'''                    hook_path_clean = hook_ass_file.replace("\\", "/").replace(":", "\\:")
                    cmd_hk = f'ffmpeg -y -i "{out_final}" -vf "subtitles=\'{hook_path_clean}\'" -c:v {encoder_escolhido} -pix_fmt yuv420p -c:a copy "{temp_hk}"'
                    subprocess.run(cmd_hk, shell=True)
                    if os.path.exists(temp_hk):
                        shutil.move(temp_hk, out_final)'''
new_hook = r'''                    hook_path_clean = hook_ass_file.replace("\\", "/").replace(":", r"\:")
                    args_hook = [
                        "ffmpeg", "-y", "-i", out_final,
                        "-vf", f"subtitles={hook_path_clean}",
                        "-c:v", encoder_escolhido,
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        temp_hk,
                    ]
                    if executar_ffmpeg(args_hook, "Hook alternativo") and os.path.exists(temp_hk):
                        shutil.move(temp_hk, out_final)
                    elif os.path.exists(temp_hk):
                        os.remove(temp_hk)'''
if old_hook in text:
    text = text.replace(old_hook, new_hook, 1)

# Make Whisper failures visible in the Streamlit interface.
old_except = '    except Exception as e:\n        print(f"[ERRO WHISPER]: {e}")\n        return False'
new_except = '    except Exception as e:\n        st.error(f"❌ Erro ao gerar legendas com Whisper: {e}")\n        return False'
if old_except in text:
    text = text.replace(old_except, new_except, 1)

# Use a widely available fallback font in both ASS styles.
text = text.replace("The Bold Font", "DejaVu Sans")

# Add a straight/rotated Hook control and a simple on-screen preview.
if "angulo_hook = st.slider" not in text:
    anchor = '        tamanho_hook = st.number_input("Tamanho da Fonte do Hook:", min_value=20, max_value=250, value=100, step=5)'
    addition = anchor + '\n        angulo_hook = st.slider("Inclinação do Hook (graus):", min_value=-10, max_value=10, value=0, step=1, help="0 deixa o Hook reto.")\n        st.markdown(f"**Pré-visualização do Hook**\\n\\n<div style=\"background:white;color:black;padding:14px;text-align:center;font-size:{min(int(tamanho_hook), 64)}px;font-weight:800;transform:rotate({angulo_hook}deg);border:2px solid #ddd;\">{texto_manchete.splitlines()[0] if texto_manchete.strip() else 'SEU HOOK AQUI'}</div>", unsafe_allow_html=True)'
    if anchor in text:
        text = text.replace(anchor, addition, 1)

if 'angulo_hook = 0' not in text:
    text = text.replace('    tamanho_hook = 100\nelse:', '    tamanho_hook = 100\n    angulo_hook = 0\nelse:', 1)

# Update Hook ASS generation to use the selected angle instead of a fixed -2.5 degrees.
text = text.replace('def gerar_hook_ass(texto_hook, caminho_saida_ass, posicao_y=200, tamanho_fonte=100):', 'def gerar_hook_ass(texto_hook, caminho_saida_ass, posicao_y=200, tamanho_fonte=100, angulo=0):')
text = text.replace('{{\\\\frz-2.5}}{texto_hook}', '{{\\\\frz{angulo}}}{texto_hook}')
text = text.replace('{{\\\\frz-2.5\\\\fad(0,500)}}{texto_hook}', '{{\\\\frz{angulo}\\\\fad(0,500)}}{texto_hook}')
text = text.replace('gerar_hook_ass(hook_selecionado, hook_ass_file, posicao_y=posicao_hook_y, tamanho_fonte=tamanho_hook)', 'gerar_hook_ass(hook_selecionado, hook_ass_file, posicao_y=posicao_hook_y, tamanho_fonte=tamanho_hook, angulo=angulo_hook)')

APP.write_text(text, encoding="utf-8")
print("Patch aplicado em app.py")
