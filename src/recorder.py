from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2

from src.utils import ensure_dir, make_chunk_id


@dataclass
class RecordResult:
    camera_name: str
    camera_ip: str
    rtsp_url: Optional[str]
    chunk_id: str
    video_path: str
    duration_sec: int
    fps: int
    width: int
    height: int
    ok: bool
    error: Optional[str] = None


def _make_paths(output_dir: str, camera_name: str) -> tuple[str, str, str]:
    chunk_id = make_chunk_id(camera_name)
    day = time.strftime("%Y-%m-%d")
    out_dir = os.path.join(output_dir, "recordings", camera_name, day)
    ensure_dir(out_dir)
    return chunk_id, out_dir, os.path.join(out_dir, f"{chunk_id}.avi")


def _stub_result(
    *,
    camera_name: str,
    camera_ip: str,
    rtsp_url: Optional[str],
    chunk_id: str,
    video_path: str,
    fps: int,
    width: int,
    height: int,
    ok: bool,
    error: Optional[str],
) -> RecordResult:
    _write_stub_avi(video_path, fps=fps, width=width, height=height, seconds=1)
    return RecordResult(
        camera_name=camera_name,
        camera_ip=camera_ip,
        rtsp_url=rtsp_url,
        chunk_id=chunk_id,
        video_path=video_path,
        duration_sec=1,
        fps=fps,
        width=width,
        height=height,
        ok=ok,
        error=error,
    )


def _open_writer(video_path: str, fps: int, width: int, height: int) -> cv2.VideoWriter:
    """H264 first (team repo convention), falling back to XVID — support varies by machine."""
    writer = None
    try:
        fourcc = cv2.VideoWriter_fourcc(*"H264")
        writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError("H264 writer failed")
        return writer
    except Exception:
        if writer is not None:
            writer.release()
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        return cv2.VideoWriter(video_path, fourcc, fps, (width, height))


def record_chunk_avi(
    output_dir: str,
    camera_name: str,
    camera_ip: str,
    rtsp_url: Optional[str],
    duration_sec: int,
    fps: int,
    width: int,
    height: int,
    enable_recording: bool,
) -> RecordResult:
    """
    Records one AVI chunk of a fixed, pre-known duration. If enable_recording=False, creates a
    tiny stub AVI. If RTSP fails, also falls back to stub AVI but returns ok=False with an
    error string, rather than raising — callers only branch on ok/log it.
    """
    chunk_id, _, video_path = _make_paths(output_dir, camera_name)

    if not enable_recording:
        return _stub_result(
            camera_name=camera_name, camera_ip=camera_ip, rtsp_url=rtsp_url,
            chunk_id=chunk_id, video_path=video_path, fps=fps, width=width, height=height,
            ok=True, error=None,
        )

    if not rtsp_url:
        return _stub_result(
            camera_name=camera_name, camera_ip=camera_ip, rtsp_url=rtsp_url,
            chunk_id=chunk_id, video_path=video_path, fps=fps, width=width, height=height,
            ok=False, error="RTSP_URL missing; wrote stub AVI instead.",
        )

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return _stub_result(
            camera_name=camera_name, camera_ip=camera_ip, rtsp_url=rtsp_url,
            chunk_id=chunk_id, video_path=video_path, fps=fps, width=width, height=height,
            ok=False, error="Failed to open RTSP stream; wrote stub AVI instead.",
        )

    writer = _open_writer(video_path, fps, width, height)
    frames_needed = int(duration_sec * fps)
    frames_written = 0

    while frames_written < frames_needed:
        ok, frame = cap.read()
        if not ok or frame is None:
            # stream hiccup — break and close what we have
            break

        frame = cv2.resize(frame, (width, height))
        writer.write(frame)
        frames_written += 1

    cap.release()
    writer.release()

    actual_sec = max(1, int(frames_written / max(1, fps)))
    ok_final = frames_written > fps  # at least ~1 second
    err = None if ok_final else "Too few frames read from RTSP."

    return RecordResult(
        camera_name=camera_name,
        camera_ip=camera_ip,
        rtsp_url=rtsp_url,
        chunk_id=chunk_id,
        video_path=video_path,
        duration_sec=actual_sec,
        fps=fps,
        width=width,
        height=height,
        ok=ok_final,
        error=err,
    )


def record_until_stopped(
    output_dir: str,
    camera_name: str,
    camera_ip: str,
    rtsp_url: Optional[str],
    fps: int,
    width: int,
    height: int,
    stop_event: threading.Event,
    max_duration_sec: int = 3600,
) -> RecordResult:
    """
    Like record_chunk_avi, but keeps recording until stop_event is set instead of a fixed
    duration — used by the webui's manual Start/Stop recording control (src/webui/routes_live.py).
    max_duration_sec is a safety cap (default 1h) so a forgotten "start" without a matching
    "stop" doesn't record forever.
    """
    chunk_id, _, video_path = _make_paths(output_dir, camera_name)

    if not rtsp_url:
        return _stub_result(
            camera_name=camera_name, camera_ip=camera_ip, rtsp_url=rtsp_url,
            chunk_id=chunk_id, video_path=video_path, fps=fps, width=width, height=height,
            ok=False, error="RTSP_URL missing; wrote stub AVI instead.",
        )

    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return _stub_result(
            camera_name=camera_name, camera_ip=camera_ip, rtsp_url=rtsp_url,
            chunk_id=chunk_id, video_path=video_path, fps=fps, width=width, height=height,
            ok=False, error="Failed to open RTSP stream; wrote stub AVI instead.",
        )

    writer = _open_writer(video_path, fps, width, height)
    frames_written = 0
    max_frames = max_duration_sec * fps

    while not stop_event.is_set() and frames_written < max_frames:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        frame = cv2.resize(frame, (width, height))
        writer.write(frame)
        frames_written += 1

    cap.release()
    writer.release()

    actual_sec = max(1, int(frames_written / max(1, fps)))
    ok_final = frames_written > fps
    err = None if ok_final else "Too few frames read from RTSP."

    return RecordResult(
        camera_name=camera_name,
        camera_ip=camera_ip,
        rtsp_url=rtsp_url,
        chunk_id=chunk_id,
        video_path=video_path,
        duration_sec=actual_sec,
        fps=fps,
        width=width,
        height=height,
        ok=ok_final,
        error=err,
    )


def _write_stub_avi(path: str, fps: int, width: int, height: int, seconds: int) -> None:
    """
    Writes a valid AVI with blank frames (so the downstream zip/manifest flow can be tested).
    """
    import numpy as np

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    frames = max(1, fps * seconds)
    blank = np.zeros((height, width, 3), dtype=np.uint8)

    for _ in range(frames):
        out.write(blank)

    out.release()
