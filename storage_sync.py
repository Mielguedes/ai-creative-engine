"""Optional Supabase Storage synchronization for AI Creative Engine.

This module does not change the existing rendering flow. It provides safe,
per-user project synchronization helpers that can be wired into the UI in a
later step.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from supabase_storage import StorageError, upload_file, download_file


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}


def _user_prefix(user_id: str) -> str:
    clean = str(user_id or "").strip()
    if not clean or "/" in clean or "\\" in clean or clean in {".", ".."}:
        raise StorageError("Invalid user_id for storage path.")
    return f"users/{clean}"


def project_prefix(user_id: str, project_name: str) -> str:
    clean_project = str(project_name or "").strip()
    if not clean_project or "/" in clean_project or "\\" in clean_project:
        raise StorageError("Invalid project name for storage path.")
    return f"{_user_prefix(user_id)}/projects/{clean_project}"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_project_manifest(project_dir: str | Path) -> dict[str, Any]:
    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise StorageError(f"Project directory not found: {root}")

    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        relative = path.relative_to(root).as_posix()
        files.append({
            "path": relative,
            "size": path.stat().st_size,
            "sha256": _file_sha256(path),
        })

    return {
        "version": 1,
        "project": root.name,
        "files": files,
    }


def sync_project_to_storage(
    user_id: str,
    project_name: str,
    project_dir: str | Path,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Upload project videos and a manifest to Supabase Storage."""
    root = Path(project_dir).resolve()
    manifest = build_project_manifest(root)
    prefix = project_prefix(user_id, project_name)

    for item in manifest["files"]:
        local_path = root / item["path"]
        object_path = f"{prefix}/{item['path']}"
        upload_file(local_path, object_path, access_token=access_token, overwrite=True)

    manifest_path = root / ".storage-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    upload_file(
        manifest_path,
        f"{prefix}/.storage-manifest.json",
        access_token=access_token,
        overwrite=True,
    )
    return manifest


def restore_file_from_storage(
    user_id: str,
    project_name: str,
    relative_path: str,
    destination_dir: str | Path,
    access_token: str | None = None,
) -> Path:
    """Restore one project file while preventing path traversal."""
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise StorageError("Invalid relative file path.")

    destination = Path(destination_dir).resolve() / relative
    base = Path(destination_dir).resolve()
    if base not in destination.parents and destination != base:
        raise StorageError("Destination escapes project directory.")

    object_path = f"{project_prefix(user_id, project_name)}/{relative.as_posix()}"
    return download_file(object_path, destination, access_token=access_token)
