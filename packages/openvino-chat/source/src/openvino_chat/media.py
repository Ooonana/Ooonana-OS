from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = frozenset({".bmp", ".jpeg", ".jpg", ".png", ".webp"})
VIDEO_EXTENSIONS = frozenset({".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"})
AUDIO_EXTENSIONS = frozenset({".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"})
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

_QUOTED_PATH = re.compile(r"(?P<quote>['\"])(?P<path>.+?)(?P=quote)")
_WINDOWS_PATH = re.compile(
    r"(?<!\w)([A-Za-z]:[\\/][^\r\n]*?\.(?:bmp|jpe?g|png|webp|avi|m4v|mkv|mov|mp4|webm|flac|m4a|mp3|ogg|opus|wav))(?=\s|$)",
    re.IGNORECASE,
)
_PLAIN_PATH = re.compile(
    r"(?<!\S)((?:\.?\.?[\\/])?[^\s'\"]+\.(?:bmp|jpe?g|png|webp|avi|m4v|mkv|mov|mp4|webm|flac|m4a|mp3|ogg|opus|wav))(?=\s|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MediaInputs:
    images: tuple[Any, ...] = ()
    videos: tuple[Any, ...] = ()
    audios: tuple[Any, ...] = ()
    paths: tuple[Path, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.images or self.videos or self.audios)

    @property
    def summary(self) -> str:
        parts = []
        if self.images:
            parts.append(f"{len(self.images)} image")
        if self.videos:
            parts.append(f"{len(self.videos)} video")
        if self.audios:
            parts.append(f"{len(self.audios)} audio")
        return ", ".join(parts)


def extract_media_paths(text: str, base_dir: Path | None = None) -> list[Path]:
    """Find existing media paths in terminal input, including drag-and-drop paths."""
    value = str(text or "")
    root = (base_dir or Path.cwd()).resolve()
    candidates: list[str] = []
    candidates.extend(match.group("path") for match in _QUOTED_PATH.finditer(value))
    candidates.extend(match.group(1) for match in _WINDOWS_PATH.finditer(value))
    candidates.extend(match.group(1) for match in _PLAIN_PATH.finditer(value))

    found: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        clean = candidate.strip().rstrip(".,;:!?)]]}")
        path = Path(clean).expanduser()
        if not path.is_absolute():
            path = root / path
        try:
            resolved = path.resolve()
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if (
            key not in seen
            and resolved.suffix.lower() in MEDIA_EXTENSIONS
            and resolved.is_file()
        ):
            seen.add(key)
            found.append(resolved)
    return found


def model_media_capabilities(model_dir: Path | None, pipeline: Any) -> frozenset[str]:
    capabilities = {"text"}
    if model_dir is None:
        return frozenset(capabilities)
    model_dir = Path(model_dir)
    pipeline_type = pipeline if isinstance(pipeline, type) else type(pipeline)
    pipeline_name = pipeline_type.__name__.lower()
    visual = "vlmpipeline" in pipeline_name or (
        (model_dir / "openvino_vision_embeddings_model.xml").is_file()
        and (model_dir / "openvino_language_model.xml").is_file()
    )
    config = _model_config(model_dir)
    if visual:
        capabilities.add("image")
        if config.get("video_token_id") is not None or config.get("model_type") in {
            "gemma4",
            "qwen3_5",
        }:
            capabilities.add("video")
    generate_doc = str(getattr(getattr(pipeline_type, "generate", None), "__doc__", "") or "")
    if visual and config.get("audio_config") is not None and "audios" in generate_doc:
        capabilities.add("audio")
    return frozenset(capabilities)


def prepare_media_inputs(
    paths: list[Path] | tuple[Path, ...],
    *,
    capabilities: frozenset[str],
    model_dir: Path | None,
) -> MediaInputs:
    images: list[Any] = []
    videos: list[Any] = []
    audios: list[Any] = []
    resolved = tuple(Path(path).resolve() for path in paths)
    for path in resolved:
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            _require_modality("image", capabilities, path)
            images.append(_read_image_tensor(path))
        elif suffix in VIDEO_EXTENSIONS:
            _require_modality("video", capabilities, path)
            videos.append(_read_video_tensor(path))
        elif suffix in AUDIO_EXTENSIONS:
            _require_modality("audio", capabilities, path)
            audios.append(_read_audio_tensor(path, _audio_sample_rate(model_dir)))
    return MediaInputs(tuple(images), tuple(videos), tuple(audios), resolved)


def _require_modality(modality: str, capabilities: frozenset[str], path: Path) -> None:
    if modality in capabilities:
        return
    if modality == "audio":
        raise ValueError(
            f"audio input is not available in this OpenVINO export/runtime: {path.name}"
        )
    raise ValueError(f"current model does not support {modality} input: {path.name}")


def _read_image_tensor(path: Path) -> Any:
    import numpy as np
    from openvino import Tensor
    from PIL import Image

    with Image.open(path) as source:
        pixels = np.asarray(source.convert("RGB"), dtype=np.uint8)
    return Tensor(pixels)


def _read_video_tensor(path: Path, max_frames: int = 60) -> Any:
    try:
        import imageio.v3 as iio
        import numpy as np
        from openvino import Tensor
    except ImportError as exc:
        raise RuntimeError(
            "video input needs imageio and imageio-ffmpeg; reinstall OpenVINO Chat"
        ) from exc

    try:
        metadata = iio.immeta(path, plugin="FFMPEG")
    except Exception:
        metadata = {}
    try:
        fps = max(1.0, float(metadata.get("fps") or 1.0))
    except (TypeError, ValueError):
        fps = 1.0
    step = max(1, round(fps))
    frames = []
    for index, frame in enumerate(iio.imiter(path, plugin="FFMPEG")):
        if index % step:
            continue
        pixels = np.asarray(frame, dtype=np.uint8)
        if pixels.ndim == 2:
            pixels = np.repeat(pixels[..., None], 3, axis=2)
        elif pixels.shape[-1] > 3:
            pixels = pixels[..., :3]
        frames.append(pixels)
        if len(frames) >= max_frames:
            break
    if not frames:
        raise ValueError(f"video has no readable frames: {path.name}")
    return Tensor(np.stack(frames))


def _read_audio_tensor(path: Path, sample_rate: int) -> Any:
    try:
        import numpy as np
        import soundfile as sf
        from openvino import Tensor
    except ImportError as exc:
        raise RuntimeError("audio input needs soundfile; reinstall OpenVINO Chat") from exc

    samples, source_rate = sf.read(path, dtype="float32", always_2d=False)
    data = np.asarray(samples, dtype=np.float32)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if source_rate != sample_rate and data.size:
        duration = data.size / float(source_rate)
        target_size = max(1, round(duration * sample_rate))
        source_x = np.linspace(0.0, duration, num=data.size, endpoint=False)
        target_x = np.linspace(0.0, duration, num=target_size, endpoint=False)
        data = np.interp(target_x, source_x, data).astype(np.float32)
    data = data[: sample_rate * 30]
    return Tensor(data.reshape(1, -1))


def _audio_sample_rate(model_dir: Path | None) -> int:
    if model_dir is None:
        return 16000
    try:
        processor = json.loads((Path(model_dir) / "processor_config.json").read_text("utf-8"))
        return max(1000, int(processor["feature_extractor"]["sampling_rate"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return 16000


def _model_config(model_dir: Path) -> dict[str, Any]:
    try:
        value = json.loads((model_dir / "config.json").read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
