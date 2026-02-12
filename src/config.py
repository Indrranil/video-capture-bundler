from __future__ import annotations

from typing import List
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

    # Dummy meta
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

    class Config:
        env_file = ".env"
        extra = "ignore"

    def camera_names(self) -> List[str]:
        return _split_csv(self.CAMERAS)

    def camera_ips(self) -> List[str]:
        return _split_csv(self.CAMERA_IPS)

    def rtsp_urls(self) -> List[str]:
        return _split_csv(self.RTSP_URLS)

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
