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
if old_leg not in text:
    raise SystemExit("Trecho de legendas não encontrado")
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
if old_hook not in text:
    raise SystemExit("Trecho de Hook não encontrado")
text = text.replace(old_hook, new_hook, 1)

# Make Whisper failures visible in the Streamlit interface.
old_except = '    except Exception as e:\n        print(f"[ERRO WHISPER]: {e}")\n        return False'
new_except = '    except Exception as e:\n        st.error(f"❌ Erro ao gerar legendas com Whisper: {e}")\n        return False'
if old_except in text:
    text = text.replace(old_except, new_except, 1)

# Use a widely available fallback font in both ASS styles.
text = text.replace("The Bold Font", "DejaVu Sans")

APP.write_text(text, encoding="utf-8")
print("Patch aplicado em app.py")
