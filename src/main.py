# src/main.py
from __future__ import annotations

import os
import signal
import sys
import time

from src.config import app_config
from src import camera_store
from src.recorder import record_chunk_avi
from src.bundler import bundle_recording
from src.state_store import StateStore
from src.kafka_listener import KafkaVerdictListener
from src.utils import ensure_dir

from src.services.api_client import APIClient
from src.services.metadata_publisher import MetadataPublisher

_env_mtime = None


def _write_pidfile(output_dir: str) -> None:
    """Lets src.webui.docker_ctl.restart_recorder() find and signal this process when
    there's no Docker container to restart instead (native/non-Docker runs)."""
    path = os.path.join(output_dir, "state", "main.pid")
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def _reexec_on_sighup(signum, frame) -> None:
    # Re-exec ourselves in place: the simplest way to make a fresh `AppConfig()` singleton
    # (and everything imported at module scope from it) pick up new .env values, short of
    # refactoring every module off of import-time config access.
    #
    # Deliberately hardcoded to `-m src.main` rather than replaying sys.argv: under `python -m
    # src.main`, sys.argv[0] resolves to a plain script path (e.g. ".../src/main.py"), and
    # execv-ing that runs it as a bare script instead of a package module — `sys.path` then
    # only has src/ on it, not the repo root, so `from src.config import ...` breaks. Always
    # re-launching via -m keeps that import machinery intact.
    print("[main] SIGHUP received -> re-executing to pick up new config", flush=True)
    os.execv(sys.executable, [sys.executable, "-m", "src.main"])


def _reload_if_env_changed() -> None:
    """
    Poll .env's mtime and app_config.reload() in place when it changes — this is what makes
    most config edits (recording params, bundling, factory naming — anything already read live
    as `app_config.X` inline below) and camera add/edit/delete (camera_store.list_cameras() is
    also recomputed every outer pass now) take effect within moments, with no restart, no
    Docker, no signal needed at all.

    KAFKA_*/CAMERA_TOPICS/VERDICT_*/TIMEZONE/ENABLE_API_PUSH/API_*/APP_ID/PIPELINE_NAME/
    OUTPUT_DIR are baked into objects constructed once below (Kafka listener, API publisher,
    StateStore) and still need an actual restart to change — see RESTART_REQUIRED_FIELDS in
    src/webui/forms.py, which is what decides whether the config UI even attempts one.
    """
    global _env_mtime
    try:
        mtime = os.path.getmtime(".env")
    except OSError:
        return
    if _env_mtime is None:
        _env_mtime = mtime
        return
    if mtime != _env_mtime:
        _env_mtime = mtime
        app_config.reload()
        print("[main] .env changed on disk -> reloaded config", flush=True)


def main() -> None:
    # Line-buffer stdout regardless of how this was launched (plain `python -m src.main` vs.
    # `python -u -m src.main`) so log lines show up promptly instead of sitting in a block
    # buffer until it fills or the process exits — matters most right after a SIGHUP restart,
    # where the re-exec's argv doesn't carry a `-u` flag even if the original invocation had one.
    sys.stdout.reconfigure(line_buffering=True)

    app_config.validate_lists()
    _write_pidfile(app_config.OUTPUT_DIR)
    if hasattr(signal, "SIGHUP"):  # not available on Windows
        signal.signal(signal.SIGHUP, _reexec_on_sighup)

    print(f"[boot] zip_mode={app_config.ZIP_MODE}")
    print(f"[boot] ENABLE_RECORDING={app_config.ENABLE_RECORDING} ENABLE_BUNDLING={app_config.ENABLE_BUNDLING}")

    # State store — TIMEZONE is baked in here at construction; changing it later needs a restart.
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)

    # --- API publisher (safe/no-op if disabled) — also fixed at construction time ---
    publisher: MetadataPublisher | None = None
    if app_config.ENABLE_API_PUSH:
        api = APIClient(
            host=app_config.API_URL,
            email=app_config.API_EMAIL,
            password=app_config.API_PASSWORD,
        )
        publisher = MetadataPublisher(
            api_client=api,
            app_id=app_config.APP_ID,
            pipeline_name=app_config.PIPELINE_NAME,
        )
        print("[boot] API push enabled => publisher initialized")
    else:
        print("[boot] ENABLE_API_PUSH is false => publisher not started")

    # Kafka listener (topic per camera) — also fixed at construction time.
    cam_topics = app_config.camera_topics()
    if not cam_topics:
        print("[boot] CAMERA_TOPICS empty => Kafka listener not started")
        listener = None
    else:
        listener = KafkaVerdictListener(
            kafka_host=app_config.KAFKA_HOST,
            kafka_port=app_config.KAFKA_PORT,
            group_id=app_config.KAFKA_GROUP_ID,
            camera_to_topic=cam_topics,
            state=state,
            verdict_anomaly=app_config.VERDICT_ANOMALY,
            verdict_normal=app_config.VERDICT_NORMAL,
        )
        listener.start()
        print(f"[boot] Kafka listener started for {len(cam_topics)} topics")

    # IMPORTANT:
    # When recording is disabled, do not call record_chunk_avi().
    # That function creates stub AVI files even with enable_recording=False.
    # This keeps the container alive without producing files. Poll (rather than sleep once
    # forever) so flipping ENABLE_RECORDING back on via the config UI is actually noticed.
    if not app_config.ENABLE_RECORDING:
        print("[boot] ENABLE_RECORDING=false => dry-run idle mode; no recording files will be created")
        while not app_config.ENABLE_RECORDING:
            time.sleep(5)
            _reload_if_env_changed()
        print("[main] ENABLE_RECORDING flipped true -> resuming normal recording loop", flush=True)

    while True:
        _reload_if_env_changed()

        # Cameras live in output/state/cameras.json (see src/camera_store.py); recomputed every
        # outer pass so add/edit/delete via the Cameras page take effect without a restart.
        cameras = camera_store.list_cameras(app_config.OUTPUT_DIR)
        names = [c["name"] for c in cameras]
        ips = [c["ip"] for c in cameras]
        urls = [c["rtsp_url"] or None for c in cameras]

        for i in range(len(names)):
            camera_name = names[i]
            camera_ip = ips[i]
            rtsp_url = urls[i]

            # topic is the camera identifier in Kafka
            topic = cam_topics.get(camera_name, "")

            rec = record_chunk_avi(
                output_dir=app_config.OUTPUT_DIR,
                camera_name=camera_name,
                camera_ip=camera_ip,
                rtsp_url=rtsp_url,
                duration_sec=app_config.VIDEO_DURATION,
                fps=app_config.VIDEO_FPS,
                width=app_config.VIDEO_WIDTH,
                height=app_config.VIDEO_HEIGHT,
                enable_recording=app_config.ENABLE_RECORDING,
            )

            # now we know chunk_id => mark as current
            state.set_current_chunk(camera_name=camera_name, chunk_id=rec.chunk_id, topic=topic)

            if rec.ok:
                print(f"[record] OK camera={camera_name} file={rec.video_path} dur={rec.duration_sec}s")
            else:
                print(f"[record] WARN camera={camera_name} file={rec.video_path} err={rec.error}")

            zip_path = bundle_recording(
                output_dir=app_config.OUTPUT_DIR,
                record=rec,
                factory_name=app_config.FACTORY_NAME,  # manifest meta
                target_class=app_config.TARGET_CLASS,
                zip_mode=app_config.ZIP_MODE,
                daily_max_size_mb=app_config.DAILY_MAX_SIZE_MB,
                enable_bundling=app_config.ENABLE_BUNDLING,
                enable_manifest=app_config.ENABLE_MANIFEST,
            )

            if zip_path:
                state.set_zip_path(rec.chunk_id, zip_path)
                print(f"[bundle] OK mode={app_config.ZIP_MODE} zip={zip_path}")

                # --- NEW: publish metadata after zip exists ---
                if publisher and publisher.enabled():
                    chunks = state.list_chunks()
                    chunk_rec = chunks.get(rec.chunk_id, {}) if isinstance(chunks, dict) else {}

                    meta = {
                        "chunk_id": rec.chunk_id,
                        "camera_name": rec.camera_name,
                        "camera_ip": rec.camera_ip,
                        "rtsp_url": rec.rtsp_url,
                        "video_path": rec.video_path,
                        "zip_path": zip_path,
                        "started_at_ist": chunk_rec.get("started_at_ist"),
                        "event_time_ist": chunk_rec.get("event_time_ist"),
                        "duration_sec": rec.duration_sec,
                        "fps": rec.fps,
                        "width": rec.width,
                        "height": rec.height,
                    }

                    publisher.publish_chunk_metadata(
                        meta=meta,
                        verdict=chunk_rec.get("verdict"),
                        status_str="success",
                    )

        time.sleep(0.2)


if __name__ == "__main__":
    main()
