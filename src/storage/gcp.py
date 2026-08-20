from __future__ import annotations

import os

from google.cloud import storage

from src.storage.base import StorageUploader, _must_get, _object_key


class GCSUploader(StorageUploader):
    def __init__(self, bucket_name: str, project_id: str) -> None:
        self.bucket_name = _must_get(bucket_name, "GCS_BUCKET")
        self.project_id = _must_get(project_id, "GCS_PROJECT_ID")

    def upload_zip(
        self,
        local_zip_path: str,
        ddmmyy: str,
        factory_location: str,
        factory_name: str,
    ) -> str:
        if not os.path.exists(local_zip_path):
            raise FileNotFoundError(f"Zip not found: {local_zip_path}")

        zip_file = os.path.basename(local_zip_path)
        object_name = _object_key(ddmmyy, factory_location, factory_name, zip_file)

        # Force project explicitly to avoid ADC project-detection issues
        client = storage.Client(project=self.project_id)
        bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_filename(local_zip_path)

        gs_url = f"gs://{self.bucket_name}/{object_name}"
        print(f"[gcs] uploaded -> {gs_url}")
        return gs_url
