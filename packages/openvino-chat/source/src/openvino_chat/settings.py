from __future__ import annotations

import os
from pathlib import Path

DEFAULT_OPENVINO_HOME = (
    Path("F:/7ryan/Downloads/.openvino")
    if os.name == "nt"
    else Path.home() / ".openvino"
)
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

MODEL_REPOS = {
    "qwen": "OpenVINO/Qwen3.5-9B-int4-ov",
    "tiny": "HarmenWessels/gemma-4-E2B-it-qat-int4-ov",
    "glm": "zai-org/GLM-4.1V-9B-Thinking",
    "gemma": "OpenVINO/gemma-4-E4B-it-int4-ov",
}
MODEL_DIRS = {
    "qwen": MODEL_ROOT / "qwen3.5-9b-int4-ov",
    "tiny": MODEL_ROOT / "gemma-4-e2b-it-qat-int4-ov",
    "glm": MODEL_ROOT / "glm-4.1v-9b-thinking-int4-ov",
    "gemma": MODEL_ROOT / "gemma-4-e4b-it-int4-ov",
}
MODEL_EXPORT_REQUIRED = {
    "glm": "GLM-4.1V-9B-Thinking has no ready OpenVINO snapshot configured; export it with the OpenVINO GLM4V notebook into the glm model path first.",
}
DEFAULT_MODEL = "qwen"
DEFAULT_REPO_ID = MODEL_REPOS[DEFAULT_MODEL]
DEFAULT_MODEL_DIR = MODEL_DIRS[DEFAULT_MODEL]


def package_install_command() -> str:
    if os.name != "nt":
        return "python3 -m pip install openvino-genai huggingface_hub prompt_toolkit rich"
    return (
        '& "F:\\LM\\.venv\\Scripts\\python.exe" -m pip install '
        "openvino-genai huggingface_hub"
    )
