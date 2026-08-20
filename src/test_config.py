"""
Plain-assert self-check for src/config.py's live-reload mechanism. Run: python -m src.test_config
Chdir's into a throwaway temp dir (AppConfig's env_file=".env" is a relative path) so this
never touches the real .env.
"""
from __future__ import annotations

import os
import tempfile

from src.config import AppConfig


def test_reload_updates_same_object_in_place() -> None:
    orig_cwd = os.getcwd()
    tmp_dir = tempfile.mkdtemp()
    try:
        os.chdir(tmp_dir)
        with open(".env", "w", encoding="utf-8") as f:
            f.write("VIDEO_DURATION=60\n")

        cfg = AppConfig()
        assert cfg.VIDEO_DURATION == 60

        with open(".env", "w", encoding="utf-8") as f:
            f.write("VIDEO_DURATION=999\n")

        same_object = cfg
        cfg.reload()
        assert cfg is same_object, "reload() must mutate in place, not replace the object"
        assert cfg.VIDEO_DURATION == 999
    finally:
        os.chdir(orig_cwd)


if __name__ == "__main__":
    test_reload_updates_same_object_in_place()
    print("ok")
