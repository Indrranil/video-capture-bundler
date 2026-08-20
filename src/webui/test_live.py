"""
Plain-assert self-check for src/webui/routes_live.py. Run: python -m src.webui.test_live
Exercises the start/stop recording lifecycle and status transitions without a real camera —
rtsp_url=None takes record_until_stopped's instant stub path, so this needs no live RTSP feed.
No pytest, no mocking framework, matching this repo's convention.
"""
from __future__ import annotations

import tempfile
import threading
import time

from fastapi.testclient import TestClient

from src.config import app_config
from src.state_store import StateStore
from src.webui import routes_live
from src.webui.main import app


def test_run_recording_completes_and_clears_active_slot() -> None:
    orig_output_dir = app_config.OUTPUT_DIR
    tmp_dir = tempfile.mkdtemp()
    try:
        app_config.OUTPUT_DIR = tmp_dir
        routes_live._active = {
            "camera_name": "test-cam",
            "started_at": time.time(),
            "stop_event": threading.Event(),
        }

        # rtsp_url=None -> record_until_stopped's stub path, returns almost instantly
        routes_live._run_recording("test-cam", "", None, threading.Event())

        assert routes_live._active is None, "the finally block must clear the active slot"

        state = StateStore(output_dir=tmp_dir, tz_name=app_config.TIMEZONE)
        chunks = state.list_chunks()
        assert any(c["camera_name"] == "test-cam" for c in chunks.values())
    finally:
        app_config.OUTPUT_DIR = orig_output_dir
        routes_live._active = None


def test_preview_rejects_camera_with_no_rtsp_url() -> None:
    client = TestClient(app)
    r = client.get("/api/live/preview", params={"camera": "__adhoc__", "adhoc_rtsp_url": ""})
    assert r.status_code == 400


def test_start_stop_conflict_detection() -> None:
    routes_live._active = None
    client = TestClient(app)
    try:
        # stop with nothing active -> 409
        r = client.post("/api/live/stop")
        assert r.status_code == 409

        # an in-progress recording -> a second start conflicts
        routes_live._active = {
            "camera_name": "camX",
            "started_at": time.time(),
            "stop_event": threading.Event(),
        }
        r = client.post("/api/live/start", json={"camera": "camX", "adhoc_rtsp_url": None})
        assert r.status_code == 409

        r = client.get("/api/live/status")
        assert r.json()["recording"] is True
        assert r.json()["camera"] == "camX"
    finally:
        routes_live._active = None


if __name__ == "__main__":
    test_run_recording_completes_and_clears_active_slot()
    test_preview_rejects_camera_with_no_rtsp_url()
    test_start_stop_conflict_detection()
    print("ok")
