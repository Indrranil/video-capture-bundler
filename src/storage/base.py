from __future__ import annotations

from abc import ABC, abstractmethod


def _must_get(val: str, name: str) -> str:
    if not val:
        raise ValueError(f"Missing required value: {name}")
    return val


def _object_key(ddmmyy: str, factory_location: str, factory_name: str, zip_file: str) -> str:
    """
    Shared object-key convention for every provider:
        recorder-service/<ddmmyy>/<factory_location>/<factory_name>/<zip_file>
    """
    return f"recorder-service/{ddmmyy}/{factory_location}/{factory_name}/{zip_file}"


class StorageUploader(ABC):
    @abstractmethod
    def upload_zip(
        self,
        local_zip_path: str,
        ddmmyy: str,
        factory_location: str,
        factory_name: str,
    ) -> str:
        """
        Uploads local_zip_path under the shared object-key convention and returns the
        fully-qualified remote URL (gs://..., https://<account>.blob.core.windows.net/..., s3://...).
        """
        raise NotImplementedError
