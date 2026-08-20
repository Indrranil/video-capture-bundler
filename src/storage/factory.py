from __future__ import annotations

from src.storage.base import StorageUploader
from src.storage.gcp import GCSUploader
from src.storage.azure import AzureBlobUploader
from src.storage.s3_compatible import S3CompatibleUploader


def get_uploader(provider: str, cfg=None) -> StorageUploader:
    """
    Dispatches STORAGE_PROVIDER -> the right uploader, constructed from cfg (defaults to
    src.config.app_config). AWS / Ace Cloud / Ola Krutrim all share S3CompatibleUploader —
    provider choice only changes which S3_* values are configured (S3_ENDPOINT_URL especially).
    """
    if cfg is None:
        from src.config import app_config as cfg

    provider = (provider or "").strip().lower()

    if provider == "gcp":
        return GCSUploader(bucket_name=cfg.GCS_BUCKET, project_id=cfg.GCS_PROJECT_ID)

    if provider == "azure":
        return AzureBlobUploader(
            connection_string=cfg.AZURE_STORAGE_CONNECTION_STRING,
            container_name=cfg.AZURE_CONTAINER_NAME,
        )

    if provider in ("aws", "acecloud", "krutrim"):
        return S3CompatibleUploader(
            bucket_name=cfg.S3_BUCKET,
            region=cfg.S3_REGION,
            access_key_id=cfg.S3_ACCESS_KEY_ID,
            secret_access_key=cfg.S3_SECRET_ACCESS_KEY,
            endpoint_url=cfg.S3_ENDPOINT_URL,
        )

    raise ValueError(f"Unknown STORAGE_PROVIDER: {provider!r}")
