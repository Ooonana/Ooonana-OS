from __future__ import annotations

import ctypes
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


CommandRunner = Callable[[str], str]


@dataclass(frozen=True)
class ModelMemoryEstimate:
    model_bytes: int
    kv_cache_bytes: int
    total_bytes: int


def estimate_model_memory(
    model_dir: Path,
    context_length: int,
    kv_cache_precision: str = "auto",
) -> ModelMemoryEstimate:
    model_bytes = _dir_size(model_dir)
    kv_cache_bytes = _estimate_kv_cache_bytes(model_dir, context_length, kv_cache_precision)
    return ModelMemoryEstimate(
        model_bytes=model_bytes,
        kv_cache_bytes=kv_cache_bytes,
        total_bytes=model_bytes + kv_cache_bytes,
    )


def format_perf_status(
    device: str,
    model_dir: Path,
    context_length: int,
    ram_text: str | None = None,
    cpu_text: str | None = None,
    gpu_text: str | None = None,
    kv_cache_precision: str = "auto",
) -> str:
    estimate = estimate_model_memory(model_dir, context_length, kv_cache_precision)
    return "\n".join(
        [
            f"device={device}",
            f"ctx={context_length}",
            f"kv_precision={kv_cache_precision}",
            f"est_ram={human_bytes(estimate.total_bytes)}",
            f"model={human_bytes(estimate.model_bytes)}",
            f"kv_cache={human_bytes(estimate.kv_cache_bytes)}",
            ram_text or get_ram_usage(),
            cpu_text or get_cpu_usage(),
            gpu_text or get_gpu_usage(),
        ]
    )


def format_live_status(
    device: str,
    context_length: int,
    process_ram_text: str | None = None,
    ram_text: str | None = None,
    cpu_text: str | None = None,
    gpu_text: str | None = None,
    kv_cache_precision: str = "auto",
) -> str:
    lines = [
        f"device: {device}",
        f"ctx: {context_length}",
        f"kv: {kv_cache_precision}",
        _colon_status(process_ram_text or get_process_ram_usage()),
        _colon_status(ram_text or get_ram_usage()),
    ]
    device_name = device.upper()
    if "GPU" in device_name:
        lines.append(_colon_status(gpu_text or get_gpu_usage()))
    elif "CPU" in device_name:
        lines.append(_colon_status(cpu_text or get_cpu_usage()))
    else:
        lines.append(_colon_status(cpu_text or get_cpu_usage()))
        lines.append(_colon_status(gpu_text or get_gpu_usage()))
    return "\n".join(lines)


def get_ram_usage() -> str:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    ok = ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    if not ok:
        return "ram=unknown"
    used = status.ullTotalPhys - status.ullAvailPhys
    return f"ram={human_bytes(used)} / {human_bytes(status.ullTotalPhys)} ({status.dwMemoryLoad}%)"


def get_process_ram_usage(
    runner: CommandRunner | None = None,
    working_set_getter: Callable[[], int | None] | None = None,
) -> str:
    getter = working_set_getter or _get_process_working_set_bytes
    try:
        working_set = getter()
    except Exception:
        working_set = None
    if working_set is not None:
        return f"proc ram: {human_bytes(working_set)}"

    run = runner or _run_powershell
    try:
        raw = run(f"(Get-Process -Id {os.getpid()}).WorkingSet64")
        value = int(float(raw.strip().splitlines()[-1]))
    except Exception:
        return "proc ram: unavailable"
    return f"proc ram: {human_bytes(value)}"


def get_process_working_set_bytes() -> int | None:
    return _get_process_working_set_bytes()


def _get_process_working_set_bytes() -> int | None:
    try:
        if not hasattr(ctypes, "windll"):
            return None

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            return None
        return int(counters.WorkingSetSize)
    except Exception:
        return None


def get_cpu_usage(runner: CommandRunner | None = None) -> str:
    run = runner or _run_powershell
    try:
        raw = run("(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average")
        value = float(raw.strip().splitlines()[-1])
    except Exception:
        return "cpu=unknown"
    return f"cpu={value:g}%"


def get_gpu_usage(runner: CommandRunner | None = None) -> str:
    run = runner or _run_powershell
    command = (
        "$vals=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' "
        "-ErrorAction SilentlyContinue).CounterSamples.CookedValue; "
        "($vals | Measure-Object -Sum).Sum"
    )
    try:
        raw = run(command)
        values = [float(line.strip()) for line in raw.splitlines() if line.strip()]
        value = sum(values)
    except Exception:
        return "gpu=unknown"
    return f"gpu={value:.1f}%"


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def _estimate_kv_cache_bytes(
    model_dir: Path,
    context_length: int,
    kv_cache_precision: str = "auto",
) -> int:
    config = _read_model_config(model_dir)
    if not config:
        bytes_per_value = _kv_precision_bytes(kv_cache_precision, 2)
        return int(max(context_length, 0) * 40 * 4096 * 2 * bytes_per_value)
    text_config = config.get("text_config") if isinstance(config.get("text_config"), dict) else config
    layers = _full_attention_layers(text_config)
    kv_heads = int(text_config.get("num_key_value_heads") or text_config.get("num_attention_heads") or 1)
    head_dim = int(text_config.get("head_dim") or 0)
    if head_dim <= 0:
        hidden_size = int(text_config.get("hidden_size") or 4096)
        attn_heads = max(int(text_config.get("num_attention_heads") or 1), 1)
        head_dim = max(hidden_size // attn_heads, 1)
    bytes_per_value = _dtype_bytes(str(text_config.get("dtype") or config.get("dtype") or "float16"))
    bytes_per_value = _kv_precision_bytes(kv_cache_precision, bytes_per_value)
    return int(max(context_length, 0) * layers * kv_heads * head_dim * 2 * bytes_per_value)


def _kv_precision_bytes(precision: str, default: int) -> float:
    return {
        "u4": 0.5,
        "u8": 1.0,
        "f16": 2.0,
    }.get(str(precision).lower(), float(default))


def _read_model_config(model_dir: Path) -> dict:
    try:
        return json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _full_attention_layers(config: dict) -> int:
    layer_types = config.get("layer_types")
    if isinstance(layer_types, list) and layer_types:
        return max(sum(1 for layer in layer_types if str(layer).lower() == "full_attention"), 1)
    return max(int(config.get("num_hidden_layers") or 40), 1)


def _dtype_bytes(dtype: str) -> int:
    lower = dtype.lower()
    if "float32" in lower or lower in {"fp32", "f32"}:
        return 4
    if "int8" in lower or lower in {"i8", "uint8", "u8"}:
        return 1
    return 2


def _run_powershell(command: str) -> str:
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        text=True,
        capture_output=True,
        timeout=5,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    return completed.stdout


def _colon_status(text: str) -> str:
    if ": " in text:
        return text.replace("_", " ")
    if "=" not in text:
        return text.replace("_", " ")
    key, value = text.split("=", 1)
    return f"{key.replace('_', ' ')}: {value}"
