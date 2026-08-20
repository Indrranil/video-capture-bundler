from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ConfigFieldOut(BaseModel):
    key: str
    label: str  # display label — usually == key, occasionally overridden (see forms.FIELD_LABELS)
    value: Any
    type: str  # "bool" | "int" | "str"
    secret: bool
    options: Optional[List[str]] = None  # present => render as a dropdown, not free text


class ConfigSectionOut(BaseModel):
    name: str
    fields: List[ConfigFieldOut]


class ConfigResponse(BaseModel):
    sections: List[ConfigSectionOut]
    # STORAGE_PROVIDER value -> field names only relevant for that provider, so the frontend
    # can show/hide Storage/Upload fields as the provider dropdown changes.
    provider_field_groups: Dict[str, List[str]] = {}


class ConfigUpdateRequest(BaseModel):
    values: Dict[str, str]


class CaptureRequest(BaseModel):
    camera: str
    adhoc_rtsp_url: Optional[str] = None


class CameraOut(BaseModel):
    name: str
    ip: str
    rtsp_url: str


class CameraCreate(BaseModel):
    name: str
    ip: str
    rtsp_url: str = ""


class CameraUpdate(BaseModel):
    ip: Optional[str] = None
    rtsp_url: Optional[str] = None


class CameraListResponse(BaseModel):
    cameras: List[CameraOut]
    restart: str


class ChunkSummary(BaseModel):
    chunk_id: str
    camera_name: str
    started_at_ist: Optional[str] = None
    zip_path: Optional[str] = None
    verdict: Optional[int] = None
    uploaded_url: Optional[str] = None
    # Seconds since the previous chunk for the SAME camera, and whether that gap looks like
    # normal on-schedule bundling vs. a missed cycle — see routes_capture._compute_gaps().
    gap_sec: Optional[int] = None
    bundling_status: Optional[str] = None  # "ok" | "gap" | None (first chunk seen for this camera)
