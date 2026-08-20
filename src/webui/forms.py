"""
Pure, framework-agnostic helpers for the config UI: which AppConfig fields exist and how
they're grouped/typed/secret-detected, plus manual-capture camera resolution. Kept free of
FastAPI imports so src/webui/test_webui.py can exercise it without the app running.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.config import AppConfig

SECRET_NAME_RE = re.compile(r"(PASSWORD|SECRET|ACCESS_KEY|_KEY$|CONNECTION_STRING|TOKEN)", re.I)

# CAMERAS/CAMERA_IPS/RTSP_URLS are now only a one-time migration seed for
# output/state/cameras.json (see src/camera_store.py) — the running recorder loop no longer
# reads them, so they're hidden from the generic config form entirely. Manage cameras via the
# dedicated Cameras page / /api/cameras instead.
HIDDEN_FIELDS = {"CAMERAS", "CAMERA_IPS", "RTSP_URLS"}

# Display grouping only — AppConfig.model_fields (minus HIDDEN_FIELDS) is always the source of
# truth for which fields exist. Anything not listed here still renders, under "Other" (see
# grouped_fields).
SECTIONS: Dict[str, List[str]] = {
    "Paths / Logging": ["OUTPUT_DIR", "LOG_LEVEL"],
    "Recording": ["FACTORY_NAME", "TARGET_CLASS", "VIDEO_DURATION", "VIDEO_FPS", "VIDEO_WIDTH", "VIDEO_HEIGHT"],
    "Toggles": ["ENABLE_RECORDING", "ENABLE_BUNDLING", "ENABLE_MANIFEST", "ENABLE_GCS_UPLOAD", "ENABLE_API_PUSH"],
    "Bundling": ["ZIP_MODE", "DAILY_MAX_SIZE_MB"],
    "Kafka": ["KAFKA_HOST", "KAFKA_PORT", "KAFKA_GROUP_ID", "CAMERA_TOPICS"],
    "Verdicts / Time": [
        "VERDICT_ANOMALY", "VERDICT_NORMAL", "TIMEZONE", "DAY_START_HOUR",
        "NORMAL_SAMPLES_PER_DAY", "NORMAL_BIN_HOURS", "RANDOM_SEED",
    ],
    "Storage / Upload": [
        "STORAGE_PROVIDER", "GCS_BUCKET", "GCS_PROJECT_ID",
        "AZURE_STORAGE_CONNECTION_STRING", "AZURE_CONTAINER_NAME",
        "S3_BUCKET", "S3_REGION", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_ENDPOINT_URL",
        "FACTORY_LOCATION", "UPLOAD_FACTORY_NAME",
    ],
    "API Push": ["API_URL", "API_EMAIL", "API_PASSWORD", "APP_ID", "PIPELINE_NAME"],
}

# Fixed choices for fields that should render as a dropdown instead of a free-text input.
# STORAGE_PROVIDER's options double as the keys of STORAGE_PROVIDER_FIELDS below.
_S3_FIELDS = ["S3_BUCKET", "S3_REGION", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_ENDPOINT_URL"]

FIELD_OPTIONS: Dict[str, List[str]] = {
    "STORAGE_PROVIDER": ["gcp", "azure", "aws", "acecloud", "krutrim"],
}

# Which Storage/Upload fields are only relevant for a given STORAGE_PROVIDER value — the
# config UI shows only the active provider's fields, hiding the rest (FACTORY_LOCATION and
# UPLOAD_FACTORY_NAME are shared across every provider, so they're deliberately absent here
# and always shown). aws/acecloud/krutrim share the exact same S3-compatible field list,
# matching src/storage/s3_compatible.py's single shared uploader class.
STORAGE_PROVIDER_FIELDS: Dict[str, List[str]] = {
    "gcp": ["GCS_BUCKET", "GCS_PROJECT_ID"],
    "azure": ["AZURE_STORAGE_CONNECTION_STRING", "AZURE_CONTAINER_NAME"],
    "aws": _S3_FIELDS,
    "acecloud": _S3_FIELDS,
    "krutrim": _S3_FIELDS,
}

# Fields that are only ever read once, into an object built at src.main's startup (Kafka
# listener, API publisher, StateStore) — changing these genuinely needs the recorder process
# restarted. Everything else either gets read live inline in src.main's loop already (recording
# params, bundling, factory naming), is recomputed every outer pass now (the camera list, via
# src/camera_store.py), or is only ever consumed by a fresh per-invocation process
# (finalize_day.py's storage/sampling fields, the webui's own request-scoped reads) — so saving
# those needs no restart at all. See src/main.py's _reload_if_env_changed().
RESTART_REQUIRED_FIELDS = {
    "OUTPUT_DIR",  # infra-pinned; changing it live would desync from the mounted volume
    "TIMEZONE",  # baked into StateStore/KafkaVerdictListener at construction
    "KAFKA_HOST", "KAFKA_PORT", "KAFKA_GROUP_ID", "CAMERA_TOPICS",
    "VERDICT_ANOMALY", "VERDICT_NORMAL",
    "ENABLE_API_PUSH", "API_URL", "API_EMAIL", "API_PASSWORD", "APP_ID", "PIPELINE_NAME",
}


def field_options(name: str) -> Optional[List[str]]:
    return FIELD_OPTIONS.get(name)


# Display-only overrides for fields whose real env-var name (kept for .env backward compat,
# see src/config.py's comment on ENABLE_GCS_UPLOAD) no longer matches what it actually does.
# The underlying key/wire format is untouched — only the label shown in the config UI changes.
FIELD_LABELS: Dict[str, str] = {
    "ENABLE_GCS_UPLOAD": "ENABLE_STORAGE_UPLOAD",
}


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name, name)


def grouped_fields() -> List[Tuple[str, List[str]]]:
    """Returns [(section_name, [field_name, ...]), ...]. Every AppConfig field (other than
    HIDDEN_FIELDS) is covered — fields not placed in SECTIONS land in a trailing 'Other'
    section instead of being dropped."""
    all_fields = [n for n in AppConfig.model_fields if n not in HIDDEN_FIELDS]
    placed = set()
    result: List[Tuple[str, List[str]]] = []

    for section, names in SECTIONS.items():
        present = [n for n in names if n in all_fields]
        if present:
            result.append((section, present))
            placed.update(present)

    leftover = [n for n in all_fields if n not in placed]
    if leftover:
        result.append(("Other", leftover))

    return result


def field_type(name: str) -> type:
    return AppConfig.model_fields[name].annotation


def is_secret(name: str) -> bool:
    return bool(SECRET_NAME_RE.search(name))


def coerce(name: str, raw: Optional[str]) -> Any:
    """Converts a raw form/JSON string value back to the type AppConfig expects."""
    t = field_type(name)
    if t is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "on", "yes")
    if t is int:
        if raw in (None, ""):
            return 0
        return int(raw)
    return "" if raw is None else str(raw)


def resolve_camera(
    camera_choice: str,
    adhoc_url: str,
    names: List[str],
    ips: List[str],
    urls: List[Optional[str]],
) -> Tuple[str, str, Optional[str]]:
    """Picks (camera_name, camera_ip, rtsp_url) for a manual capture: either a known camera
    from current CAMERAS config, or an ad-hoc entry when an override RTSP URL is given."""
    adhoc_url = (adhoc_url or "").strip()
    if camera_choice == "__adhoc__" or adhoc_url:
        return "manual-adhoc", "", (adhoc_url or None)

    idx = names.index(camera_choice)
    url = urls[idx] if urls else None
    return camera_choice, ips[idx], url
