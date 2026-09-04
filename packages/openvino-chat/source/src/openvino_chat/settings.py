from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_OPENVINO_HOME = Path.home() / ".openvino"
OPENVINO_HOME = Path(os.environ.get("OPENVINO_HOME", DEFAULT_OPENVINO_HOME)).expanduser()
MODEL_ROOT = Path(os.environ.get("OPENVINO_MODEL_ROOT", OPENVINO_HOME / "models")).expanduser()
CONFIG_PATH = Path(
    os.environ.get("OPENVINO_CHAT_CONFIG", OPENVINO_HOME / "config.json")
).expanduser()
REPORT_DIR = Path(
    os.environ.get("OPENVINO_CHAT_REPORT_DIR", OPENVINO_HOME / "reports")
).expanduser()
SESSION_DIR = Path(
    os.environ.get("OPENVINO_CHAT_SESSION_DIR", OPENVINO_HOME / "sessions")
).expanduser()
EXPORT_DIR = Path(
    os.environ.get("OPENVINO_CHAT_EXPORT_DIR", OPENVINO_HOME / "exports")
).expanduser()
API_DIR = Path(
    os.environ.get("OPENVINO_CHAT_API_DIR", OPENVINO_HOME / "api")
).expanduser()
BENCHMARK_PATH = Path(
    os.environ.get("OPENVINO_CHAT_BENCHMARK_PATH", OPENVINO_HOME / "benchmarks.json")
).expanduser()
KNOWLEDGE_DIR = Path(
    os.environ.get("OPENVINO_CHAT_KNOWLEDGE_DIR", OPENVINO_HOME / "knowledge")
).expanduser()
KNOWLEDGE_INDEX_PATH = Path(
    os.environ.get("OPENVINO_CHAT_KNOWLEDGE_INDEX", KNOWLEDGE_DIR / "index.json")
).expanduser()
KNOWLEDGE_MODELS_DIR = Path(
    os.environ.get("OPENVINO_CHAT_KNOWLEDGE_MODELS", KNOWLEDGE_DIR / "models")
).expanduser()
MODEL_MANIFEST_NAME = ".openvino-chat-model.json"

DEFAULT_CONTEXT_LENGTH = 16384
DEFAULT_AUTO_COMPACT = True
DEFAULT_DUCK_MODE = False
GENERATION_EFFORTS = ("low", "medium", "high", "custom")
GENERATION_EFFORT_ALIASES = {
    "fast": "low",
    "balanced": "medium",
    "default": "medium",
    "deep": "high",
    "max": "high",
}
DEFAULT_GENERATION_EFFORT = "medium"
KNOWLEDGE_MODES = ("offline", "auto", "web")
DEFAULT_KNOWLEDGE_MODE = "auto"
RAG_EMBED_REPO = "OpenVINO/bge-base-en-v1.5-int8-ov"
RAG_RERANK_REPO = "OpenVINO/bge-reranker-base-int8-ov"

MODEL_REPOS = {
    "qwen": "OpenVINO/Qwen3.5-9B-int4-ov",
    "tiny": "empero-ai/Qwen3.8-4B-Distill",
    "gemma": "OpenVINO/gemma-4-E4B-it-int4-ov",
    "ornith": "ornith-ai/Ornith-1.5-9B",
}
MODEL_DIRS = {
    "qwen": MODEL_ROOT / "qwen3.5-9b-int4-ov",
    "qwen38": MODEL_ROOT / "qwen3.8-9b-int4-ov",
    "tiny": MODEL_ROOT / "qwen3.8-4b-int4-ov",
    "gemma": MODEL_ROOT / "gemma-4-e4b-it-int4-ov",
    "ornith": MODEL_ROOT / "ornith-1.5-9b-int4-ov",
}
MODEL_EXPORT_REQUIRED = {
    "tiny": "Qwen3.8-4B-Distill needs OpenVINO INT4 export; import a converted folder or compatible conversion archive.",
    "ornith": "Ornith-1.5-9B must be exported to OpenVINO INT4 first; place the converted model in the ornith model path.",
}
DEFAULT_GENERATION_SETTINGS = {
    "temperature": 0.7,
    "top_p": 0.9,
}
MODEL_GENERATION_SETTINGS = {
    "gemma": {
        "general": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
        "coding": {"temperature": 1.0, "top_p": 0.95, "top_k": 64},
    },
    "qwen38": {
        "general": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
        "coding": {"temperature": 0.6, "top_p": 0.95, "top_k": 20},
    },
    "ornith": {
        "general": {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
        },
        "coding": {
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
        },
    },
}
QWEN_GENERATION_SETTINGS = {
    "on": {
        "general": {
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
        },
        "coding": {
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 0.0,
            "repetition_penalty": 1.0,
        },
    },
    "off": {
        "general": {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5,
            "repetition_penalty": 1.0,
        },
        "coding": {
            "temperature": 1.0,
            "top_p": 1.0,
            "top_k": 40,
            "min_p": 0.0,
            "presence_penalty": 2.0,
            "repetition_penalty": 1.0,
        },
    },
}
BINARY_THINKING_EFFORTS = ("off", "on")
GRADED_THINKING_EFFORTS = ("off", "low", "medium", "xhigh")
THINKING_EFFORTS = BINARY_THINKING_EFFORTS + ("low", "medium", "xhigh")
THINKING_EFFORT_ALIASES = {
    "none": "off",
    "default": "on",
    "high": "xhigh",
}
DEFAULT_THINKING_EFFORT = "on"

DEFAULT_MODEL = "qwen"
DEFAULT_REPO_ID = MODEL_REPOS[DEFAULT_MODEL]
DEFAULT_MODEL_DIR = MODEL_DIRS[DEFAULT_MODEL]


def discover_model_dirs(
    model_root: Path | None = None,
    known_dirs: dict[str, Path] | None = None,
) -> dict[str, Path]:
    """Return built-in aliases plus every visible folder under model root."""
    root = Path(model_root if model_root is not None else MODEL_ROOT).expanduser()
    known = dict(MODEL_DIRS if known_dirs is None else known_dirs)
    catalog = dict(known)
    known_paths = {_normalized_path(path) for path in known.values()}
    try:
        children = sorted(root.iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        return catalog
    for child in children:
        if not child.is_dir() or child.name.startswith("."):
            continue
        if _normalized_path(child) in known_paths:
            continue
        name = child.name
        if any(key.casefold() == name.casefold() for key in catalog):
            continue
        catalog[name] = child
    return catalog


def model_repo_for_path(
    model_dir: Path,
    known_dirs: dict[str, Path] | None = None,
    known_repos: dict[str, str] | None = None,
) -> str | None:
    known = MODEL_DIRS if known_dirs is None else known_dirs
    repos = MODEL_REPOS if known_repos is None else known_repos
    target = _normalized_path(model_dir)
    for name, path in known.items():
        if _normalized_path(path) == target:
            return repos.get(name)
    manifest = Path(model_dir) / MODEL_MANIFEST_NAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    repo_id = str(data.get("repo_id") or "").strip()
    return repo_id or None


def _normalized_path(path: Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(Path(path).expanduser())))


def normalize_thinking_effort(value: str) -> str:
    effort = str(value).strip().lower()
    effort = THINKING_EFFORT_ALIASES.get(effort, effort)
    if effort not in THINKING_EFFORTS:
        raise ValueError("effort must be off, on, low, medium, or xhigh")
    return effort


def normalize_generation_effort(value: str) -> str:
    effort = str(value).strip().lower()
    effort = GENERATION_EFFORT_ALIASES.get(effort, effort)
    if effort not in GENERATION_EFFORTS:
        raise ValueError("effort must be low, medium, high, or custom")
    return effort


def thinking_efforts_for_model(model_dir: Path | None) -> tuple[str, ...]:
    """Return only effort values implemented by the model chat template."""
    if model_dir is None:
        return BINARY_THINKING_EFFORTS
    root = Path(model_dir)
    for path in (root / "chat_template.jinja", root / "tokenizer_config.json"):
        try:
            template = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if "reasoning_effort" in template and all(
            value in template for value in ("low", "medium", "xhigh")
        ):
            return GRADED_THINKING_EFFORTS
    return BINARY_THINKING_EFFORTS


def resolve_thinking_effort(value: str, supported: tuple[str, ...]) -> str:
    effort = normalize_thinking_effort(value)
    if effort in supported:
        return effort
    if effort == "on" and "xhigh" in supported:
        return "xhigh"
    raise ValueError(f"model supports thinking: {', '.join(supported)}")


def coerce_thinking_effort(value: str, supported: tuple[str, ...]) -> str:
    """Translate saved effort when switching between graded and binary models."""
    effort = normalize_thinking_effort(value)
    try:
        return resolve_thinking_effort(effort, supported)
    except ValueError:
        if effort != "off" and "on" in supported:
            return "on"
        raise


def normalize_knowledge_mode(value: str) -> str:
    mode = str(value).strip().lower()
    if mode not in KNOWLEDGE_MODES:
        raise ValueError("knowledge mode must be offline, auto, or web")
    return mode


def normalize_auto_compact(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on", "auto"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("auto compact must be on or off")


def normalize_duck_mode(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("duck mode must be on or off")


def generation_settings(
    model_name: str,
    profile: str = "general",
    thinking_effort: str = DEFAULT_THINKING_EFFORT,
    *,
    graded_reasoning: bool = False,
    generation_effort: str = DEFAULT_GENERATION_EFFORT,
) -> dict[str, float | int]:
    name = model_name.lower()
    if "ornith" in name:
        key = "ornith"
    elif "qwen3.8" in name:
        key = "qwen38"
    elif "qwen" in name:
        key = "qwen"
    elif "gemma" in name:
        key = "gemma"
    else:
        key = ""
    effort = normalize_generation_effort(generation_effort)
    if effort not in {"medium", "custom"}:
        direct_qwen = key == "qwen" and normalize_thinking_effort(thinking_effort) == "off"
        if effort == "low":
            profile = "general" if direct_qwen else "coding"
        else:
            profile = "coding" if direct_qwen else "general"
    settings = dict(DEFAULT_GENERATION_SETTINGS)
    if key == "qwen":
        effort = normalize_thinking_effort(thinking_effort)
        if effort not in BINARY_THINKING_EFFORTS:
            effort = "on"
        settings.update(QWEN_GENERATION_SETTINGS[effort].get(profile, {}))
    elif key == "qwen38" and graded_reasoning:
        effort = normalize_thinking_effort(thinking_effort)
        profile_settings = {
            "temperature": 0.7 if effort == "off" else 1.0,
            "top_p": 0.8 if effort == "off" else 0.95,
            "top_k": 20,
            "min_p": 0.0,
            "presence_penalty": 1.5 if effort == "off" else 0.0,
            "repetition_penalty": 1.0,
        }
        settings.update(profile_settings)
    else:
        settings.update(MODEL_GENERATION_SETTINGS.get(key, {}).get(profile, {}))
    return settings


def package_install_command() -> str:
    python = "python" if os.name == "nt" else "python3"
    return f"{python} -m pip install openvino-genai huggingface_hub prompt_toolkit rich"
