# src/uploader_gcs.py
from __future__ import annotations

import os
from google.cloud import storage


def _must_get(val: str, name: str) -> str:
    if not val:
        raise ValueError(f"Missing required value: {name}")
    return val


def upload_zip_to_gcs(
    bucket_name: str,
    local_zip_path: str,
    ddmmyy: str,
    factory_location: str,
    factory_name: str,
) -> str:
    """
    Upload path:
        recorder-service/ddmmyy/<factory_location>/<factory_name>/<zip_file>

    Example:
        recorder-service/120226/Nashik/cam1/cam1_120226_101500.zip

    Returns:
        gs://bucket/path
    """

    # --- Validation (prevents silent bad uploads) ---
    _must_get(bucket_name, "bucket_name")
    _must_get(factory_location, "factory_location")
    _must_get(factory_name, "factory_name")

    if not os.path.exists(local_zip_path):
        raise FileNotFoundError(f"Zip not found: {local_zip_path}")

    # --- Build object path ---
    zip_file = os.path.basename(local_zip_path)
    object_name = f"recorder-service/{ddmmyy}/{factory_location}/{factory_name}/{zip_file}"

    # --- Upload ---
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)

    blob.upload_from_filename(local_zip_path)

    gs_url = f"gs://{bucket_name}/{object_name}"
    print(f"[gcs] uploaded -> {gs_url}")

    return gs_url
