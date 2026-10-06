"""Read-only model memory estimates. Swap is reported, never counted as RAM."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import os
from pathlib import Path

from .cgroup_memory import constrain_memory
from .perf import _estimate_kv_cache_bytes

MIB = 1024 * 1024


@dataclass(frozen=True)
class MemoryEstimate:
    total_ram: int
    available_ram: int
    swap_free: int
    weights: int
    estimated_kv: int
    overhead: int
    context: int
    recommended_context: int

    @property
    def estimated_required(self) -> int:
        return self.weights + self.estimated_kv + self.overhead

    def report(self) -> dict:
        return {**asdict(self), "estimated_required": self.estimated_required,
                "fits_available_ram": self.estimated_required <= self.available_ram,
                "estimate_only": True, "swap_is_physical_ram": False}

    def message(self) -> str:
        return (f"Model weights {self.weights / MIB:.0f} MiB; estimated total {self.estimated_required / MIB:.0f} MiB "
                f"at context {self.context}. Physical RAM available {self.available_ram / MIB:.0f} / "
                f"{self.total_ram / MIB:.0f} MiB; swap free {self.swap_free / MIB:.0f} MiB (not extra RAM). "
                f"Suggested context ceiling {self.recommended_context}. Choose a smaller INT4 model, reduce context, "
                "or use supported u8/u4 KV cache settings. Estimates do not guarantee allocation succeeds.")


def memory_snapshot(*, membership=Path("/proc/self/cgroup"),
                    mountinfo=Path("/proc/self/mountinfo"), cgroup_root=None) -> tuple[int, int, int]:
    try:
        import psutil
        memory, swap = psutil.virtual_memory(), psutil.swap_memory()
        total, available, swap_free = int(memory.total), int(memory.available), int(swap.free)
    except ImportError:
        data = {}
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                data[key] = int(value.split()[0]) * 1024
        except (OSError, ValueError):
            return 0, 0, 0
        total, available, swap_free = data.get("MemTotal", 0), data.get("MemAvailable", data.get("MemFree", 0)), data.get("SwapFree", 0)
    total, available = constrain_memory(total, available, membership, mountinfo, cgroup_root)
    return total, available, max(0, swap_free)


def estimate_memory(model_dir: Path, context: int = 4096, kv_precision: str = "auto", snapshot=None) -> MemoryEstimate:
    context = max(2, int(context))
    weights, seen = 0, set()
    for path in Path(model_dir).rglob("*.bin"):
        if not path.is_file():
            continue
        info = path.stat()
        key = info.st_dev, info.st_ino
        if key not in seen:
            weights += info.st_size
            seen.add(key)
    per_token = _estimate_kv_cache_bytes(Path(model_dir), 1, kv_precision)
    total, available, swap_free = snapshot or memory_snapshot()
    overhead = max(256 * MIB, weights // 5) if weights else 0
    room = max(0, available - weights - overhead)
    recommended = min(context, room // per_token) if per_token else context
    if recommended < 2:
        recommended = 0  # No supported context fits this allowance.
    return MemoryEstimate(total, available, swap_free, weights, per_token * context, overhead, context, recommended)


def preflight_model(model_dir: Path, context: int = 4096, kv_precision: str = "auto") -> MemoryEstimate:
    report = estimate_memory(model_dir, context, kv_precision)
    policy = os.environ.get("OPENVINO_MEMORY_POLICY", "warn").lower()
    if policy not in ("warn", "strict", "off"):
        raise ValueError("OPENVINO_MEMORY_POLICY must be warn, strict, or off")
    if policy != "off" and report.total_ram and report.weights and report.estimated_required > report.available_ram:
        if policy == "strict":
            raise MemoryError(report.message())
        logging.getLogger(__name__).warning("memory_preflight: %s", report.message())
    return report


def is_memory_error(error: Exception) -> bool:
    return isinstance(error, MemoryError) or any(word in str(error).lower() for word in (
        "out of memory", "bad_alloc", "cannot allocate memory", "failed to allocate memory", "cl_out_of_resources",
    ))
