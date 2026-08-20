"""
Plain-assert self-check for the webui package. Run: python -m src.webui.test_webui
No pytest — matches this repo's "no test suite yet, don't invent a framework" convention.
"""
from __future__ import annotations

import os
import tempfile

from src.config import AppConfig
from src.webui import docker_ctl, routes_config
from src.webui.forms import (
    FIELD_LABELS,
    FIELD_OPTIONS,
    HIDDEN_FIELDS,
    RESTART_REQUIRED_FIELDS,
    STORAGE_PROVIDER_FIELDS,
    coerce,
    grouped_fields,
    resolve_camera,
)


def test_coerce_round_trip() -> None:
    assert coerce("VIDEO_FPS", "30") == 30
    assert coerce("ENABLE_RECORDING", "on") is True
    assert coerce("ENABLE_RECORDING", "true") is True
    assert coerce("ENABLE_RECORDING", None) is False
    assert coerce("FACTORY_NAME", None) == ""
    assert coerce("FACTORY_NAME", "ASSAM_UNIT_3") == "ASSAM_UNIT_3"


def test_grouped_fields_covers_every_field() -> None:
    covered = {n for _, names in grouped_fields() for n in names}
    expected = set(AppConfig.model_fields) - HIDDEN_FIELDS
    assert covered == expected, "a field got dropped from the config form"


def test_storage_provider_fields_consistent() -> None:
    # STORAGE_PROVIDER_FIELDS' keys must match STORAGE_PROVIDER's dropdown options exactly, and
    # every field name it references must be a real AppConfig field — a typo here would
    # silently break the config UI's provider-aware show/hide instead of raising anywhere.
    assert set(STORAGE_PROVIDER_FIELDS.keys()) == set(FIELD_OPTIONS["STORAGE_PROVIDER"])
    for fields in STORAGE_PROVIDER_FIELDS.values():
        for name in fields:
            assert name in AppConfig.model_fields, f"{name} is not a real AppConfig field"


def test_field_labels_reference_real_fields() -> None:
    for name in FIELD_LABELS:
        assert name in AppConfig.model_fields, f"{name} is not a real AppConfig field"


def test_restart_required_fields_reference_real_fields() -> None:
    for name in RESTART_REQUIRED_FIELDS:
        assert name in AppConfig.model_fields, f"{name} is not a real AppConfig field"
    # Storage/Upload fields must NOT be in here — that's the whole point of this change
    # (saving a provider/bucket/key edit shouldn't even attempt a restart).
    for name in STORAGE_PROVIDER_FIELDS["gcp"] + STORAGE_PROVIDER_FIELDS["aws"]:
        assert name not in RESTART_REQUIRED_FIELDS


def test_resolve_camera() -> None:
    names, ips, urls = ["cam1"], ["10.0.0.12"], [None]
    assert resolve_camera("cam1", "", names, ips, urls) == ("cam1", "10.0.0.12", None)

    camera_name, camera_ip, rtsp = resolve_camera("__adhoc__", "rtsp://x", names, ips, urls)
    assert camera_name == "manual-adhoc"
    assert rtsp == "rtsp://x"


def test_merge_values_keeps_existing_secret_on_blank() -> None:
    # This is the logic /api/config/test-storage leans on: testing with the form's current
    # (possibly-unsaved) values must still resolve a left-blank secret to the REAL value
    # already in .env, exactly like a real save would — otherwise "test upload" would always
    # fail with an empty secret the moment the user hasn't retyped it.
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False)
    tmp.write("API_PASSWORD=real-secret\nLOG_LEVEL=INFO\n")
    tmp.close()

    orig_path = routes_config.ENV_PATH
    routes_config.ENV_PATH = tmp.name
    try:
        merged = routes_config._merge_values({"API_PASSWORD": "", "LOG_LEVEL": "DEBUG"})
        assert merged["API_PASSWORD"] == "real-secret"  # blank submission keeps existing
        assert merged["LOG_LEVEL"] == "DEBUG"  # non-secret overwritten normally

        merged2 = routes_config._merge_values({"API_PASSWORD": "new-secret"})
        assert merged2["API_PASSWORD"] == "new-secret"  # non-blank overrides
    finally:
        routes_config.ENV_PATH = orig_path
        os.unlink(tmp.name)


def test_restart_recorder_never_raises() -> None:
    # A container name guaranteed not to exist, and a fresh temp dir with no main.pid — both
    # restart strategies fail, but the function must return a message, never raise. Uses a
    # nonsense container name deliberately so this can never touch a real running container.
    tmp = tempfile.mkdtemp()
    message = docker_ctl.restart_recorder(tmp, container_name="definitely-not-a-real-container-xyz")
    assert isinstance(message, str) and message


def test_app_imports() -> None:
    from src.webui.main import app

    assert app is not None


if __name__ == "__main__":
    test_coerce_round_trip()
    test_grouped_fields_covers_every_field()
    test_storage_provider_fields_consistent()
    test_restart_required_fields_reference_real_fields()
    test_field_labels_reference_real_fields()
    test_resolve_camera()
    test_merge_values_keeps_existing_secret_on_blank()
    test_restart_recorder_never_raises()
    test_app_imports()
    print("ok")
