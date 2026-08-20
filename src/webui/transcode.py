from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

CACHE_SUBDIR = "transcoded"


def _cache_path(output_dir: str, chunk_id: str) -> str:
    cache_dir = os.path.join(output_dir, "state", CACHE_SUBDIR)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{chunk_id}.mp4")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def get_or_transcode(output_dir: str, chunk_id: str, source_path: str) -> Optional[str]:
    """
    Returns a browser-playable H.264/MP4 version of source_path (our recordings are always
    .avi — H264-in-AVI when that encoder was available, XVID otherwise — and no major browser
    has an AVI demuxer regardless of the codec inside), transcoding once and caching the result
    at output/state/transcoded/<chunk_id>.mp4 so every view after the first is instant.

    Returns None if ffmpeg isn't installed or the transcode fails for any reason — callers
    should fall back to serving source_path directly (download-only in most browsers, but
    better than a broken "View" link) rather than erroring outright.
    """
    cached = _cache_path(output_dir, chunk_id)
    if os.path.exists(cached) and os.path.getsize(cached) > 0:
        return cached

    if not ffmpeg_available():
        return None

    # ffmpeg infers the output container FORMAT from the filename's extension, not its content —
    # cached + ".tmp" would end in ".tmp" (mp4.tmp), which ffmpeg can't map to any muxer at all.
    # Keeping ".mp4" as the actual last extension is what makes this work.
    tmp_path = os.path.join(os.path.dirname(cached), f"{chunk_id}.tmp.mp4")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", source_path,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p",  # widest browser/device compatibility
                "-movflags", "+faststart",  # moov atom up front — playback can start before full download
                "-an",  # cv2.VideoWriter never writes audio, so recordings never have any to keep
                tmp_path,
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0 or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            return None
        os.replace(tmp_path, cached)
        return cached
    except Exception:
        return None
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
