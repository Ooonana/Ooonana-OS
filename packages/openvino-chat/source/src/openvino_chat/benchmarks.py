from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

from openvino_chat.engine import GenerationMetrics
from openvino_chat.perf import get_process_working_set_bytes, human_bytes
from openvino_chat.settings import BENCHMARK_PATH
from openvino_chat.state_io import read_json, write_bytes


_STORE_LOCK = threading.Lock()
MAX_BENCHMARK_BYTES = 16 * 1024 * 1024
_COUNT_FIELDS = ("context_length", "samples", "input_tokens", "output_tokens", "ttft_samples", "peak_process_ram_bytes")
_TIME_FIELDS = ("elapsed_seconds", "ttft_seconds", "best_tokens_per_second")


def benchmark_path() -> Path:
    configured = os.environ.get("OPENVINO_CHAT_BENCHMARK_PATH")
    if configured:
        return Path(configured).expanduser()
    configured_home = os.environ.get("OPENVINO_HOME")
    if configured_home:
        return Path(configured_home).expanduser() / "benchmarks.json"
    return BENCHMARK_PATH


class BenchmarkStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else benchmark_path()
        self.last_error: str | None = None

    def record(
        self,
        model_dir: Path,
        device: str,
        kv_cache_precision: str,
        context_length: int,
        metrics: GenerationMetrics,
    ) -> dict[str, Any]:
        key = _profile_key(model_dir, device, kv_cache_precision, context_length)
        with _STORE_LOCK:
            payload = self._read(strict=True)
            profiles = payload.setdefault("profiles", {})
            profile = profiles.setdefault(
                key,
                {
                    "model": Path(model_dir).name,
                    "device": str(device).upper(),
                    "kv_cache_precision": str(kv_cache_precision).lower(),
                    "context_length": int(context_length),
                    "samples": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "elapsed_seconds": 0.0,
                    "ttft_samples": 0,
                    "ttft_seconds": 0.0,
                    "peak_process_ram_bytes": 0,
                    "best_tokens_per_second": 0.0,
                },
            )
            for field in _COUNT_FIELDS:
                profile.setdefault(field, int(context_length) if field == "context_length" else 0)
            for field in _TIME_FIELDS:
                profile.setdefault(field, 0.0)
            profile["samples"] += 1
            profile["input_tokens"] += int(metrics.input_tokens)
            profile["output_tokens"] += int(metrics.output_tokens)
            profile["elapsed_seconds"] += float(metrics.elapsed_seconds)
            if metrics.ttft_seconds is not None:
                profile["ttft_samples"] += 1
                profile["ttft_seconds"] += float(metrics.ttft_seconds)
            process_ram = get_process_working_set_bytes() or 0
            profile["peak_process_ram_bytes"] = max(
                int(profile.get("peak_process_ram_bytes") or 0),
                int(process_ram),
            )
            profile["best_tokens_per_second"] = max(
                float(profile.get("best_tokens_per_second") or 0.0),
                float(metrics.tokens_per_second),
            )
            profile["last"] = {
                "input_tokens": int(metrics.input_tokens),
                "output_tokens": int(metrics.output_tokens),
                "elapsed_seconds": round(float(metrics.elapsed_seconds), 6),
                "ttft_seconds": (
                    round(float(metrics.ttft_seconds), 6)
                    if metrics.ttft_seconds is not None
                    else None
                ),
                "tokens_per_second": round(float(metrics.tokens_per_second), 4),
                "process_ram_bytes": int(process_ram),
            }
            self._write(payload)
            return dict(profile)

    def get(
        self,
        model_dir: Path,
        device: str,
        kv_cache_precision: str,
        context_length: int,
    ) -> dict[str, Any] | None:
        key = _profile_key(model_dir, device, kv_cache_precision, context_length)
        with _STORE_LOCK:
            profile = self._read().get("profiles", {}).get(key)
        return dict(profile) if isinstance(profile, dict) else None

    def format_profile(self, profile: dict[str, Any]) -> str:
        samples = max(1, int(profile.get("samples") or 0))
        output_tokens = int(profile.get("output_tokens") or 0)
        elapsed = max(float(profile.get("elapsed_seconds") or 0.0), 0.000001)
        ttft_samples = int(profile.get("ttft_samples") or 0)
        ttft = float(profile.get("ttft_seconds") or 0.0)
        lines = [
            f"profile_samples={samples}",
            f"profile_tokens_per_sec={output_tokens / elapsed:.2f}",
            f"profile_best_tokens_per_sec={float(profile.get('best_tokens_per_second') or 0.0):.2f}",
        ]
        if ttft_samples:
            lines.append(f"profile_ttft={ttft / ttft_samples:.3f}s")
        peak_ram = int(profile.get("peak_process_ram_bytes") or 0)
        if peak_ram:
            lines.append(f"profile_peak_proc_ram={human_bytes(peak_ram)}")
        lines.append(f"profile_saved={self.path}")
        return "\n".join(lines)

    def _read(self, *, strict: bool = False) -> dict[str, Any]:
        try:
            payload = read_json(self.path, MAX_BENCHMARK_BYTES)
            if not isinstance(payload, dict) or type(payload.get("version", 1)) is not int or payload.get("version", 1) != 1:
                raise ValueError("invalid benchmark record")
            profiles = payload.get("profiles", {})
            if not isinstance(profiles, dict):
                raise ValueError("invalid benchmark profiles")
            for profile in profiles.values():
                if not isinstance(profile, dict):
                    raise ValueError("invalid benchmark profile")
                for field in _COUNT_FIELDS + _TIME_FIELDS:
                    value = profile.get(field, 0)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or not math.isfinite(value):
                        raise ValueError("invalid benchmark metric")
                    if field in _COUNT_FIELDS and type(value) is not int:
                        raise ValueError("invalid benchmark counter")
            self.last_error = None
            return payload
        except FileNotFoundError:
            self.last_error = None
        except (OSError, ValueError, TypeError, OverflowError) as error:
            self.last_error = str(error)
            if strict:
                raise ValueError("benchmark record unreadable; original preserved") from error
        return {"version": 1, "profiles": {}}

    def _write(self, payload: dict[str, Any]) -> None:
        encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        write_bytes(self.path, encoded, MAX_BENCHMARK_BYTES)


def _profile_key(
    model_dir: Path,
    device: str,
    kv_cache_precision: str,
    context_length: int,
) -> str:
    return "|".join(
        [
            Path(model_dir).name.lower(),
            str(device).upper(),
            str(kv_cache_precision).lower(),
            str(int(context_length)),
        ]
    )
