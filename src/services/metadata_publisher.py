# src/services/metadata_publisher.py
from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.api_client import APIClient, APIEndpoint, APIResponseStatus

class MetadataPublisher:
    """
    Creates a pipeline_session once, then for each chunk creates:
      - pipeline_session_output
      - pipeline_session_output_units (one unit per metadata key)
    """

    def __init__(self, api_client: APIClient, app_id: int, pipeline_name: str) -> None:
        self._api_client = api_client
        self._pipeline_session_id: Optional[int] = None

        if not app_id or not pipeline_name:
            return  # keep disabled if not configured

        status, payload = self._api_client.post(
            endpoint=APIEndpoint.CREATE_PIPELINE_SESSION,
            data={"pipeline_id": app_id, "name": pipeline_name},
        )
        if status == APIResponseStatus.OK and payload:
            self._pipeline_session_id = payload.get("id")

    def enabled(self) -> bool:
        return self._pipeline_session_id is not None

    def publish_chunk_metadata(self, meta: Dict[str, Any], verdict: Optional[int], status_str: str = "success") -> bool:
        """
        meta: flat dict of key->value (chunk_id, camera_name, zip_path, gs_url, times, etc)
        verdict: 1 anomaly, 0 normal, or None
        """
        if not self._pipeline_session_id:
            return False

        # Create pipeline_session_output
        st, out = self._api_client.post(
            endpoint=APIEndpoint.CREATE_PIPELINE_SESSION_OUTPUT,
            data={"pipeline_session_id": self._pipeline_session_id},
        )
        if st != APIResponseStatus.OK or not out:
            return False

        output_id = out.get("id")
        if not output_id:
            return False

        v = "" if verdict is None else str(int(verdict))

        # Create units
        for k, val in meta.items():
            payload = {
                "pipeline_session_output_id": output_id,
                "output_key": str(k),
                "output_value": "" if val is None else str(val),
                "verdict": v,             # same verdict for all keys
                "name": str(k),           # keeps name meaningful
                "status": status_str,     # "success" or "error"
            }
            st2, _ = self._api_client.post(APIEndpoint.CREATE_PIPELINE_SESSION_OUTPUT_UNIT, payload)
            if st2 != APIResponseStatus.OK:
                # do NOT hard-fail the whole app; just stop publishing for this chunk
                return False

        return True
