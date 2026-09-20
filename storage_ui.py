"""Streamlit-facing helpers for local uploads and optional Supabase sync."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Any

import streamlit as st

from supabase_storage import StorageError, upload_file
from storage_sync import project_prefix


def _safe_name(name: str) -> str:
    clean = re.sub(r"[^\w.\-]", "_", str(name or "").strip())
    if not clean or clean in {".", ".."}:
        raise StorageError("Invalid uploaded filename.")
    return clean


def _content_hash(uploaded_file: Any) -> str:
    digest = hashlib.sha256()
    digest.update(uploaded_file.getbuffer())
    return digest.hexdigest()


def save_uploaded_files(
    files: Iterable[Any],
    destination: str | Path,
    *,
    user_id: str | None = None,
    project_name: str | None = None,
    storage_subfolder: str | None = None,
    access_token: str | None = None,
) -> list[Path]:
    """Save uploads locally and sync them to Storage once per session/hash.

    Local files remain available to the existing FFmpeg rendering pipeline.
    Storage synchronization is best-effort: a failed remote upload is reported
    in the UI without deleting the local copy.
    """
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    uploaded_cache = st.session_state.setdefault("storage_uploaded_hashes", set())

    for uploaded in files or []:
        filename = _safe_name(getattr(uploaded, "name", "upload.mp4"))
        local_path = target / filename
        content_hash = _content_hash(uploaded)

        if not local_path.exists() or local_path.stat().st_size == 0:
            local_path.write_bytes(uploaded.getbuffer())
        saved.append(local_path)

        if not user_id or not project_name or not storage_subfolder:
            continue

        cache_key = f"{user_id}/{project_name}/{storage_subfolder}/{filename}:{content_hash}"
        if cache_key in uploaded_cache:
            continue

        object_path = f"{project_prefix(user_id, project_name)}/{storage_subfolder}/{filename}"
        try:
            upload_file(
                local_path,
                object_path,
                access_token=access_token,
                overwrite=True,
            )
            uploaded_cache.add(cache_key)
        except Exception as exc:
            st.warning(f"Upload local salvo, mas o Storage não foi sincronizado ({filename}): {exc}")

    return saved
