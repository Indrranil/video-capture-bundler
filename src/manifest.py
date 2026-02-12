from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


from src.utils import utc_now_iso



@dataclass
class BundleMeta:
    factory_name: str
    target_class: str
    camera_name: str
    camera_ip: str
    rtsp_url: str | None
    recorded_at: str
    duration_sec: int
    fps: int
    width: int
    height: int
    video_filename: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factory_name": self.factory_name,
            "target_class": self.target_class,
            "camera_name": self.camera_name,
            "camera_ip": self.camera_ip,
            "rtsp_url": self.rtsp_url,
            "recorded_at": self.recorded_at,
            "duration_sec": self.duration_sec,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "video_filename": self.video_filename,
        }


def build_manifest(
    factory_name: str,
    target_class: str,
    camera_name: str,
    camera_ip: str,
    rtsp_url: str | None,
    duration_sec: int,
    fps: int,
    width: int,
    height: int,
    video_filename: str,
) -> BundleMeta:
    return BundleMeta(
        factory_name=factory_name,
        target_class=target_class,
        camera_name=camera_name,
        camera_ip=camera_ip,
        rtsp_url=rtsp_url,
        recorded_at=utc_now_iso(),
        duration_sec=duration_sec,
        fps=fps,
        width=width,
        height=height,
        video_filename=video_filename,
    )
