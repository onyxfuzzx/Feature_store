"""Opaque storage keys; client filenames and URIs never select local paths."""
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.core.config import settings


def artifact_path(uri: str | None, model_id: UUID, version_id: UUID) -> Path:
    if not uri or not uri.startswith("artifact://"):
        raise HTTPException(404, "No managed artifact uploaded for this version")
    key = uri[len("artifact://"):]
    parts = key.split("/")
    if len(parts) != 3 or parts[:2] != [str(model_id), str(version_id)]:
        raise HTTPException(400, "Artifact key does not belong to this model version")
    try:
        UUID(parts[2])
    except ValueError as exc:
        raise HTTPException(400, "Invalid artifact storage key") from exc
    root = settings.artifact_storage_dir.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(400, "Artifact path escapes storage")
    return path


def store_artifact(file, model_id, version_id):
    name = file.filename or ""
    if (not name or name in {".", ".."} or len(name) > 200 or ":" in name or "\x00" in name
            or PurePosixPath(name).name != name or PureWindowsPath(name).name != name):
        raise HTTPException(400, "Artifact filename must be a plain filename")
    uri = f"artifact://{model_id}/{version_id}/{uuid4()}"
    path = artifact_path(uri, model_id, version_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    size = 0
    try:
        with partial.open("xb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.artifact_max_bytes:
                    raise HTTPException(413, "Artifact exceeds ARTIFACT_MAX_BYTES")
                output.write(chunk)
        if not size:
            raise HTTPException(400, "Artifact is empty")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return uri, path, size
