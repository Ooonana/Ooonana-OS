"""Display package activity until the transfer closes its control pipe."""

import os
import select
import signal
import sys
import time
from pathlib import Path


REPO_METADATA = ("current", "index.tsv", "SHA256SUMS", "SHA256SUMS.sig")


def content_length(headers):
    """Read the current response length, ignoring redirects and chunked bodies."""
    try:
        lines = headers.read_text(encoding="latin-1").splitlines()
    except OSError:
        return None

    total = None
    success = False
    encoded = False
    for line in lines:
        line = line.strip()
        if line.startswith("HTTP/"):
            status = line.split()[1:2]
            success = bool(status and status[0].startswith("2"))
            total = None
            encoded = False
        elif success:
            name, _, value = line.partition(":")
            value = value.strip()
            if name.lower() == "content-length" and value.isascii() and value.isdigit() and len(value) < 20:
                total = int(value)
            elif name.lower() in ("transfer-encoding", "content-encoding") and value.lower() != "identity":
                encoded = True
    return total if total and not encoded else None


def file_size(path):
    try:
        return path.stat().st_size
    except OSError:
        return 0


def draw(label, frame, *, size, total=None, speed=0):
    try:
        width = os.get_terminal_size(sys.stderr.fileno()).columns or 80
    except OSError:
        width = 80
    width = max(1, width - 1)
    utf8 = (sys.stderr.encoding or "").lower().replace("-", "") == "utf8"
    empty, full, cell_width = ("□", "■", 2) if utf8 else ("[ ]", "[#]", 3)
    details = ""
    if total:
        percent = min(100, size * 100 // total)
        details = f"{percent:3}%  "
    if width >= max(68, len(label) + 49):
        count = f"{size / 1024:.1f}"
        if total:
            count += f"/{total / 1024:.1f}"
        details += f"{count} KiB  "
    details += f"{speed / 1024:.1f} KiB/s"

    # Keep the number of cells stable as speed changes on normal terminals.
    reserved = max(17, len(details)) if total else len(details) + 2
    label_reserve = (13 if width >= 50 else 2) if total else min(len(label), 25) + 2
    cells = min(10, max(0, (width - reserved - label_reserve) // cell_width))
    if cells and total:
        filled = cells * percent // 100
        bar = full * filled + empty * (cells - filled)
    elif cells:
        position = frame % cells
        bar = empty * position + full + empty * (cells - position - 1)
    else:
        bar = ""

    tail = f"{bar}  {details}" if bar else details
    tail_width = cells * cell_width + (2 if bar else 0) + len(details)
    label_width = width - tail_width - 2
    line = f"{label[:label_width]}  {tail}" if label_width >= 12 else tail[:width]
    if "NO_COLOR" not in os.environ:
        term = os.environ.get("TERM", "")
        orange = "\x1b[38;5;214m" if "256color" in term or "direct" in term else "\x1b[33m"
        line = f"{orange}{line}\x1b[0m"
    sys.stderr.write(f"\r\x1b[K{line}")
    sys.stderr.flush()


def interrupted(number, _frame):
    raise SystemExit(128 + number)


def main(label, filename, header_path, result_path):
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)

    payload = Path(filename)
    headers = Path(header_path) if header_path else None
    paths = (payload,) if headers else tuple(payload / name for name in REPO_METADATA)
    title = f"Downloading {label}" if headers else f"Refreshing {label}"
    start = previous_time = time.monotonic()
    previous_sizes = (0,) * len(paths)
    frame = 0
    try:
        while True:
            now = time.monotonic()
            sizes = tuple(file_size(path) for path in paths)
            received = sum(size - old if size >= old else size for size, old in zip(sizes, previous_sizes))
            speed = received / max(0.01, now - previous_time) if frame else 0
            total = content_length(headers) if headers else None
            draw(title, frame, size=sum(sizes), total=total, speed=speed)
            previous_sizes, previous_time = sizes, now
            if select.select([sys.stdin], [], [], 0.25)[0]:
                break
            frame += 1
    finally:
        sys.stderr.write("\r\x1b[K")
        sys.stderr.flush()

    result = Path(result_path)
    if result.is_file() and result.read_text().strip() == "0":
        size = sum(file_size(path) for path in paths)
        speed = size / max(0.01, time.monotonic() - start)
        if headers:
            draw(f"Downloaded {label}", frame, size=size, total=size or 1, speed=speed)
            sys.stderr.write("\n")
        else:
            print(f"Fetched {label}  {size / 1024:.1f} KiB  {speed / 1024:.1f} KiB/s", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:])
