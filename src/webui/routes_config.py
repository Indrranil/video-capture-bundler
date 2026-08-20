from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace

from dotenv import dotenv_values, set_key
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from src.config import AppConfig, app_config
from src.storage import get_uploader
from src.webui import docker_ctl
from src.webui.forms import (
    RESTART_REQUIRED_FIELDS,
    STORAGE_PROVIDER_FIELDS,
    coerce,
    field_label,
    field_options,
    field_type,
    grouped_fields,
    is_secret,
)
from src.webui.schemas import ConfigFieldOut, ConfigResponse, ConfigSectionOut, ConfigUpdateRequest

router = APIRouter(prefix="/api/config", tags=["config"])

ENV_PATH = ".env"


def _type_name(t: type) -> str:
    if t is bool:
        return "bool"
    if t is int:
        return "int"
    return "str"


def _merge_values(raw_values: dict) -> dict:
    """Merges submitted field values over the current .env, coercing types and treating a
    blank secret submission as 'keep existing value' — shared by the real save (below) and
    /test-storage, so testing with the form's current (possibly unsaved) values behaves
    exactly like testing what would actually get saved."""
    current = dotenv_values(ENV_PATH)
    merged = dict(current)
    for name, raw in raw_values.items():
        if name not in AppConfig.model_fields:
            continue
        if is_secret(name) and (raw is None or raw == ""):
            continue
        merged[name] = str(coerce(name, raw))
    return merged


@router.get("", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    current = dotenv_values(ENV_PATH)
    sections = []
    for section_name, names in grouped_fields():
        fields = []
        for name in names:
            secret = is_secret(name)
            raw = current.get(name)
            if raw is None:
                raw = str(AppConfig.model_fields[name].default)
            value = "" if secret else raw
            fields.append(
                ConfigFieldOut(
                    key=name,
                    label=field_label(name),
                    value=value,
                    type=_type_name(field_type(name)),
                    secret=secret,
                    options=field_options(name),
                )
            )
        sections.append(ConfigSectionOut(name=section_name, fields=fields))
    return ConfigResponse(sections=sections, provider_field_groups=STORAGE_PROVIDER_FIELDS)


@router.post("")
def update_config(body: ConfigUpdateRequest) -> dict:
    current = dotenv_values(ENV_PATH)
    merged = _merge_values(body.values)

    try:
        AppConfig(**merged).validate_lists()
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    changed = {k: v for k, v in merged.items() if current.get(k) != v}
    for key, value in changed.items():
        set_key(ENV_PATH, key, value)

    restart_message = ""
    if changed:
        if set(changed) & RESTART_REQUIRED_FIELDS:
            restart_message = docker_ctl.restart_recorder(app_config.OUTPUT_DIR)
        else:
            # src.main polls .env's mtime and reloads these fields in place on its own — see
            # _reload_if_env_changed() there. No restart needed, so none is even attempted.
            restart_message = "Applies automatically within a few seconds — no restart needed."

    return {"ok": True, "changed": list(changed.keys()), "restart": restart_message}


@router.post("/test-storage")
async def test_storage(file: UploadFile = File(...), values: str = Form(...)) -> dict:
    """
    Uploads the given file for real, using the CURRENT (possibly unsaved) Storage/Upload form
    values — reuses _merge_values so a blank secret input still resolves to whatever real
    secret is already in .env, exactly like a real save would. Nothing here writes to .env or
    restarts anything; it's purely "would these credentials actually work." Always returns 200
    with an ok flag — a failed test is an expected outcome to report, not a server error. The
    uploaded object is NOT deleted afterward (this repo has no delete-from-provider capability
    yet) — it lands under factory_location=connection-test so it's easy to spot/clean up.
    """
    try:
        raw_values = json.loads(values)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="values must be a JSON object")

    merged = _merge_values(raw_values)
    full = {name: field.default for name, field in AppConfig.model_fields.items()}
    full.update(merged)
    fake_cfg = SimpleNamespace(**full)
    provider = full.get("STORAGE_PROVIDER", "gcp")

    # A plain NamedTemporaryFile gets a random name, which upload_zip() would then use as the
    # object key (it basenames local_zip_path) — using a real temp dir + the original filename
    # instead means the uploaded test object is actually identifiable in the bucket afterward.
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, os.path.basename(file.filename or "testfile"))
            with open(tmp_path, "wb") as f:
                f.write(await file.read())

            uploader = get_uploader(provider, fake_cfg)
            today = datetime.now(timezone.utc).strftime("%d%m%y")
            url = uploader.upload_zip(
                local_zip_path=tmp_path,
                ddmmyy=today,
                factory_location="connection-test",
                factory_name="test",
            )
        return {"ok": True, "message": f"Upload succeeded -> {url}"}
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}
