"""
Plain-assert self-check for src/webui/routes_capture.py: the bundling-gap computation (proves
time-wise bundling cadence is actually visible/verifiable) and the upload-capture endpoint's
error paths. Run: python -m src.webui.test_capture
"""
from __future__ import annotations

import tempfile

from fastapi.testclient import TestClient

from src.config import app_config
from src.state_store import StateStore
from src.webui.main import app
from src.webui.routes_capture import _compute_gaps


def test_compute_gaps_flags_a_missed_cycle() -> None:
    orig_duration = app_config.VIDEO_DURATION
    app_config.VIDEO_DURATION = 60  # tolerance = 120s
    try:
        chunks = {
            "c1": {"chunk_id": "c1", "camera_name": "cam1", "started_at_ist": "2026-01-01T10:00:00+05:30"},
            "c2": {"chunk_id": "c2", "camera_name": "cam1", "started_at_ist": "2026-01-01T10:01:30+05:30"},
            "c3": {"chunk_id": "c3", "camera_name": "cam1", "started_at_ist": "2026-01-01T10:10:00+05:30"},
        }
        rows = {r["chunk_id"]: r for r in _compute_gaps(chunks)}

        assert rows["c1"]["gap_sec"] is None, "first chunk for a camera has nothing to compare against"
        assert rows["c1"]["bundling_status"] is None

        assert rows["c2"]["gap_sec"] == 90  # +1m30s, within 2x60s tolerance
        assert rows["c2"]["bundling_status"] == "ok"

        assert rows["c3"]["gap_sec"] == 510  # +8m30s, well past tolerance -> missed cycle
        assert rows["c3"]["bundling_status"] == "gap"
    finally:
        app_config.VIDEO_DURATION = orig_duration


def test_compute_gaps_tracks_cameras_independently() -> None:
    chunks = {
        "a1": {"chunk_id": "a1", "camera_name": "camA", "started_at_ist": "2026-01-01T10:00:00+05:30"},
        "b1": {"chunk_id": "b1", "camera_name": "camB", "started_at_ist": "2026-01-01T10:00:05+05:30"},
    }
    rows = {r["chunk_id"]: r for r in _compute_gaps(chunks)}
    # each is the first chunk seen for its OWN camera — neither should see the other's timestamp
    assert rows["a1"]["gap_sec"] is None
    assert rows["b1"]["gap_sec"] is None


def test_upload_capture_error_paths() -> None:
    orig_output_dir = app_config.OUTPUT_DIR
    tmp_dir = tempfile.mkdtemp()
    try:
        app_config.OUTPUT_DIR = tmp_dir
        client = TestClient(app)

        r = client.post("/api/captures/does-not-exist/upload")
        assert r.status_code == 404

        state = StateStore(output_dir=tmp_dir, tz_name=app_config.TIMEZONE)
        state.set_current_chunk(camera_name="cam1", chunk_id="chunk-no-zip", topic="")

        r = client.post("/api/captures/chunk-no-zip/upload")
        assert r.status_code == 400
    finally:
        app_config.OUTPUT_DIR = orig_output_dir


if __name__ == "__main__":
    test_compute_gaps_flags_a_missed_cycle()
    test_compute_gaps_tracks_cameras_independently()
    test_upload_capture_error_paths()
    print("ok")
