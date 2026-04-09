
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

    # Cameras
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

    # Upload (GCS) ✅ make these distinct (avoid FACTORY_NAME collision)
    ENABLE_GCS_UPLOAD: bool = Field(default=False)
    GCS_BUCKET: str = Field(default="")
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


app_config = AppConfig()
