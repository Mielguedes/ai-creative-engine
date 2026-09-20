"""Helpers for persistent Supabase Storage files.

This module is intentionally independent from the Streamlit UI so it can be
integrated incrementally without changing the current rendering flow.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests


class StorageError(RuntimeError):
    """Raised when a Supabase Storage operation fails."""


def _config() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_KEY", "").strip()
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "ai-creative-engine").strip()

    if not url or not key or not bucket:
        raise StorageError(
            "Configure SUPABASE_URL, SUPABASE_KEY and SUPABASE_STORAGE_BUCKET."
        )

    return url, key, bucket


def _headers(access_token: Optional[str] = None) -> dict[str, str]:
    _, key, _ = _config()
    headers = {
        "apikey": key,
        "Content-Type": "application/octet-stream",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    else:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _object_url(object_path: str) -> str:
    url, _, bucket = _config()
    clean_path = object_path.strip("/")
    if not clean_path:
        raise StorageError("object_path cannot be empty.")
    return f"{url}/storage/v1/object/{bucket}/{clean_path}"


def upload_file(
    local_path: str | Path,
    object_path: str,
    access_token: Optional[str] = None,
    overwrite: bool = True,
) -> None:
    """Upload one local file to the configured private bucket."""
    path = Path(local_path)
    if not path.is_file():
        raise StorageError(f"Local file not found: {path}")

    headers = _headers(access_token)
    headers["x-upsert"] = "true" if overwrite else "false"
    headers["Content-Type"] = "application/octet-stream"

    with path.open("rb") as stream:
        response = requests.post(
            _object_url(object_path),
            headers=headers,
            data=stream,
            timeout=300,
        )

    if response.status_code not in (200, 201):
        raise StorageError(
            f"Storage upload failed ({response.status_code}): "
            f"{response.text[:1000]}"
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
            f"Storage download failed ({response.status_code}): "
            f"{response.text[:1000]}"
        )

    with destination.open("wb") as stream:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                stream.write(chunk)

    return destination


def delete_file(
    object_path: str,
    access_token: Optional[str] = None,
) -> None:
    """Delete one object from the configured bucket."""
    response = requests.delete(
        _object_url(object_path),
        headers=_headers(access_token),
        timeout=60,
    )

    if response.status_code not in (200, 204):
        raise StorageError(
            f"Storage delete failed ({response.status_code}): "
            f"{response.text[:1000]}"
        )
