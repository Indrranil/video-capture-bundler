from __future__ import annotations

import os
import zipfile
from typing import Optional


from src.utils import ensure_dir, day_key_local, file_size_bytes, mb_to_bytes, write_json
from src.manifest import build_manifest
from src.recorder import RecordResult



def bundle_recording(
    output_dir: str,
    record: RecordResult,
    factory_name: str,
    target_class: str,
    zip_mode: str,
    daily_max_size_mb: int,
    enable_bundling: bool,
    enable_manifest: bool,
) -> Optional[str]:
    """
    Returns bundle zip path if created, else None.
    """
    if not enable_bundling:
        return None

    if zip_mode not in ("chunk", "daily"):
        raise ValueError("ZIP_MODE must be 'chunk' or 'daily'.")

    if zip_mode == "chunk":
        return _bundle_chunk(
            output_dir=output_dir,
            record=record,
            factory_name=factory_name,
            target_class=target_class,
            enable_manifest=enable_manifest,
        )

    return _bundle_daily(
        output_dir=output_dir,
        record=record,
        factory_name=factory_name,
        target_class=target_class,
        enable_manifest=enable_manifest,
        daily_max_size_mb=daily_max_size_mb,
    )


def _bundle_chunk(
    output_dir: str,
    record: RecordResult,
    factory_name: str,
    target_class: str,
    enable_manifest: bool,
) -> str:
    day = day_key_local()
    bundle_dir = os.path.join(output_dir, "bundles", record.camera_name, day, "chunks")
    ensure_dir(bundle_dir)

    zip_path = os.path.join(bundle_dir, f"{record.chunk_id}.zip")
    meta_path = os.path.join(bundle_dir, f"{record.chunk_id}.metadata.json")

    if enable_manifest:
        meta = build_manifest(
            factory_name=factory_name,
            target_class=target_class,
            camera_name=record.camera_name,
            camera_ip=record.camera_ip,
            rtsp_url=record.rtsp_url,
            duration_sec=record.duration_sec,
            fps=record.fps,
            width=record.width,
            height=record.height,
            video_filename=os.path.basename(record.video_path),
        )
        write_json(meta_path, meta.to_dict())

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(record.video_path, arcname=os.path.basename(record.video_path))
        if enable_manifest and os.path.exists(meta_path):
            zf.write(meta_path, arcname="metadata.json")

    return zip_path


def _bundle_daily(
    output_dir: str,
    record: RecordResult,
    factory_name: str,
    target_class: str,
    enable_manifest: bool,
    daily_max_size_mb: int,
) -> str:
    day = day_key_local()
    bundle_dir = os.path.join(output_dir, "bundles", record.camera_name, day, "daily")
    ensure_dir(bundle_dir)

    zip_path = os.path.join(bundle_dir, f"{record.camera_name}_{day}.zip")

    # Safety: if daily zip exceeds max size, start a "part-2"
    max_bytes = mb_to_bytes(daily_max_size_mb)
    if os.path.exists(zip_path) and file_size_bytes(zip_path) > max_bytes:
        zip_path = os.path.join(bundle_dir, f"{record.camera_name}_{day}_part2.zip")

    meta = None
    if enable_manifest:
        meta = build_manifest(
            factory_name=factory_name,
            target_class=target_class,
            camera_name=record.camera_name,
            camera_ip=record.camera_ip,
            rtsp_url=record.rtsp_url,
            duration_sec=record.duration_sec,
            fps=record.fps,
            width=record.width,
            height=record.height,
            video_filename=os.path.basename(record.video_path),
        )

    # Append into the daily zip
    with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(record.video_path, arcname=os.path.join("chunks", os.path.basename(record.video_path)))

        # Store manifest per chunk under manifests/<chunk_id>.json
        if enable_manifest and meta is not None:
            zf.writestr(os.path.join("manifests", f"{record.chunk_id}.json"), _json_bytes(meta.to_dict()))

    return zip_path


def _json_bytes(d: dict) -> bytes:
    import json
    return json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8")
