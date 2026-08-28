from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlparse

from openvino_chat.settings import (
    DEFAULT_MODEL_DIR,
    DEFAULT_REPO_ID,
    MODEL_DIRS,
    MODEL_EXPORT_REQUIRED,
    MODEL_MANIFEST_NAME,
    MODEL_REPOS,
    MODEL_ROOT,
    discover_model_dirs,
)


SnapshotDownload = Callable[..., str]
RepoFiles = Callable[[str], list[str]]
_HF_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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
    repo_files: RepoFiles | None = None,
) -> Path:
    key = name.lower()
    if key in MODEL_REPOS:
        if key in MODEL_EXPORT_REQUIRED:
            raise ValueError(f"export required for {key}: {MODEL_EXPORT_REQUIRED[key]}")
        return download_model(
            MODEL_REPOS[key],
            target_dir or MODEL_DIRS[key],
            snapshot_download,
        )
    return download_hf_model(
        name,
        target_dir=target_dir,
        snapshot_download=snapshot_download,
        repo_files=repo_files,
    )


def download_hf_model(
    repo: str,
    target_dir: Path | None = None,
    snapshot_download: SnapshotDownload | None = None,
    repo_files: RepoFiles | None = None,
) -> Path:
    repo_id = normalize_hf_repo_id(repo)
    target = Path(target_dir) if target_dir is not None else hf_model_target(repo_id)
    if is_openvino_model_dir(target):
        _write_model_manifest(target, repo_id)
        return target
    if target.exists() and not target.is_dir():
        raise ValueError(f"model target is not a folder: {target}")

    files = (repo_files or _list_repo_files)(repo_id)
    required = {"openvino_model.xml", "openvino_language_model.xml"}
    if not required.intersection(files):
        raise ValueError(
            f"Hugging Face repo is not OpenVINO-ready: {repo_id}\n"
            "expected openvino_model.xml or openvino_language_model.xml in repo root\n"
            "use an OpenVINO *-ov repo, or convert with: "
            f"optimum-cli export openvino --model {repo_id} --weight-format int4 <folder>"
        )

    if target_dir is not None:
        result = download_model(repo_id, target, snapshot_download)
        _write_model_manifest(result, repo_id)
        return result

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.download")
    try:
        result = download_model(repo_id, staging, snapshot_download)
        if target.exists():
            raise ValueError(f"model folder already exists: {target}")
        result.replace(target)
        _write_model_manifest(target, repo_id)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return target


def normalize_hf_repo_id(value: str) -> str:
    text = str(value).strip()
    parsed = urlparse(text)
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
            "huggingface.co",
            "www.huggingface.co",
            "hf.co",
            "www.hf.co",
        }:
            raise ValueError(f"not a Hugging Face model repo: {value}")
        parts = [part for part in parsed.path.split("/") if part]
    else:
        if "\\" in text or text.startswith(("/", ".", "~")):
            raise ValueError(f"not a Hugging Face model repo: {value}")
        parts = [part for part in text.split("/") if part]
    if len(parts) < 2:
        raise ValueError(
            f"unknown model: {value}; use built-in name or Hugging Face owner/repo"
        )
    owner, model = parts[:2]
    model = model.removesuffix(".git")
    if not _HF_COMPONENT.fullmatch(owner) or not _HF_COMPONENT.fullmatch(model):
        raise ValueError(f"invalid Hugging Face model repo: {value}")
    return f"{owner}/{model}"


def is_hf_repo_reference(value: str) -> bool:
    try:
        normalize_hf_repo_id(value)
    except ValueError:
        return False
    return True


def hf_model_target(repo_id: str, model_root: Path | None = None) -> Path:
    owner, model = normalize_hf_repo_id(repo_id).split("/", 1)
    root = Path(model_root if model_root is not None else MODEL_ROOT)
    folder = f"{owner}--{model}"
    return root / folder


def download_model(
    repo_id: str,
    target: Path,
    snapshot_download: SnapshotDownload | None = None,
) -> Path:
    downloader = snapshot_download or _snapshot_download
    existed = target.exists()
    downloader(repo_id=repo_id, local_dir=target)
    if not is_openvino_model_dir(target):
        if not existed and target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        raise RuntimeError(
            "downloaded folder is not an OpenVINO model: "
            f"{target} (missing openvino_model.xml or openvino_language_model.xml)"
        )
    return target


def is_openvino_model_dir(path: Path) -> bool:
    model_dir = Path(path)
    if not model_dir.exists() or not model_dir.is_dir():
        return False
    return any(
        (model_dir / name).is_file()
        for name in ("openvino_model.xml", "openvino_language_model.xml")
    )


def delete_named_model(name: str) -> Path:
    catalog = discover_model_dirs(MODEL_ROOT, MODEL_DIRS)
    target = next(
        (path for key, path in catalog.items() if key.casefold() == name.casefold()),
        None,
    )
    if target is None:
        raise ValueError(f"unknown model: {name}")
    resolved_target = target.resolve()
    root = MODEL_ROOT.resolve()
    if not _is_relative_to(resolved_target, root):
        raise ValueError(f"refusing to delete outside model root: {resolved_target}")
    if resolved_target.exists():
        shutil.rmtree(resolved_target)
    return resolved_target


def _snapshot_download(**kwargs: Any) -> str:
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "20")
    from huggingface_hub import snapshot_download

    kwargs.setdefault("max_workers", 1)
    return snapshot_download(**kwargs)


def _list_repo_files(repo_id: str) -> list[str]:
    from huggingface_hub import HfApi

    return HfApi().list_repo_files(repo_id, repo_type="model")


def _write_model_manifest(target: Path, repo_id: str) -> None:
    manifest = Path(target) / MODEL_MANIFEST_NAME
    temporary = manifest.with_suffix(manifest.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"repo_id": repo_id}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    temporary.replace(manifest)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
