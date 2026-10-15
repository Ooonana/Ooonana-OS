"""Presentation only. Never probe services, infer hardware health or change state."""
import json
import math


def size_text(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Not reported"
    if value < 0 or value > 2**63 or not math.isfinite(value):
        return "Not reported"
    for unit, divisor in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if value >= divisor:
            return f"{value / divisor:.1f} {unit}"
    return f"{value:.0f} B"


def format_snapshot(output):
    try:
        report = json.loads(output)
    except (ValueError, TypeError, RecursionError):
        return None
    if not isinstance(report, dict) or not isinstance(report.get("kernel"), str) or not report["kernel"]:
        return None
    if not isinstance(report.get("services"), dict) or not isinstance(report.get("memory_bytes"), dict):
        return None
    lines, attention = [], []

    def value(item):
        return item if isinstance(item, str) and item else "Not reported"

    def names(items):
        return ", ".join(items) if isinstance(items, list) and all(isinstance(item, str) for item in items) and items else "None reported"

    def yes_no(item):
        return "Yes" if item is True else "No" if item is False else "Not reported"

    lines.extend(["System", f"Kernel: {value(report['kernel'])}",
                  f"Architecture: {value(report.get('architecture'))}", f"Session: {value(report.get('mode'))}",
                  f"WSL: {yes_no(report.get('wsl'))}", f"Restart required: {yes_no(report.get('reboot_required'))}"])
    if report.get("reboot_required") is True:
        attention.append("Restart required")
    memory = report["memory_bytes"]
    if any(size_text(memory.get(key)) == "Not reported" for key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")):
        attention.append("Memory information incomplete")
    lines.extend(["", "Memory", f"Physical RAM: {size_text(memory.get('MemTotal'))}",
                  f"Available RAM: {size_text(memory.get('MemAvailable'))}",
                  f"Swap: {size_text(memory.get('SwapFree'))} free of {size_text(memory.get('SwapTotal'))}",
                  "Compressed swap is not extra physical RAM."])
    zram = report.get("zram")
    for block in zram if isinstance(zram, list) else []:
        if isinstance(block, dict):
            lines.extend([f"{value(block.get('device'))}:",
                          f"  Physical consumption: {size_text(block.get('physical_consumption'))}",
                          f"  Original data: {size_text(block.get('original_data'))}",
                          f"  Compressed data: {size_text(block.get('compressed_data'))}",
                          f"  Logical capacity: {size_text(block.get('logical_capacity'))}"])
    lines.extend(["", "Service endpoints"])
    if not report["services"]:
        lines.append("No service checks reported.")
        attention.append("No service checks reported")
    for name, service in report["services"].items():
        state = value(service.get("state")) if isinstance(service, dict) else "Not reported"
        probe = value(service.get("probe")) if isinstance(service, dict) else "Not reported"
        lines.append(f"{name}: {state.replace('-', ' ')} — {probe}")
        if state != "ready":
            attention.append(f"{name}: {state}")
    devices = report.get("devices")
    if isinstance(devices, dict):
        lines.extend(["", "Detected device nodes"])
        lines.extend(f"{name.title()}: {names(items)}" for name, items in devices.items())
    helpers = report.get("helpers")
    if isinstance(helpers, dict):
        lines.extend(["", "Commands", "Available: " + names([name for name, present in helpers.items() if present is True]),
                      "Missing: " + names([name for name, present in helpers.items() if present is False])])
    lines.extend(["", "Scope", "Read-only snapshot. Endpoint replies and device nodes do not prove physical hardware works.",
                  f"Audio playback tested: {yes_no(report.get('audio_playback_tested'))}",
                  f"Hardware functionality tested: {yes_no(report.get('hardware_functionality_tested'))}"])
    return "\n".join(lines), attention
