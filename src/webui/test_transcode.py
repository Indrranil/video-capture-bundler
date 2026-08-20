"""
Plain-assert self-check for src/webui/transcode.py. Run: python -m src.webui.test_transcode
Uses a small synthetic .avi source (same helper pattern as src/test_recorder.py) so this needs
no real camera. The real-transcode assertions are skipped (not failed) if ffmpeg isn't on PATH
in this environment — that's an environment fact, not a code bug; the "ffmpeg missing" fallback
path is tested unconditionally via a mock either way.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import patch

import cv2
import numpy as np

from src.webui import transcode


def _write_test_source_video(path: str, fps: int, width: int, height: int, seconds: int) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    blank = np.zeros((height, width, 3), dtype=np.uint8)
    for _ in range(fps * seconds):
        out.write(blank)
    out.release()


def test_returns_none_when_ffmpeg_missing() -> None:
    tmp_dir = tempfile.mkdtemp()
    try:
        source_path = os.path.join(tmp_dir, "source.avi")
        _write_test_source_video(source_path, fps=5, width=64, height=48, seconds=1)

        with patch("src.webui.transcode.shutil.which", return_value=None):
            result = transcode.get_or_transcode(tmp_dir, "chunk1", source_path)
        assert result is None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_transcode_and_cache_roundtrip() -> None:
    if not transcode.ffmpeg_available():
        print("test_transcode_and_cache_roundtrip: skipped (no ffmpeg on PATH here)")
        return

    tmp_dir = tempfile.mkdtemp()
    try:
        source_path = os.path.join(tmp_dir, "source.avi")
        _write_test_source_video(source_path, fps=5, width=64, height=48, seconds=1)

        mp4_path = transcode.get_or_transcode(tmp_dir, "chunk1", source_path)
        assert mp4_path is not None, "transcode should succeed on a valid source video"
        assert os.path.exists(mp4_path)
        assert os.path.getsize(mp4_path) > 0
        assert mp4_path.endswith("chunk1.mp4")

        # second call must hit the cache — not re-invoke ffmpeg at all
        with patch("src.webui.transcode.subprocess.run") as mock_run:
            mp4_path_2 = transcode.get_or_transcode(tmp_dir, "chunk1", source_path)
        assert mp4_path_2 == mp4_path
        mock_run.assert_not_called()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_returns_none_on_bad_source_file() -> None:
    if not transcode.ffmpeg_available():
        print("test_returns_none_on_bad_source_file: skipped (no ffmpeg on PATH here)")
        return

    tmp_dir = tempfile.mkdtemp()
    try:
        bad_source = os.path.join(tmp_dir, "not-a-video.avi")
        with open(bad_source, "w", encoding="utf-8") as f:
            f.write("this is not a video file")

        result = transcode.get_or_transcode(tmp_dir, "badchunk", bad_source)
        assert result is None, "ffmpeg should fail on a non-video input and we should report that as None"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_returns_none_when_ffmpeg_missing()
    test_transcode_and_cache_roundtrip()
    test_returns_none_on_bad_source_file()
    print("ok")
