from __future__ import annotations

import threading
import time
import traceback
from typing import Optional

import cv2
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from src import camera_store
from src.bundler import bundle_recording
from src.config import app_config
from src.recorder import record_until_stopped
from src.state_store import StateStore
from src.webui.forms import resolve_camera
from src.webui.schemas import CaptureRequest

router = APIRouter(prefix="/api/live", tags=["live"])

# MJPEG preview — deliberately capped low. This is a "can I see the camera" check, not a
# surveillance viewer: keeps CPU/bandwidth sane on a server that might be doing this for
# several cameras (and several browser tabs) at once.
PREVIEW_WIDTH = 640
PREVIEW_FPS = 8

# --- Manual start/stop recording state ---------------------------------------------------
# ponytail: single global slot, one manual recording at a time — matches the existing
# single-form Manual Capture UX. Add per-camera concurrent slots if that ever stops being true.
_active: Optional[dict] = None
_lock = threading.Lock()


def _resolve(camera: str, adhoc_rtsp_url: str):
    cameras = camera_store.list_cameras(app_config.OUTPUT_DIR)
    names = [c["name"] for c in cameras]
    ips = [c["ip"] for c in cameras]
    urls = [c["rtsp_url"] or None for c in cameras]
    return resolve_camera(camera, adhoc_rtsp_url, names, ips, urls)


def _mjpeg_frames(rtsp_url: str):
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        cap.release()
        raise HTTPException(status_code=502, detail="Could not open RTSP stream for preview")

    try:
        interval = 1.0 / PREVIEW_FPS
        while True:
            frame_start = time.time()
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            h, w = frame.shape[:2]
            if w > PREVIEW_WIDTH:
                scale = PREVIEW_WIDTH / w
                frame = cv2.resize(frame, (PREVIEW_WIDTH, int(h * scale)))

            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok:
                continue

            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

            elapsed = time.time() - frame_start
            if elapsed < interval:
                time.sleep(interval - elapsed)
    finally:
        # Also reached on client disconnect: FastAPI raises GeneratorExit into this generator
        # at whatever yield it's suspended on, and Python runs `finally` blocks on that too.
        cap.release()


@router.get("/preview")
def preview(camera: str = Query(...), adhoc_rtsp_url: str = Query(default="")):
    _, _, rtsp_url = _resolve(camera, adhoc_rtsp_url)
    if not rtsp_url:
        raise HTTPException(status_code=400, detail="No RTSP URL available for this camera")
    return StreamingResponse(
        _mjpeg_frames(rtsp_url), media_type="multipart/x-mixed-replace; boundary=frame"
    )


def _run_recording(camera_name: str, camera_ip: str, rtsp_url: Optional[str], stop_event: threading.Event) -> None:
    global _active
    try:
        state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
        rec = record_until_stopped(
            output_dir=app_config.OUTPUT_DIR,
            camera_name=camera_name,
            camera_ip=camera_ip,
            rtsp_url=rtsp_url,
            fps=app_config.VIDEO_FPS,
            width=app_config.VIDEO_WIDTH,
            height=app_config.VIDEO_HEIGHT,
            stop_event=stop_event,
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
        # a background thread would otherwise swallow this silently
        traceback.print_exc()
    finally:
        with _lock:
            _active = None


@router.get("/status")
def status() -> dict:
    with _lock:
        if _active is None:
            return {"recording": False}
        return {
            "recording": True,
            "camera": _active["camera_name"],
            "started_at": _active["started_at"],
            "elapsed_sec": int(time.time() - _active["started_at"]),
        }


@router.post("/start")
def start(body: CaptureRequest) -> dict:
    global _active
    with _lock:
        if _active is not None:
            raise HTTPException(status_code=409, detail="A manual recording is already in progress")

        camera_name, camera_ip, rtsp_url = _resolve(body.camera, body.adhoc_rtsp_url or "")
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_run_recording, args=(camera_name, camera_ip, rtsp_url, stop_event), daemon=True
        )
        _active = {"camera_name": camera_name, "started_at": time.time(), "stop_event": stop_event}
        thread.start()

    return {"ok": True, "camera": camera_name}


@router.post("/stop")
def stop() -> dict:
    with _lock:
        if _active is None:
            raise HTTPException(status_code=409, detail="No manual recording is in progress")
        _active["stop_event"].set()

    return {"ok": True, "message": "Stopping — bundling finishes in the background, check Recent captures shortly."}
