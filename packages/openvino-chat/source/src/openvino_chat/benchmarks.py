from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from openvino_chat.engine import GenerationMetrics
from openvino_chat.perf import get_process_working_set_bytes, human_bytes
from openvino_chat.settings import BENCHMARK_PATH


_STORE_LOCK = threading.Lock()


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
            payload = self._read()
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

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("profiles", {}), dict):
                return payload
        except (OSError, ValueError, TypeError):
            pass
        return {"version": 1, "profiles": {}}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


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
