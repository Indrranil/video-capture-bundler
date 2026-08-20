"""
Plain-assert self-check for src/camera_store.py. Run: python -m src.test_camera_store
Uses a throwaway temp dir so it never touches the real output/state/cameras.json.
"""
from __future__ import annotations

import shutil
import tempfile

from src import camera_store


class _FakeCfg:
    def camera_names(self):
        return ["cam1"]

    def camera_ips(self):
        return ["10.0.0.1"]

    def rtsp_urls(self):
        return ["rtsp://existing"]


def test_seed_and_crud() -> None:
    tmp = tempfile.mkdtemp()
    try:
        # first call seeds from the legacy CSV fields
        cameras = camera_store.list_cameras(tmp, cfg=_FakeCfg())
        assert cameras == [{"name": "cam1", "ip": "10.0.0.1", "rtsp_url": "rtsp://existing"}]

        camera_store.add_camera(tmp, "cam2", "10.0.0.2", "")
        cameras = camera_store.list_cameras(tmp)
        assert {c["name"] for c in cameras} == {"cam1", "cam2"}

        try:
            camera_store.add_camera(tmp, "cam2", "10.0.0.3", "")
            assert False, "expected duplicate-name error"
        except ValueError:
            pass

        camera_store.update_camera(tmp, "cam2", ip="10.0.0.99")
        cameras = camera_store.list_cameras(tmp)
        assert next(c for c in cameras if c["name"] == "cam2")["ip"] == "10.0.0.99"

        camera_store.delete_camera(tmp, "cam1")
        cameras = camera_store.list_cameras(tmp)
        assert {c["name"] for c in cameras} == {"cam2"}

        try:
            camera_store.delete_camera(tmp, "does-not-exist")
            assert False, "expected KeyError"
        except KeyError:
            pass

        try:
            camera_store.add_camera(tmp, "", "10.0.0.5")
            assert False, "expected ValueError for blank name"
        except ValueError:
            pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_seed_and_crud()
    print("ok")
