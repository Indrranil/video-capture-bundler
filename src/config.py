
# src/config.py
from __future__ import annotations

from typing import List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


class AppConfig(BaseSettings):
    # Paths / logging
    OUTPUT_DIR: str = Field(default="./output")
    LOG_LEVEL: str = Field(default="INFO")

    # Cameras — LEGACY, one-time migration seed only (see src/camera_store.py). The recorder
    # loop reads output/state/cameras.json now; these three are only consulted the first time
    # that file doesn't exist yet.
    CAMERAS: str = Field(default="cam1")
    CAMERA_IPS: str = Field(default="10.0.0.12")
    RTSP_URLS: str = Field(default="")  # can be empty for stub/local testing

    # Dummy meta (used for manifest)
    FACTORY_NAME: str = Field(default="DUMMY_FACTORY")
    TARGET_CLASS: str = Field(default="DUMMY_OBJ")

    # Recording
    VIDEO_DURATION: int = Field(default=120)
    VIDEO_FPS: int = Field(default=25)
    VIDEO_WIDTH: int = Field(default=1920)
    VIDEO_HEIGHT: int = Field(default=1080)

    # Module toggles
    ENABLE_RECORDING: bool = Field(default=True)
    ENABLE_BUNDLING: bool = Field(default=True)
    ENABLE_MANIFEST: bool = Field(default=True)

    # Bundling
    ZIP_MODE: str = Field(default="chunk")  # "chunk" | "daily"
    DAILY_MAX_SIZE_MB: int = Field(default=2048)

    # Kafka
    KAFKA_HOST: str = Field(default="localhost")
    KAFKA_PORT: int = Field(default=9092)
    KAFKA_GROUP_ID: str = Field(default="video-capture-bundler")
    CAMERA_TOPICS: str = Field(default="")  # cam1:topic1,cam2:topic2

    # Verdict mapping
    VERDICT_ANOMALY: int = Field(default=1)
    VERDICT_NORMAL: int = Field(default=0)

    # IST + day window
    TIMEZONE: str = Field(default="Asia/Kolkata")
    DAY_START_HOUR: int = Field(default=6)

    # Sampling
    NORMAL_SAMPLES_PER_DAY: int = Field(default=12)
    NORMAL_BIN_HOURS: int = Field(default=2)
    RANDOM_SEED: int = Field(default=42)

    # Upload — provider selection. ENABLE_GCS_UPLOAD name kept for backward compat with the
    # deployed .env; it now gates upload to whichever STORAGE_PROVIDER is selected below, not
    # specifically GCS.
    ENABLE_GCS_UPLOAD: bool = Field(default=False)
    STORAGE_PROVIDER: str = Field(default="gcp")  # gcp | azure | aws | acecloud | krutrim

    # GCP
    GCS_BUCKET: str = Field(default="")
    GCS_PROJECT_ID: str = Field(default="polaris-ai-452710")  # was hardcoded in uploader_gcs.py

    # Azure — connection-string based (one field vs. account-name+key+endpoint-suffix)
    AZURE_STORAGE_CONNECTION_STRING: str = Field(default="")
    AZURE_CONTAINER_NAME: str = Field(default="")

    # Generic S3-compatible — shared by aws / acecloud / krutrim; only S3_ENDPOINT_URL changes
    # per provider (blank = real AWS). S3_ENDPOINT_URL must be scheme+host ONLY
    # (e.g. "https://hyd2.kos.olakrutrimsvc.com") — do not paste a bucket-suffixed URL from a
    # provider's console; the bucket goes in S3_BUCKET separately, or every object key doubles
    # the bucket name and every upload fails (see src/storage/s3_compatible.py's docstring).
    S3_BUCKET: str = Field(default="")
    S3_REGION: str = Field(default="")
    S3_ACCESS_KEY_ID: str = Field(default="")
    S3_SECRET_ACCESS_KEY: str = Field(default="")
    S3_ENDPOINT_URL: str = Field(default="")

    FACTORY_LOCATION: str = Field(default="")
    UPLOAD_FACTORY_NAME: str = Field(default="")  # NEW (optional)

    # API push ✅ align with team-style naming
    ENABLE_API_PUSH: bool = Field(default=False)
    API_URL: str = Field(default="")  # NEW (replaces API_HOST usage)
    API_EMAIL: str = Field(default="")
    API_PASSWORD: str = Field(default="")

    # Pipeline identity ✅
    APP_ID: int = Field(default=0)  # NEW
    PIPELINE_NAME: str = Field(default="")  # NEW

    class Config:
        env_file = ".env"
        extra = "ignore"

    def camera_names(self) -> List[str]:
        return _split_csv(self.CAMERAS)

    def camera_ips(self) -> List[str]:
        return _split_csv(self.CAMERA_IPS)

    def rtsp_urls(self) -> List[str]:
        return _split_csv(self.RTSP_URLS)

    def camera_topics(self) -> Dict[str, str]:
        """
        Parses CAMERA_TOPICS="cam1:topicA,cam2:topicB" into dict.
        """
        out: Dict[str, str] = {}
        raw = _split_csv(self.CAMERA_TOPICS)
        for item in raw:
            if ":" not in item:
                continue
            cam, topic = item.split(":", 1)
            cam = cam.strip()
            topic = topic.strip()
            if cam and topic:
                out[cam] = topic
        return out

    def upload_factory_name(self) -> str:
        # Backward compatible fallback
        return self.UPLOAD_FACTORY_NAME or self.FACTORY_NAME

    def validate_lists(self) -> None:
        names = self.camera_names()
        ips = self.camera_ips()
        urls = self.rtsp_urls()

        if len(names) != len(ips):
            raise ValueError("CAMERAS and CAMERA_IPS must have the same number of values.")

        # RTSP_URLS can be empty (for stub). If provided, it must match.
        if urls and len(urls) != len(names):
            raise ValueError("RTSP_URLS must be empty or have the same number of values as CAMERAS.")

    def reload(self) -> None:
        """
        Re-reads .env and applies the fresh values onto THIS SAME singleton instance, in
        place — every module that did `from src.config import app_config` holds a reference
        to this exact object, so mutating its fields (rather than replacing app_config with a
        new object) makes the update visible everywhere immediately, no restart needed.

        Only helps within a single process, though — main.py, the webui, and finalize_day.py
        each have their own separate app_config instance in their own process. src/main.py
        calls this itself (polling .env's mtime) so its long-running loop picks up changes on
        its own; it's meaningless for finalize_day.py (already a fresh process per run, so it
        always reads current .env values with no reload needed) and for the webui (already
        re-reads dotenv_values(".env") per-request rather than going through app_config for
        the fields it edits).
        """
        fresh = AppConfig()
        for name in type(self).model_fields:
            setattr(self, name, getattr(fresh, name))


app_config = AppConfig()
