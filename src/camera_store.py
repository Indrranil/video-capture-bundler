"""
Camera list storage: a flat JSON file (output/state/cameras.json), same idiom as
src/state_store.py's chunks.json — no database needed for a handful of cameras.

Each camera is {"name": str, "ip": str, "rtsp_url": str}. This is the single authoritative
source for src.main's recording loop and the webui's capture endpoints; the old
CAMERAS/CAMERA_IPS/RTSP_URLS CSV env fields (src/config.py) are now only read once, as a
migration seed, the first time cameras.json doesn't exist yet — so an existing deployment's
cameras aren't lost when this file is introduced.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from src.utils import ensure_dir, read_json, write_json

Camera = Dict[str, str]


def _path(output_dir: str) -> str:
    return os.path.join(output_dir, "state", "cameras.json")


def _seed_from_config(cfg) -> List[Camera]:
    names = cfg.camera_names()
    ips = cfg.camera_ips()
    urls = cfg.rtsp_urls()
    if not urls:
        urls = [""] * len(names)
    return [{"name": names[i], "ip": ips[i], "rtsp_url": urls[i] or ""} for i in range(len(names))]


def _save(output_dir: str, cameras: List[Camera]) -> None:
    path = _path(output_dir)
    ensure_dir(os.path.dirname(path))
    write_json(path, cameras)


def list_cameras(output_dir: str, cfg=None) -> List[Camera]:
    path = _path(output_dir)
    existing = read_json(path)
    if existing is not None:
        return existing

    if cfg is None:
        from src.config import app_config as cfg

    seeded = _seed_from_config(cfg)
    _save(output_dir, seeded)
    return seeded


def add_camera(output_dir: str, name: str, ip: str, rtsp_url: str = "") -> List[Camera]:
    name = (name or "").strip()
    ip = (ip or "").strip()
    if not name:
        raise ValueError("Camera name is required")
    if not ip:
        raise ValueError("Camera IP is required")

    cameras = list_cameras(output_dir)
    if any(c["name"] == name for c in cameras):
        raise ValueError(f"Camera '{name}' already exists")

    cameras.append({"name": name, "ip": ip, "rtsp_url": (rtsp_url or "").strip()})
    _save(output_dir, cameras)
    return cameras


def update_camera(
    output_dir: str,
    name: str,
    ip: Optional[str] = None,
    rtsp_url: Optional[str] = None,
) -> List[Camera]:
    cameras = list_cameras(output_dir)
    for c in cameras:
        if c["name"] == name:
            if ip is not None:
                c["ip"] = ip.strip()
            if rtsp_url is not None:
                c["rtsp_url"] = rtsp_url.strip()
            _save(output_dir, cameras)
            return cameras
    raise KeyError(f"Camera '{name}' not found")


def delete_camera(output_dir: str, name: str) -> List[Camera]:
    cameras = list_cameras(output_dir)
    remaining = [c for c in cameras if c["name"] != name]
    if len(remaining) == len(cameras):
        raise KeyError(f"Camera '{name}' not found")
    _save(output_dir, remaining)
    return remaining
