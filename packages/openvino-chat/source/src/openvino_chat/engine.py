from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from openvino_chat.settings import package_install_command


TokenCallback = Callable[[str], None]


class OpenVinoChatEngine:
    def __init__(
        self,
        pipeline: Any,
        device: str,
        model_name: str = "model",
        kv_cache_precision: str = "auto",
    ) -> None:
        self._pipeline = pipeline
        self.device = device
        self.model_name = model_name
        self.kv_cache_precision = kv_cache_precision
        self._tokenizer: Any = None
        self._tokenizer_checked = False

    def count_tokens(self, text: str) -> int:
        tokenizer = self._get_tokenizer()
        if tokenizer is not None:
            try:
                max_length = max(1024, len(text.encode("utf-8")) + 16)
                encoded = tokenizer.encode(
                    text,
                    add_special_tokens=False,
                    max_length=max_length,
                )
                input_ids = getattr(encoded, "input_ids", encoded)
                shape = getattr(input_ids, "shape", None)
                if shape is None and hasattr(input_ids, "get_shape"):
                    shape = input_ids.get_shape()
                if shape:
                    return max(0, int(shape[-1]))
            except Exception:
                pass
        return _estimated_token_count(text)

    def _get_tokenizer(self) -> Any:
        if not self._tokenizer_checked:
            self._tokenizer_checked = True
            getter = getattr(self._pipeline, "get_tokenizer", None)
            if callable(getter):
                try:
                    self._tokenizer = getter()
                except Exception:
                    self._tokenizer = None
        return self._tokenizer

    def format_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> str | None:
        tokenizer = self._get_tokenizer()
        formatter = getattr(tokenizer, "apply_chat_template", None)
        if not callable(formatter):
            return None
        try:
            kwargs: dict[str, Any] = {"add_generation_prompt": True}
            if tools:
                kwargs["tools"] = tools
            return str(formatter(messages, **kwargs))
        except Exception:
            return None

    def generate(
        self,
        prompt: str,
        on_token: TokenCallback | None = None,
        should_stop: Callable[[], bool] | None = None,
        max_new_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.9,
        context_length: int | None = None,
    ) -> str:
        chunks: list[str] = []

        def streamer(token: str) -> bool:
            chunks.append(token)
            if on_token is not None:
                on_token(token)
            return bool(should_stop and should_stop())

        effective_max_new_tokens = max(1, int(max_new_tokens))
        if context_length is not None:
            context_limit = max(2, int(context_length))
            prompt_tokens = self.count_tokens(prompt)
            available_tokens = context_limit - prompt_tokens
            if available_tokens <= 0:
                raise ValueError(
                    f"prompt uses {prompt_tokens} tokens, exceeding ctx={context_limit}"
                )
            effective_max_new_tokens = min(effective_max_new_tokens, available_tokens)

        kwargs = {
            "max_new_tokens": effective_max_new_tokens,
            "do_sample": temperature > 0,
            "temperature": temperature,
            "top_p": top_p,
        }
        if on_token is not None:
            kwargs["streamer"] = streamer
        result = self._pipeline.generate(prompt, **kwargs)
        if chunks:
            return "".join(chunks)
        return _result_text(result)


def load_engine(
    model_dir: Path,
    device: str = "GPU",
    fallback_device: str = "CPU",
    pipeline_cls: type | None = None,
    kv_cache_precision: str = "auto",
) -> OpenVinoChatEngine:
    pipeline_type = pipeline_cls or _pipeline_cls(model_dir)
    first_device = device.upper()
    second_device = fallback_device.upper()
    model_name = _model_name(model_dir)
    kv_precision = normalize_kv_cache_precision(kv_cache_precision)
    properties = {} if kv_precision == "auto" else {"KV_CACHE_PRECISION": kv_precision}
    try:
        pipeline = pipeline_type(model_dir, first_device, **properties)
        return OpenVinoChatEngine(pipeline, first_device, model_name, kv_precision)
    except Exception:
        if first_device == second_device:
            raise
        pipeline = pipeline_type(model_dir, second_device, **properties)
        return OpenVinoChatEngine(pipeline, second_device, model_name, kv_precision)


def normalize_kv_cache_precision(value: str | None) -> str:
    normalized = str(value or "auto").strip().lower()
    if normalized not in {"auto", "u4", "u8", "f16"}:
        raise ValueError("kv precision must be auto, u4, u8, or f16")
    return normalized


def _pipeline_cls(model_dir: Path) -> type:
    try:
        import openvino_genai as ov_genai
    except ImportError as exc:
        raise RuntimeError(
            "missing package: install with " + package_install_command()
        ) from exc
    if (model_dir / "openvino_model.xml").exists():
        return ov_genai.LLMPipeline
    return ov_genai.VLMPipeline


def _model_name(model_dir: Path) -> str:
    name = model_dir.name.lower()
    if "glm" in name:
        return "GLM"
    if "gemma" in name:
        return "Gemma"
    if "qwen" in name:
        return "Qwen"
    return model_dir.name


def model_name_from_dir(model_dir: Path) -> str:
    return _model_name(model_dir)


def _result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text
    texts = getattr(result, "texts", None)
    if isinstance(texts, list) and texts:
        return str(texts[0])
    return str(result)


def _estimated_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text.encode("utf-8")) + 2) // 3)
