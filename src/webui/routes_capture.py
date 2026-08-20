from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from src.config import app_config
from src.state_store import StateStore
from src.storage import get_uploader
from src.webui.schemas import ChunkSummary

router = APIRouter(prefix="/api", tags=["capture"])


def _compute_gaps(chunks: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Groups chunk records by camera, sorted chronologically, and annotates each with the gap
    (in seconds) since that camera's previous chunk, plus a coarse "ok"/"gap" verdict — this is
    what lets you actually SEE that time-wise bundling has been firing on schedule rather than
    just trusting it. Computed over the FULL history (not just whatever's displayed), so gaps
    stay accurate even once a camera's chunks fall outside the top-N shown in the UI.

    "ok" = gap <= 2x VIDEO_DURATION (generous — bundling/upload latency, not just recording
    time, eats into the gap); anything larger is flagged "gap" as a likely missed cycle. The
    very first chunk seen for a camera has no previous chunk to compare against, so gap_sec/
    bundling_status stay None for it rather than falsely flagging a "gap".
    """
    by_camera: Dict[str, List[Dict[str, Any]]] = {}
    for rec in chunks.values():
        by_camera.setdefault(rec.get("camera_name", ""), []).append(dict(rec))

    tolerance_sec = max(1, app_config.VIDEO_DURATION) * 2
    out: List[Dict[str, Any]] = []

    for items in by_camera.values():
        items.sort(key=lambda r: r.get("started_at_ist") or "")
        prev_dt = None
        for item in items:
            started = item.get("started_at_ist")
            dt = None
            if started:
                try:
                    dt = datetime.fromisoformat(started)
                except ValueError:
                    dt = None

            if dt is not None and prev_dt is not None:
                gap = int((dt - prev_dt).total_seconds())
                item["gap_sec"] = gap
                item["bundling_status"] = "ok" if gap <= tolerance_sec else "gap"
            else:
                item["gap_sec"] = None
                item["bundling_status"] = None

            if dt is not None:
                prev_dt = dt
            out.append(item)

    return out


@router.get("/captures", response_model=List[ChunkSummary])
def list_captures() -> List[ChunkSummary]:
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
    with_gaps = _compute_gaps(state.list_chunks())
    rows = sorted(with_gaps, key=lambda r: r.get("started_at_ist") or "", reverse=True)
    return [ChunkSummary(**row) for row in rows[:20]]


@router.post("/captures/{chunk_id}/upload")
def upload_capture(chunk_id: str) -> dict:
    """
    Uploads one already-bundled chunk to whichever STORAGE_PROVIDER is configured — the same
    upload_zip() production code path finalize_day.py uses, just triggered on demand for a
    single chunk instead of the day-end batch. Always 200 with an ok flag: a failed upload
    (bad creds, unreachable endpoint) is an expected outcome to show the user, not a server
    error — matches /api/config/test-storage's convention.
    """
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
    rec = state.get_chunk(chunk_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found")

    zip_path = rec.get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=400, detail="This chunk has no zip file to upload yet")

    factory_location = app_config.FACTORY_LOCATION or "unknown"
    factory_name = app_config.upload_factory_name()
    day_key = datetime.now(ZoneInfo(app_config.TIMEZONE)).strftime("%d%m%y")

    try:
        uploader = get_uploader(app_config.STORAGE_PROVIDER)
        url = uploader.upload_zip(
            local_zip_path=zip_path,
            ddmmyy=day_key,
            factory_location=factory_location,
            factory_name=factory_name,
        )
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}

    state.set_uploaded_url(chunk_id, url)
    return {"ok": True, "message": f"Uploaded -> {url}", "url": url}
