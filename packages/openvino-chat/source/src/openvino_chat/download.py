from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path
import shutil
from typing import Any

from openvino_chat.settings import DEFAULT_MODEL_DIR, DEFAULT_REPO_ID, MODEL_DIRS, MODEL_EXPORT_REQUIRED, MODEL_REPOS, MODEL_ROOT


SnapshotDownload = Callable[..., str]


def download_qwen(
    target_dir: Path | None = None,
    snapshot_download: SnapshotDownload | None = None,
) -> Path:
    target = target_dir or DEFAULT_MODEL_DIR
    return download_model(DEFAULT_REPO_ID, target, snapshot_download)


def download_named_model(
    name: str,
    target_dir: Path | None = None,
    snapshot_download: SnapshotDownload | None = None,
) -> Path:
    key = name.lower()
    if key not in MODEL_REPOS:
        raise ValueError(f"unknown model: {name}")
    if key in MODEL_EXPORT_REQUIRED:
        raise ValueError(f"export required for {key}: {MODEL_EXPORT_REQUIRED[key]}")
    return download_model(
        MODEL_REPOS[key],
        target_dir or MODEL_DIRS[key],
        snapshot_download,
    )


def download_model(
    repo_id: str,
    target: Path,
    snapshot_download: SnapshotDownload | None = None,
) -> Path:
    downloader = snapshot_download or _snapshot_download
    downloader(
        repo_id=repo_id,
        local_dir=target,
    )
    return target


def delete_named_model(name: str) -> Path:
    key = name.lower()
    if key not in MODEL_DIRS:
        raise ValueError(f"unknown model: {name}")
    target = MODEL_DIRS[key].resolve()
    root = MODEL_ROOT.resolve()
    if not _is_relative_to(target, root):
        raise ValueError(f"refusing to delete outside model root: {target}")
    if target.exists():
        shutil.rmtree(target)
    return target


def _snapshot_download(**kwargs: Any) -> str:
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "20")
    from huggingface_hub import snapshot_download

    kwargs.setdefault("max_workers", 1)
    return snapshot_download(**kwargs)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
