
# src/finalize_day.py
from __future__ import annotations

import os
from typing import List, Dict, Any

from src.config import app_config
from src.state_store import StateStore
from src.selector import select_for_upload
from src.storage import get_uploader

from src.services.api_client import APIClient
from src.services.metadata_publisher import MetadataPublisher


def _must_get(val: str, name: str) -> str:
    if not val:
        raise ValueError(f"Missing required env: {name}")
    return val


def finalize_day() -> None:
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)

    chunks = state.list_chunks()

    anomalies, selected_normals, day_key = select_for_upload(
        chunks=chunks,
        tz_name=app_config.TIMEZONE,
        day_start_hour=app_config.DAY_START_HOUR,
        normal_samples_per_day=app_config.NORMAL_SAMPLES_PER_DAY,
        normal_bin_hours=app_config.NORMAL_BIN_HOURS,
        random_seed=app_config.RANDOM_SEED,
    )

    print(f"[finalize] day_key={day_key} anomalies={len(anomalies)} selected_normals={len(selected_normals)}")

    # --- NEW: API publisher (safe/no-op if disabled) ---
    publisher: MetadataPublisher | None = None
    if app_config.ENABLE_API_PUSH:
        api = APIClient(
            host=app_config.API_URL,
            email=app_config.API_EMAIL,
            password=app_config.API_PASSWORD,
        )
        publisher = MetadataPublisher(
            api_client=api,
            app_id=app_config.APP_ID,
            pipeline_name=app_config.PIPELINE_NAME,
        )
        print("[finalize] API push enabled => publisher initialized")
    else:
        print("[finalize] ENABLE_API_PUSH=false => publisher not started")

    if not app_config.ENABLE_GCS_UPLOAD:
        print("[finalize] ENABLE_GCS_UPLOAD=false => skipping upload")
        return

    factory_location = _must_get(app_config.FACTORY_LOCATION, "FACTORY_LOCATION")
    factory_name = _must_get(
        app_config.upload_factory_name(),
        "UPLOAD_FACTORY_NAME or FACTORY_NAME",
    )
    uploader = get_uploader(app_config.STORAGE_PROVIDER)

    to_upload: List[Dict[str, Any]] = []
    to_upload.extend(anomalies)
    to_upload.extend(selected_normals)

    uploaded = 0
    for rec in to_upload:
        zip_path = rec.get("zip_path")
        if not zip_path or not os.path.exists(zip_path):
            continue

        gs_url = uploader.upload_zip(
            local_zip_path=zip_path,
            ddmmyy=day_key,
            factory_location=factory_location,
            factory_name=factory_name,
        )
        uploaded += 1
        print(f"[upload] {zip_path} -> {gs_url}")

        # --- NEW: publish metadata after upload ---
        if publisher and publisher.enabled():
            meta = {
                "chunk_id": rec.get("chunk_id"),
                "camera_name": rec.get("camera_name"),
                "topic": rec.get("topic"),
                "zip_path": rec.get("zip_path"),
                "gs_url": gs_url,
                "started_at_ist": rec.get("started_at_ist"),
                "event_time_ist": rec.get("event_time_ist"),
                "day_key_ddmmyy": day_key,
                "factory_location": factory_location,
                "factory_name": factory_name,
            }
            publisher.publish_chunk_metadata(
                meta=meta,
                verdict=rec.get("verdict"),
                status_str="success",
            )

    print(f"[finalize] uploaded={uploaded}")


if __name__ == "__main__":
    finalize_day()
