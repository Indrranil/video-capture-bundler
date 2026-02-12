from __future__ import annotations

import os
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def day_key_local() -> str:
    # "YYYY-MM-DD" in local time (good enough for initial daily grouping)
    return datetime.now().strftime("%Y-%m-%d")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def file_size_bytes(path: str) -> int:
    return os.path.getsize(path)


def mb_to_bytes(mb: int) -> int:
    return mb * 1024 * 1024


def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def safe_slug(s: str) -> str:
    keep = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)


def make_chunk_id(camera_name: str) -> str:
    # Unique enough: cam + unix ms
    return f"{safe_slug(camera_name)}_{int(time.time() * 1000)}"
