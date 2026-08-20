from __future__ import annotations

import os

import boto3
from botocore.config import Config

from src.storage.base import StorageUploader, _must_get, _object_key

# Without this, a bad/unreachable endpoint hangs on boto3's default (much longer) connect
# timeout instead of failing fast — finalize_day.py is a batch job, not something that should
# block for minutes on one bad provider config. limited retries for the same reason.
_CLIENT_CONFIG = Config(connect_timeout=10, read_timeout=30, retries={"max_attempts": 2, "mode": "standard"})


class S3CompatibleUploader(StorageUploader):
    """
    One class for every S3-compatible backend (AWS, Ace Cloud, Ola Krutrim, ...) —
    provider identity is just which bucket/region/endpoint/creds get passed in.
    Leave endpoint_url blank for real AWS; set it to the provider's endpoint otherwise.

    endpoint_url must be scheme+host ONLY (e.g. "https://hyd2.kos.olakrutrimsvc.com") — do NOT
    include the bucket name in it even if your provider's console shows you a URL that looks
    like ".../<bucket>". The bucket is supplied separately (bucket_name/S3_BUCKET); pasting a
    bucket-suffixed URL in here doubles the bucket into the object path
    (".../<bucket>/<bucket>/recorder-service/...") and every upload will fail.
    """

    def __init__(
        self,
        bucket_name: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str = "",
    ) -> None:
        self.bucket_name = _must_get(bucket_name, "S3_BUCKET")
        self.region = region
        self.access_key_id = _must_get(access_key_id, "S3_ACCESS_KEY_ID")
        self.secret_access_key = _must_get(secret_access_key, "S3_SECRET_ACCESS_KEY")
        self.endpoint_url = endpoint_url or None

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

        client = boto3.client(
            "s3",
            region_name=self.region or None,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            config=_CLIENT_CONFIG,
        )
        client.upload_file(local_zip_path, self.bucket_name, object_name)

        url = f"s3://{self.bucket_name}/{object_name}"
        print(f"[s3] uploaded -> {url}")
        return url
