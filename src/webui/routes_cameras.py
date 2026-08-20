from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from src import camera_store
from src.config import app_config
from src.webui.schemas import CameraCreate, CameraListResponse, CameraOut, CameraUpdate

router = APIRouter(prefix="/api/cameras", tags=["cameras"])

# src.main recomputes camera_store.list_cameras() every outer loop pass (see
# _reload_if_env_changed()'s docstring there) — add/edit/delete here takes effect within a few
# seconds on its own, no restart needed.
_NO_RESTART_NEEDED = "Applies automatically within a few seconds — no restart needed."


@router.get("", response_model=List[CameraOut])
def list_cameras() -> List[CameraOut]:
    return [CameraOut(**c) for c in camera_store.list_cameras(app_config.OUTPUT_DIR)]


@router.post("", response_model=CameraListResponse)
def add_camera(body: CameraCreate) -> CameraListResponse:
    try:
        cameras = camera_store.add_camera(app_config.OUTPUT_DIR, body.name, body.ip, body.rtsp_url)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return CameraListResponse(cameras=[CameraOut(**c) for c in cameras], restart=_NO_RESTART_NEEDED)


@router.put("/{name}", response_model=CameraListResponse)
def update_camera(name: str, body: CameraUpdate) -> CameraListResponse:
    try:
        cameras = camera_store.update_camera(
            app_config.OUTPUT_DIR, name, ip=body.ip, rtsp_url=body.rtsp_url
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=e.args[0])
    return CameraListResponse(cameras=[CameraOut(**c) for c in cameras], restart=_NO_RESTART_NEEDED)


@router.delete("/{name}", response_model=CameraListResponse)
def delete_camera(name: str) -> CameraListResponse:
    try:
        cameras = camera_store.delete_camera(app_config.OUTPUT_DIR, name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=e.args[0])
    return CameraListResponse(cameras=[CameraOut(**c) for c in cameras], restart=_NO_RESTART_NEEDED)
