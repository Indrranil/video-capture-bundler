from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.config import app_config
from src.state_store import StateStore
from src.storage import get_uploader
from src.webui import transcode
from src.webui.schemas import CapturesResponse, ChunkSummary

router = APIRouter(prefix="/api", tags=["capture"])


def _compute_gaps(chunks: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Annotates each AUTO chunk with the gap (seconds) since that camera's previous AUTO chunk,
    plus a coarse "ok"/"gap" verdict — this is what lets you actually SEE that the main loop's
    time-wise bundling has been firing on schedule rather than just trusting it. Computed over
    the FULL history first (not just whatever's displayed), so gaps stay accurate even once a
    camera's older chunks fall outside the top-N shown in the UI.

    Manual chunks are deliberately excluded from this sequence entirely (not just skipped when
    annotating) — mixing an on-demand manual recording into the schedule would make the
    surrounding AUTO gaps look artificially larger/smaller than reality. Manual chunks always
    get gap_sec=None/bundling_status=None; there's no "expected schedule" for them.

    "ok" = gap <= 2x VIDEO_DURATION (generous — bundling/upload latency, not just recording
    time, eats into the gap); anything larger is flagged "gap" as a likely missed cycle. The
    first AUTO chunk seen for a camera has nothing to compare against, so it also stays None.
    """
    by_camera: Dict[str, List[Dict[str, Any]]] = {}
    for rec in chunks.values():
        if rec.get("source", "auto") != "auto":
            continue
        by_camera.setdefault(rec.get("camera_name", ""), []).append(dict(rec))

    tolerance_sec = max(1, app_config.VIDEO_DURATION) * 2
    annotated_by_id: Dict[str, Dict[str, Any]] = {}

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
            annotated_by_id[item["chunk_id"]] = item

    out: List[Dict[str, Any]] = []
    for rec in chunks.values():
        chunk_id = rec.get("chunk_id")
        annotated = annotated_by_id.get(chunk_id)
        if annotated is not None:
            out.append(annotated)
        else:
            row = dict(rec)
            row.setdefault("gap_sec", None)
            row.setdefault("bundling_status", None)
            out.append(row)
    return out


@router.get("/captures", response_model=CapturesResponse)
def list_captures(
    source: Optional[str] = Query(default=None, description="'auto' | 'manual', omit for both"),
    limit: int = Query(default=100, le=1000),
) -> CapturesResponse:
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
    with_gaps = _compute_gaps(state.list_chunks())

    if source:
        with_gaps = [r for r in with_gaps if r.get("source", "auto") == source]

    with_gaps.sort(key=lambda r: r.get("started_at_ist") or "", reverse=True)
    total = len(with_gaps)

    rows = []
    for row in with_gaps[:limit]:
        video_path = row.get("video_path")
        rows.append(ChunkSummary(**row, has_video=bool(video_path and os.path.exists(video_path))))

    return CapturesResponse(total=total, rows=rows)


@router.get("/captures/{chunk_id}/video")
def get_capture_video(chunk_id: str):
    """
    Serves a browser-playable version of the recording for either the Manual Capture or
    Recordings page. Recordings are always .avi (bundler.py never deletes the source file
    after zipping it) — no major browser has an AVI demuxer, so this transcodes to H.264/MP4
    via transcode.get_or_transcode() the first time a chunk is viewed, caching the result at
    output/state/transcoded/<chunk_id>.mp4 so every view after that is instant. Falls back to
    serving the raw .avi (download-only in most browsers, but not a broken link) if ffmpeg
    isn't installed or the transcode fails for any reason.
    """
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
    rec = state.get_chunk(chunk_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found")

    video_path = rec.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="No video file found for this chunk")

    mp4_path = transcode.get_or_transcode(app_config.OUTPUT_DIR, chunk_id, video_path)
    if mp4_path:
        return FileResponse(
            mp4_path, media_type="video/mp4", filename=f"{chunk_id}.mp4",
            content_disposition_type="inline",
        )

    return FileResponse(
        video_path,
        media_type="video/x-msvideo",
        filename=os.path.basename(video_path),
        content_disposition_type="inline",
    )


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
