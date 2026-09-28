from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any
from urllib.parse import urlparse

from openvino_chat.settings import (
    DEFAULT_MODEL_DIR,
    DEFAULT_REPO_ID,
    MODEL_DIRS,
    MODEL_EXPORT_REQUIRED,
    MODEL_MANIFEST_NAME,
    MODEL_REMOTES_PATH,
    MODEL_REPOS,
    MODEL_ROOT,
    canonical_model_name,
    discover_model_dirs,
)


SnapshotDownload = Callable[..., str]
RepoFiles = Callable[[str], list[str]]
_HF_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REMOTE_CATALOG_VERSION = 1


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
    raw_key = name.lower()
    canonical = canonical_model_name(raw_key)
    key = canonical if canonical in MODEL_REPOS or canonical in MODEL_EXPORT_REQUIRED else raw_key
    remote = model_remote_record(key)
    if remote and bool(remote.get("verified")):
        return restore_named_model(
            key,
            target_dir=target_dir,
            snapshot_download=snapshot_download,
            repo_files=repo_files,
        )
    if key in MODEL_EXPORT_REQUIRED:
        raise ValueError(f"export required for {key}: {MODEL_EXPORT_REQUIRED[key]}")
    if key in MODEL_REPOS:
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


def load_model_remotes(path: Path | None = None) -> dict[str, dict[str, Any]]:
    catalog_path = Path(path or MODEL_REMOTES_PATH)
    if not catalog_path.exists():
        return {}
    try:
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid model remote catalog: {catalog_path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != _REMOTE_CATALOG_VERSION:
        raise RuntimeError(f"unsupported model remote catalog: {catalog_path}")
    models = data.get("models")
    if not isinstance(models, dict):
        raise RuntimeError(f"invalid model remote catalog: {catalog_path}")
    return {
        str(key): dict(value)
        for key, value in models.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def model_remote_record(name: str, path: Path | None = None) -> dict[str, Any] | None:
    key = canonical_model_name(name)
    if path is not None:
        for candidate, candidate_path in discover_model_dirs(MODEL_ROOT, MODEL_DIRS).items():
            if _same_path(candidate_path, path):
                key = canonical_model_name(candidate)
                break
    record = load_model_remotes().get(key)
    return dict(record) if record else None


def remote_model_dirs(remotes_path: Path | None = None) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for key, record in load_model_remotes(remotes_path).items():
        target_dir = str(record.get("target_dir") or "").strip()
        if (
            not target_dir
            or target_dir in {".", ".."}
            or "/" in target_dir
            or "\\" in target_dir
        ):
            continue
        result[canonical_model_name(key)] = MODEL_ROOT / target_dir
    return result


def model_retention_status(name: str, path: Path) -> str:
    key = canonical_model_name(name)
    remote = model_remote_record(key, path)
    if remote and bool(remote.get("verified")) and remote.get("repo_id"):
        return f"backup verified ({remote['repo_id']})"
    if key in MODEL_REPOS and key not in MODEL_EXPORT_REQUIRED:
        return f"downloadable ({MODEL_REPOS[key]})"
    if key not in MODEL_DIRS:
        repo = _manifest_repo(path)
        if repo:
            return f"downloadable ({repo})"
    return "local only"


def backup_named_model(
    name: str,
    repo_id: str | None = None,
    *,
    api: Any | None = None,
    remotes_path: Path | None = None,
) -> dict[str, Any]:
    key, target = _resolve_named_model(name, remotes_path)
    if not is_openvino_model_dir(target):
        raise ValueError(f"model is not installed or invalid: {target}")
    if api is None:
        from huggingface_hub import HfApi, get_token

        if not get_token():
            raise RuntimeError(
                "Hugging Face authentication required. Run locally: "
                f'"{sys.executable}" -c "from huggingface_hub import login; login()"'
            )
        api = HfApi()
    if repo_id is None:
        identity = api.whoami()
        owner = str(identity.get("name") or "").strip()
        if not owner:
            raise RuntimeError("Hugging Face account name is unavailable")
        repo_id = f"{owner}/openvino-{target.name}"
    repo_id = normalize_hf_repo_id(repo_id)

    api.create_repo(repo_id, repo_type="model", private=True, exist_ok=True)
    uploader = getattr(api, "upload_large_folder", None)
    if callable(uploader):
        uploader(
            repo_id,
            target,
            repo_type="model",
            private=True,
            ignore_patterns=[".cache/**"],
            print_report=False,
        )
    else:
        api.upload_folder(
            repo_id=repo_id,
            folder_path=target,
            repo_type="model",
            ignore_patterns=[".cache/**"],
        )

    local_files = _local_model_inventory(target)
    info = api.model_info(repo_id, files_metadata=True)
    remote_files = {
        sibling.rfilename: sibling.size
        for sibling in (getattr(info, "siblings", None) or [])
    }
    missing = sorted(set(local_files) - set(remote_files))
    mismatched = sorted(
        filename
        for filename, size in local_files.items()
        if filename in remote_files and remote_files[filename] != size
    )
    if missing or mismatched:
        detail = []
        if missing:
            detail.append("missing=" + ", ".join(missing[:8]))
        if mismatched:
            detail.append("size_mismatch=" + ", ".join(mismatched[:8]))
        raise RuntimeError("Hugging Face backup verification failed: " + "; ".join(detail))
    if not {"openvino_model.xml", "openvino_language_model.xml"}.intersection(remote_files):
        raise RuntimeError("Hugging Face backup verification failed: OpenVINO entrypoint missing")

    record = {
        "repo_id": repo_id,
        "target_dir": target.name,
        "verified": True,
        "file_count": len(local_files),
        "bytes": sum(local_files.values()),
        "files": local_files,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    remotes = load_model_remotes(remotes_path)
    remotes[key] = record
    _write_model_remotes(remotes, remotes_path)
    return dict(record)


def restore_named_model(
    name: str,
    target_dir: Path | None = None,
    *,
    snapshot_download: SnapshotDownload | None = None,
    repo_files: RepoFiles | None = None,
    remotes_path: Path | None = None,
) -> Path:
    key, configured_target = _resolve_named_model(name, remotes_path)
    remote = load_model_remotes(remotes_path).get(key)
    if not remote or not remote.get("verified") or not remote.get("repo_id"):
        raise ValueError(f"no verified Hugging Face backup for {key}")
    repo_id = normalize_hf_repo_id(str(remote["repo_id"]))
    target = Path(target_dir) if target_dir is not None else configured_target
    if is_openvino_model_dir(target):
        return target
    if target.exists():
        raise ValueError(f"model target already exists but is invalid: {target}")
    files = (repo_files or _list_repo_files)(repo_id)
    if not {"openvino_model.xml", "openvino_language_model.xml"}.intersection(files):
        raise RuntimeError(f"verified backup is no longer OpenVINO-ready: {repo_id}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.restore")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        download_model(repo_id, staging, snapshot_download)
        _verify_restored_inventory(staging, remote, repo_id)
        staging.replace(target)
        _write_model_manifest(target, repo_id)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return target


def delete_named_model(name: str, *, force: bool = False) -> Path:
    key, target = _resolve_named_model(name)
    resolved_target = target.resolve()
    root = MODEL_ROOT.resolve()
    if resolved_target == root or not _is_relative_to(resolved_target, root):
        raise ValueError(f"refusing to delete outside model root: {resolved_target}")
    if resolved_target.exists() and not force and model_retention_status(key, target) == "local only":
        raise ValueError(
            f"refusing to delete local-only model {key}; run 'openvino backup {key}' first "
            "or repeat delete with --force"
        )
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


def _resolve_named_model(
    name: str,
    remotes_path: Path | None = None,
) -> tuple[str, Path]:
    catalog = discover_model_dirs(MODEL_ROOT, MODEL_DIRS)
    requested = name.strip().casefold()
    canonical = canonical_model_name(requested)
    for key, path in catalog.items():
        if key.casefold() in {requested, canonical}:
            return canonical_model_name(key), path
    for key, path in remote_model_dirs(remotes_path).items():
        if key.casefold() in {requested, canonical}:
            return canonical_model_name(key), path
    raise ValueError(f"unknown model: {name}")


def _manifest_repo(path: Path) -> str | None:
    manifest = Path(path) / MODEL_MANIFEST_NAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    value = str(data.get("repo_id") or "").strip()
    return value or None


def _local_model_inventory(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in Path(path).rglob("*"):
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix()
        if relative == ".cache" or relative.startswith(".cache/"):
            continue
        result[relative] = item.stat().st_size
    return result


def _verify_restored_inventory(
    path: Path,
    record: dict[str, Any],
    repo_id: str,
) -> None:
    actual = _local_model_inventory(path)
    raw_expected = record.get("files")
    expected: dict[str, int] | None = None
    if isinstance(raw_expected, dict):
        parsed: dict[str, int] = {}
        for filename, raw_size in raw_expected.items():
            if not isinstance(filename, str):
                parsed = {}
                break
            try:
                size = int(raw_size)
            except (TypeError, ValueError):
                parsed = {}
                break
            if size < 0:
                parsed = {}
                break
            parsed[filename] = size
        if parsed:
            expected = parsed

    problems: list[str] = []
    if expected is not None:
        missing = sorted(set(expected) - set(actual))
        mismatched = sorted(
            filename
            for filename, size in expected.items()
            if filename in actual and actual[filename] != size
        )
        if missing:
            problems.append("missing=" + ", ".join(missing[:8]))
        if mismatched:
            problems.append("size_mismatch=" + ", ".join(mismatched[:8]))

    expected_count = record.get("file_count")
    if isinstance(expected_count, int) and len(actual) < expected_count:
        problems.append(f"file_count={len(actual)} expected_at_least={expected_count}")
    expected_bytes = record.get("bytes")
    if isinstance(expected_bytes, int) and sum(actual.values()) < expected_bytes:
        problems.append(
            f"bytes={sum(actual.values())} expected_at_least={expected_bytes}"
        )
    if problems:
        raise RuntimeError(
            f"restored backup verification failed for {repo_id}: " + "; ".join(problems)
        )


def _write_model_remotes(
    models: dict[str, dict[str, Any]],
    path: Path | None = None,
) -> None:
    catalog_path = Path(path or MODEL_REMOTES_PATH)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = catalog_path.with_suffix(catalog_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {"version": _REMOTE_CATALOG_VERSION, "models": models},
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    temporary.replace(catalog_path)


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(os.fspath(left))) == os.path.normcase(
        os.path.abspath(os.fspath(right))
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
