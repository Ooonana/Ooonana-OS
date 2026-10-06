"""Bounded reads and private atomic writes for local AI state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any


def read_bytes(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("state exceeds size limit")
    return data


def read_json(path: Path, limit: int) -> Any:
    try:
        return json.loads(read_bytes(path, limit).decode("utf-8"))
    except RecursionError as error:
        raise ValueError("state nesting exceeds limit") from error


def write_bytes(path: Path, data: bytes, limit: int) -> None:
    if len(data) > limit:
        raise ValueError("state exceeds size limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
