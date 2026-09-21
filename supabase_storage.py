"""Helpers for persistent Supabase Storage files.

The module remains independent from the Streamlit UI and supports either
explicit configuration, environment variables, or Streamlit secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests


class StorageError(RuntimeError):
    """Raised when a Supabase Storage operation fails."""


_CONFIG: dict[str, str] = {}


def _normalize_url(url: str) -> str:
    """Return the Supabase project URL without API path suffixes."""
    clean = (url or "").strip().rstrip("/")
    for suffix in ("/rest/v1", "/storage/v1", "/auth/v1"):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)].rstrip("/")
    return clean


def configure(url: str, key: str, bucket: str = "ai-creative-engine") -> None:
    """Configure Storage explicitly, preferably once after user login."""
    _CONFIG["url"] = _normalize_url(url)
    _CONFIG["key"] = (key or "").strip()
    _CONFIG["bucket"] = (bucket or "").strip()


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value

    try:
        import streamlit as st

        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def _config() -> tuple[str, str, str]:
    url = _CONFIG.get("url") or _secret("SUPABASE_URL")
    key = (
        _CONFIG.get("key")
        or _secret("SUPABASE_KEY")
        or _secret("SUPABASE_ANON_KEY")
    )
    bucket = _CONFIG.get("bucket") or _secret("SUPABASE_STORAGE_BUCKET") or "ai-creative-engine"

    if not url or not key or not bucket:
        raise StorageError(
            "Configure SUPABASE_URL, SUPABASE_KEY ou SUPABASE_ANON_KEY e SUPABASE_STORAGE_BUCKET."
        )

    return _normalize_url(url), key, bucket.strip()


def _headers(access_token: Optional[str] = None) -> dict[str, str]:
    _, key, _ = _config()
    return {
        "apikey": key,
        "Content-Type": "application/octet-stream",
        "Authorization": f"Bearer {access_token or key}",
    }


def _object_url(object_path: str) -> str:
    url, _, bucket = _config()
    clean_path = "/".join(
        part
        for part in object_path.strip("/").split("/")
        if part not in ("", ".", "..")
    )
    if not clean_path:
        raise StorageError("object_path cannot be empty.")
    return f"{url}/storage/v1/object/{bucket}/{clean_path}"


def upload_file(
    local_path: str | Path,
    object_path: str,
    access_token: Optional[str] = None,
    overwrite: bool = True,
) -> None:
    """Upload one local file to the configured bucket."""
    path = Path(local_path)
    if not path.is_file():
        raise StorageError(f"Local file not found: {path}")

    headers = _headers(access_token)
    headers["x-upsert"] = "true" if overwrite else "false"

    with path.open("rb") as stream:
        response = requests.post(
            _object_url(object_path),
            headers=headers,
            data=stream,
            timeout=300,
        )

    if response.status_code not in (200, 201):
        raise StorageError(
            f"Storage upload failed ({response.status_code}): {response.text[:1000]}"
        )


def download_file(
    object_path: str,
    local_path: str | Path,
    access_token: Optional[str] = None,
) -> Path:
    """Download one object to a local file and return its path."""
    destination = Path(local_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        _object_url(object_path),
        headers=_headers(access_token),
        stream=True,
        timeout=300,
    )

    if response.status_code != 200:
        raise StorageError(
            f"Storage download failed ({response.status_code}): {response.text[:1000]}"
        )

    with destination.open("wb") as stream:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                stream.write(chunk)

    return destination


def delete_file(object_path: str, access_token: Optional[str] = None) -> None:
    """Delete one object from the configured bucket."""
    response = requests.delete(
        _object_url(object_path),
        headers=_headers(access_token),
        timeout=60,
    )

    if response.status_code not in (200, 204):
        raise StorageError(
            f"Storage delete failed ({response.status_code}): {response.text[:1000]}"
        )
