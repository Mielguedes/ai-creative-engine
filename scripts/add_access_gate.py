from pathlib import Path

app = Path('app.py')
text = app.read_text(encoding='utf-8')

import_line = 'from access_control import check_user_access\n'
if import_line not in text:
    anchor = 'from storage_sync import project_prefix, restore_file_from_storage, sync_project_to_storage\n'
    if anchor not in text:
        raise SystemExit('Import anchor not found')
    text = text.replace(anchor, anchor + import_line, 1)

gate = '''\n# ============================================================\n# CONTROLE OPCIONAL DE ACESSO DOS COMPRADORES\n# ============================================================\n_access_allowed, _access_message, _access_record = check_user_access(\n    st=st,\n    supabase_url=SUPABASE_URL,\n    supabase_key=SUPABASE_KEY,\n    access_token=st.session_state.get("access_token", ""),\n    user_id=USER_ID,\n)\nif not _access_allowed:\n    st.error(f"🔒 {_access_message}")\n    st.info("Se você acredita que isso é um engano, entre em contato com o suporte.")\n    st.stop()\n\nif _access_record:\n    st.session_state["user_plano"] = str(_access_record.get("plan") or "user")\n\n'''

marker = '# ============================================================\n# ESTRUTURA DE PASTAS E PROJETOS'
if 'check_user_access(' not in text:
    if marker not in text:
        raise SystemExit('Gate insertion marker not found')
    text = text.replace(marker, gate + marker, 1)

app.write_text(text, encoding='utf-8')
print('Access gate added')
