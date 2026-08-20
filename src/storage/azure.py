from __future__ import annotations

import os

from azure.storage.blob import BlobServiceClient

from src.storage.base import StorageUploader, _must_get, _object_key


class AzureBlobUploader(StorageUploader):
    def __init__(self, connection_string: str, container_name: str) -> None:
        self.connection_string = _must_get(connection_string, "AZURE_STORAGE_CONNECTION_STRING")
        self.container_name = _must_get(container_name, "AZURE_CONTAINER_NAME")

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

        client = BlobServiceClient.from_connection_string(self.connection_string)
        blob_client = client.get_blob_client(container=self.container_name, blob=object_name)
        with open(local_zip_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)

        url = blob_client.url
        print(f"[azure] uploaded -> {url}")
        return url
