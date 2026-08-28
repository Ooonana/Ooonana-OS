from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openvino_chat.settings import (
    DEFAULT_GENERATION_EFFORT,
    DEFAULT_THINKING_EFFORT,
    GRADED_THINKING_EFFORTS,
    generation_settings,
    package_install_command,
    resolve_thinking_effort as resolve_model_thinking_effort,
    thinking_efforts_for_model,
)


TokenCallback = Callable[[str], None]


@dataclass(frozen=True)
class GenerationMetrics:
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float
    ttft_seconds: float | None
    tokens_per_second: float


class OpenVinoChatEngine:
    def __init__(
        self,
        pipeline: Any,
        device: str,
        model_name: str = "model",
        kv_cache_precision: str = "auto",
        model_dir: Path | None = None,
    ) -> None:
        self._pipeline = pipeline
        self.device = device
        self.model_name = model_name
        self.kv_cache_precision = kv_cache_precision
        self.model_dir = Path(model_dir) if model_dir is not None else None
        self.supported_thinking_efforts = thinking_efforts_for_model(self.model_dir)
        self._tokenizer: Any = None
        self._tokenizer_checked = False
        self.last_metrics: GenerationMetrics | None = None
        self._structured_tool_configs: dict[str, Any] = {}
        self._structured_tools_disabled = False

    @property
    def supports_graded_thinking(self) -> bool:
        return "xhigh" in self.supported_thinking_efforts

    def resolve_thinking_effort(self, value: str) -> str:
        return resolve_model_thinking_effort(value, self.supported_thinking_efforts)

    def _thinking_context(self, effort: str) -> dict[str, Any]:
        context: dict[str, Any] = {"enable_thinking": effort != "off"}
        if effort in GRADED_THINKING_EFFORTS and effort != "off":
            context["reasoning_effort"] = effort
        return context

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
        thinking_effort: str = DEFAULT_THINKING_EFFORT,
    ) -> str | None:
        tokenizer = self._get_tokenizer()
        formatter = getattr(tokenizer, "apply_chat_template", None)
        if not callable(formatter):
            return None
        effort = self.resolve_thinking_effort(thinking_effort)
        try:
            kwargs: dict[str, Any] = {
                "add_generation_prompt": True,
                "extra_context": self._thinking_context(effort),
            }
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
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        presence_penalty: float | None = None,
        repetition_penalty: float | None = None,
        generation_profile: str = "general",
        generation_effort: str = DEFAULT_GENERATION_EFFORT,
        thinking_effort: str = DEFAULT_THINKING_EFFORT,
        context_length: int | None = None,
    ) -> str:
        return self._generate_input(
            prompt,
            prompt_text=prompt,
            on_token=on_token,
            should_stop=should_stop,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            generation_profile=generation_profile,
            generation_effort=generation_effort,
            thinking_effort=thinking_effort,
            context_length=context_length,
        )

    def generate_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        thinking_effort: str = DEFAULT_THINKING_EFFORT,
        tool_choice: str = "auto",
        formatted_prompt: str | None = None,
        **generation_kwargs: Any,
    ) -> str:
        """Generate from native chat history so OpenVINO can reuse common KV state."""
        effort = self.resolve_thinking_effort(thinking_effort)
        prompt = formatted_prompt or self.format_chat(
            messages,
            tools=tools,
            thinking_effort=effort,
        )
        if not prompt:
            raise ValueError("model chat template is unavailable")
        try:
            import openvino_genai as ov_genai

            history = ov_genai.ChatHistory()
            history.set_messages(messages)
            if tools:
                history.set_tools(tools)
            history.set_extra_context(self._thinking_context(effort))
        except (ImportError, AttributeError, TypeError):
            return self.generate(prompt, thinking_effort=effort, **generation_kwargs)
        structured_tools = self._structured_tool_output(
            tools,
            require_tool=tool_choice == "required",
        )
        if structured_tools is not None:
            generation_kwargs.setdefault("structured_output_config", structured_tools)
        return self._generate_input(
            history,
            prompt_text=prompt,
            thinking_effort=effort,
            **generation_kwargs,
        )

    def _structured_tool_output(
        self,
        tools: list[dict[str, Any]] | None,
        *,
        require_tool: bool = False,
    ) -> Any | None:
        if self._structured_tools_disabled or not tools or "gemma" in self.model_name.lower():
            return None
        try:
            import openvino_genai as ov_genai

            structured = ov_genai.StructuredOutputConfig
        except (ImportError, AttributeError):
            return None
        key = ("required:" if require_tool else "auto:") + json.dumps(
            tools,
            sort_keys=True,
            separators=(",", ":"),
        )
        if key in self._structured_tool_configs:
            return self._structured_tool_configs[key]
        tags = []
        for tool in tools:
            function = tool.get("function") if isinstance(tool, dict) else None
            if not isinstance(function, dict) or not function.get("name"):
                continue
            schema = json.dumps(function.get("parameters") or {"type": "object"})
            tags.append(
                structured.Tag(
                    f"<tool_call>\n<function={function['name']}>\n",
                    structured.QwenXMLParametersFormat(schema),
                    "\n</function>\n</tool_call>",
                )
            )
        if not tags:
            return None
        config = ov_genai.StructuredOutputConfig()
        config.compound_grammar = structured.TriggeredTags(
            ["<tool_call>"],
            tags,
            at_least_one=require_tool,
            stop_after_first=True,
        )
        self._structured_tool_configs[key] = config
        return config

    def _generate_input(
        self,
        inputs: Any,
        *,
        prompt_text: str,
        on_token: TokenCallback | None = None,
        should_stop: Callable[[], bool] | None = None,
        max_new_tokens: int = 4096,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        min_p: float | None = None,
        presence_penalty: float | None = None,
        repetition_penalty: float | None = None,
        generation_profile: str = "general",
        generation_effort: str = DEFAULT_GENERATION_EFFORT,
        thinking_effort: str = DEFAULT_THINKING_EFFORT,
        context_length: int | None = None,
        structured_output_config: Any | None = None,
    ) -> str:
        chunks: list[str] = []
        started = time.perf_counter()
        first_token_at: float | None = None

        def streamer(token: str) -> bool:
            nonlocal first_token_at
            if first_token_at is None:
                first_token_at = time.perf_counter()
            chunks.append(token)
            if on_token is not None:
                on_token(token)
            return bool(should_stop and should_stop())

        effective_max_new_tokens = max(1, int(max_new_tokens))
        prompt_tokens = self.count_tokens(prompt_text)
        if context_length is not None:
            context_limit = max(2, int(context_length))
            available_tokens = context_limit - prompt_tokens
            if available_tokens <= 0:
                raise ValueError(
                    f"prompt uses {prompt_tokens} tokens, exceeding ctx={context_limit}"
                )
            effective_max_new_tokens = min(effective_max_new_tokens, available_tokens)

        effort = self.resolve_thinking_effort(thinking_effort)
        sampling = generation_settings(
            self.model_name,
            generation_profile,
            effort,
            graded_reasoning=self.supports_graded_thinking,
            generation_effort=generation_effort,
        )
        overrides = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "min_p": min_p,
            "presence_penalty": presence_penalty,
            "repetition_penalty": repetition_penalty,
        }
        sampling.update({key: value for key, value in overrides.items() if value is not None})
        effective_temperature = float(sampling["temperature"])
        kwargs = {
            "max_new_tokens": effective_max_new_tokens,
            "do_sample": effective_temperature > 0,
            **sampling,
        }
        if structured_output_config is not None:
            kwargs["structured_output_config"] = structured_output_config
        if on_token is not None:
            kwargs["streamer"] = streamer
        try:
            result = self._pipeline.generate(inputs, **kwargs)
        except RuntimeError as exc:
            if (
                structured_output_config is None
                or chunks
                or not _is_structured_grammar_error(exc)
            ):
                raise
            self._structured_tools_disabled = True
            kwargs.pop("structured_output_config", None)
            started = time.perf_counter()
            first_token_at = None
            result = self._pipeline.generate(inputs, **kwargs)
        text = "".join(chunks) if chunks else _result_text(result)
        elapsed = max(time.perf_counter() - started, 0.000001)
        output_tokens = self.count_tokens(text)
        self.last_metrics = GenerationMetrics(
            input_tokens=prompt_tokens,
            output_tokens=output_tokens,
            elapsed_seconds=elapsed,
            ttft_seconds=(first_token_at - started) if first_token_at is not None else None,
            tokens_per_second=output_tokens / elapsed,
        )
        return text


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
        return OpenVinoChatEngine(
            pipeline,
            first_device,
            model_name,
            kv_precision,
            model_dir=model_dir,
        )
    except Exception:
        if first_device == second_device:
            raise
        pipeline = pipeline_type(model_dir, second_device, **properties)
        return OpenVinoChatEngine(
            pipeline,
            second_device,
            model_name,
            kv_precision,
            model_dir=model_dir,
        )


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
    if "gemma" in name:
        return "Gemma"
    if "ornith" in name:
        return "Ornith"
    if "qwen3.8" in name or "qwen38" in name:
        return "Qwen3.8"
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


def _is_structured_grammar_error(exc: RuntimeError) -> bool:
    message = str(exc).lower()
    return "ebnf parser error" in message or "grammar parser error" in message
