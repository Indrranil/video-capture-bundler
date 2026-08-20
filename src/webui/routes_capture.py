from __future__ import annotations

import traceback
from typing import List

from fastapi import APIRouter, BackgroundTasks

from src import camera_store
from src.bundler import bundle_recording
from src.config import app_config
from src.recorder import record_chunk_avi
from src.state_store import StateStore
from src.webui.forms import resolve_camera
from src.webui.schemas import CaptureRequest, ChunkSummary

router = APIRouter(prefix="/api", tags=["capture"])


@router.get("/captures", response_model=List[ChunkSummary])
def list_captures() -> List[ChunkSummary]:
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
    chunks = state.list_chunks()
    rows = sorted(chunks.values(), key=lambda r: r.get("started_at_ist") or "", reverse=True)
    return [ChunkSummary(**row) for row in rows[:20]]


def _run_capture(camera_name: str, camera_ip: str, rtsp_url, duration: int) -> None:
    try:
        state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
        rec = record_chunk_avi(
            output_dir=app_config.OUTPUT_DIR,
            camera_name=camera_name,
            camera_ip=camera_ip,
            rtsp_url=rtsp_url,
            duration_sec=duration,
            fps=app_config.VIDEO_FPS,
            width=app_config.VIDEO_WIDTH,
            height=app_config.VIDEO_HEIGHT,
            enable_recording=app_config.ENABLE_RECORDING,
        )
        state.set_current_chunk(camera_name=camera_name, chunk_id=rec.chunk_id, topic="")

        zip_path = bundle_recording(
            output_dir=app_config.OUTPUT_DIR,
            record=rec,
            factory_name=app_config.FACTORY_NAME,
            target_class=app_config.TARGET_CLASS,
            zip_mode=app_config.ZIP_MODE,
            daily_max_size_mb=app_config.DAILY_MAX_SIZE_MB,
            enable_bundling=app_config.ENABLE_BUNDLING,
            enable_manifest=app_config.ENABLE_MANIFEST,
        )
        if zip_path:
            state.set_zip_path(rec.chunk_id, zip_path)
    except Exception:
        # a background task swallows exceptions by default — surface them in the logs
        traceback.print_exc()


@router.post("/capture")
def trigger_capture(body: CaptureRequest, background_tasks: BackgroundTasks) -> dict:
    cameras = camera_store.list_cameras(app_config.OUTPUT_DIR)
    names = [c["name"] for c in cameras]
    ips = [c["ip"] for c in cameras]
    urls = [c["rtsp_url"] or None for c in cameras]

    camera_name, camera_ip, rtsp_url = resolve_camera(
        body.camera, body.adhoc_rtsp_url or "", names, ips, urls
    )
    duration = body.duration_override or app_config.VIDEO_DURATION

    background_tasks.add_task(_run_capture, camera_name, camera_ip, rtsp_url, duration)
    return {"ok": True, "message": "started", "camera": camera_name, "duration": duration}
