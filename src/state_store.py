from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from src.utils import ensure_dir


def _now_ist_iso(tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return datetime.now(tz).isoformat()


# ponytail: no file lock — chunks.json now has three potential writers (main.py's loop, the
# Kafka listener thread, and src/webui's manual-capture background task), each doing a non-
# atomic read-modify-write. Accepted for now (matches the existing "last write wins" design);
# add fcntl.flock around these two helpers if manual captures start colliding with the main loop.
def _safe_read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_write_json(path: str, obj: dict) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


@dataclass
class ChunkRecord:
    chunk_id: str
    camera_name: str
    topic: str
    started_at_ist: str
    zip_path: Optional[str] = None
    verdict: Optional[int] = None  # 1 anomaly, 0 normal
    event_time_ist: Optional[str] = None
    uploaded_url: Optional[str] = None  # set once manually uploaded via the webui's Upload button

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "camera_name": self.camera_name,
            "topic": self.topic,
            "started_at_ist": self.started_at_ist,
            "zip_path": self.zip_path,
            "verdict": self.verdict,
            "event_time_ist": self.event_time_ist,
            "uploaded_url": self.uploaded_url,
        }


class StateStore:
    """
    Persists:
      - current chunk per camera: output/state/current_chunk_<camera>.json
      - all chunk records: output/state/chunks.json (dict keyed by chunk_id)
    """

    def __init__(self, output_dir: str, tz_name: str) -> None:
        self.output_dir = output_dir
        self.tz_name = tz_name
        self.state_dir = os.path.join(output_dir, "state")
        ensure_dir(self.state_dir)
        self.chunks_path = os.path.join(self.state_dir, "chunks.json")

    def set_current_chunk(self, camera_name: str, chunk_id: str, topic: str) -> None:
        path = os.path.join(self.state_dir, f"current_chunk_{camera_name}.json")
        payload = {
            "camera_name": camera_name,
            "chunk_id": chunk_id,
            "topic": topic,
            "started_at_ist": _now_ist_iso(self.tz_name),
        }
        _safe_write_json(path, payload)

        # also register chunk start in chunks.json
        chunks = _safe_read_json(self.chunks_path)
        if chunk_id not in chunks:
            rec = ChunkRecord(
                chunk_id=chunk_id,
                camera_name=camera_name,
                topic=topic,
                started_at_ist=payload["started_at_ist"],
            )
            chunks[chunk_id] = rec.to_dict()
            _safe_write_json(self.chunks_path, chunks)

    def get_current_chunk_id_for_camera(self, camera_name: str) -> Optional[str]:
        path = os.path.join(self.state_dir, f"current_chunk_{camera_name}.json")
        if not os.path.exists(path):
            return None
        try:
            data = _safe_read_json(path)
            return data.get("chunk_id")
        except Exception:
            return None

    def mark_verdict_for_camera_current_chunk(self, camera_name: str, verdict: int) -> Optional[str]:
        """
        Returns chunk_id if updated.
        """
        chunk_id = self.get_current_chunk_id_for_camera(camera_name)
        if not chunk_id:
            return None

        chunks = _safe_read_json(self.chunks_path)
        rec = chunks.get(chunk_id)
        if not rec:
            return None

        # update only once; if multiple events come, last event wins
        rec["verdict"] = int(verdict)
        rec["event_time_ist"] = _now_ist_iso(self.tz_name)
        chunks[chunk_id] = rec
        _safe_write_json(self.chunks_path, chunks)
        return chunk_id

    def set_zip_path(self, chunk_id: str, zip_path: str) -> None:
        chunks = _safe_read_json(self.chunks_path)
        rec = chunks.get(chunk_id)
        if not rec:
            return
        rec["zip_path"] = zip_path
        chunks[chunk_id] = rec
        _safe_write_json(self.chunks_path, chunks)

    def set_uploaded_url(self, chunk_id: str, url: str) -> None:
        chunks = _safe_read_json(self.chunks_path)
        rec = chunks.get(chunk_id)
        if not rec:
            return
        rec["uploaded_url"] = url
        chunks[chunk_id] = rec
        _safe_write_json(self.chunks_path, chunks)

    def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        return _safe_read_json(self.chunks_path).get(chunk_id)

    def list_chunks(self) -> Dict[str, Dict[str, Any]]:
        return _safe_read_json(self.chunks_path)
