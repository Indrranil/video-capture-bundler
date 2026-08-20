"""
Plain-assert self-check for the provider-dispatch branch in src/storage/factory.py.
Run: python -m src.storage.test_storage_factory
No pytest, no mocking, no network calls — just construct each concrete class directly
(bypassing app_config) and check get_uploader()'s unknown-provider error path.
"""
from __future__ import annotations

from src.storage.gcp import GCSUploader
from src.storage.azure import AzureBlobUploader
from src.storage.s3_compatible import S3CompatibleUploader
from src.storage.factory import get_uploader


class _FakeCfg:
    GCS_BUCKET = "bucket"
    GCS_PROJECT_ID = "project"
    AZURE_STORAGE_CONNECTION_STRING = "conn"
    AZURE_CONTAINER_NAME = "container"
    S3_BUCKET = "bucket"
    S3_REGION = "us-east-1"
    S3_ACCESS_KEY_ID = "key"
    S3_SECRET_ACCESS_KEY = "secret"
    S3_ENDPOINT_URL = ""


def test_dispatch() -> None:
    cfg = _FakeCfg()

    assert isinstance(get_uploader("gcp", cfg), GCSUploader)
    assert isinstance(get_uploader("azure", cfg), AzureBlobUploader)
    for provider in ("aws", "acecloud", "krutrim"):
        assert isinstance(get_uploader(provider, cfg), S3CompatibleUploader)

    try:
        get_uploader("bogus", cfg)
        assert False, "expected ValueError for unknown provider"
    except ValueError:
        pass


def test_missing_required_field_raises() -> None:
    cfg = _FakeCfg()
    cfg.GCS_BUCKET = ""
    try:
        get_uploader("gcp", cfg)
        assert False, "expected ValueError for missing GCS_BUCKET"
    except ValueError:
        pass


if __name__ == "__main__":
    test_dispatch()
    test_missing_required_field_raises()
    print("ok")
