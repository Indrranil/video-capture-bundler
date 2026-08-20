"""
Plain-assert self-check for src/recorder.py's stop_event-based indefinite recording. Run:
python -m src.test_recorder
No real camera available for this, and no real-time pacing to lean on either — a local video
file decodes as fast as the CPU can go, not at its nominal fps, so it can't stand in for "a
stream that's still arriving." Instead this patches cv2.VideoCapture with a fake that "reads" a
blank frame every ~2ms forever, and verifies stop_event actually halts the loop well short of
the (much larger) max_duration_sec safety cap — the only thing that stops a fake source that
never runs out on its own.
"""
from __future__ import annotations

import shutil
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np

from src.recorder import record_chunk_avi, record_until_stopped


def test_record_chunk_avi_stub_paths_still_work_after_refactor() -> None:
    # record_chunk_avi and record_until_stopped now share _stub_result()/_open_writer() —
    # this is a regression check that extracting those helpers didn't change record_chunk_avi's
    # existing stub behavior (enable_recording=False, and missing rtsp_url).
    tmp_dir = tempfile.mkdtemp()
    try:
        rec = record_chunk_avi(
            output_dir=tmp_dir, camera_name="cam1", camera_ip="10.0.0.1", rtsp_url=None,
            duration_sec=5, fps=10, width=64, height=48, enable_recording=False,
        )
        assert rec.ok is True and rec.duration_sec == 1 and rec.error is None
        import os
        assert os.path.exists(rec.video_path)

        rec2 = record_chunk_avi(
            output_dir=tmp_dir, camera_name="cam1", camera_ip="10.0.0.1", rtsp_url=None,
            duration_sec=5, fps=10, width=64, height=48, enable_recording=True,
        )
        assert rec2.ok is False and "RTSP_URL missing" in rec2.error
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_stop_event_interrupts_the_loop() -> None:
    tmp_dir = tempfile.mkdtemp()
    try:
        fps, width, height = 10, 64, 48
        blank = np.zeros((height, width, 3), dtype=np.uint8)

        def _slow_read(*_args, **_kwargs):
            time.sleep(0.002)
            return True, blank

        fake_cap = MagicMock()
        fake_cap.isOpened.return_value = True
        fake_cap.read.side_effect = _slow_read

        stop_event = threading.Event()
        result_holder = {}

        def _run():
            result_holder["result"] = record_until_stopped(
                output_dir=tmp_dir,
                camera_name="stopcam",
                camera_ip="",
                rtsp_url="fake://unused",
                fps=fps,
                width=width,
                height=height,
                stop_event=stop_event,
                max_duration_sec=3600,  # a fake source that never runs out on its own would
                                        # otherwise hit this; setting stop_event should win first
            )

        with patch("src.recorder.cv2.VideoCapture", return_value=fake_cap):
            t = threading.Thread(target=_run)
            t.start()
            time.sleep(0.3)  # ~150 fake frames at the ~2ms pace above
            stop_event.set()
            t.join(timeout=5)

        assert not t.is_alive(), "recording thread should have stopped promptly after stop_event"
        result = result_holder["result"]
        assert result.ok is True
        assert result.duration_sec < 3600, "stop_event should have ended this, not the safety cap"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_record_chunk_avi_stub_paths_still_work_after_refactor()
    test_stop_event_interrupts_the_loop()
    print("ok")
