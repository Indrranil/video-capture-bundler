# src/main.py
from __future__ import annotations

import time

from src.config import app_config
from src.recorder import record_chunk_avi
from src.bundler import bundle_recording
from src.state_store import StateStore
from src.kafka_listener import KafkaVerdictListener

from src.services.api_client import APIClient
from src.services.metadata_publisher import MetadataPublisher


def main() -> None:
    app_config.validate_lists()

    names = app_config.camera_names()
    ips = app_config.camera_ips()
    urls = app_config.rtsp_urls()

    # If RTSP_URLS empty, we pass None per camera
    if not urls:
        urls = [None] * len(names)

    print(f"[boot] cameras={len(names)} zip_mode={app_config.ZIP_MODE}")
    print(f"[boot] ENABLE_RECORDING={app_config.ENABLE_RECORDING} ENABLE_BUNDLING={app_config.ENABLE_BUNDLING}")

    # State store
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)

    # --- NEW: API publisher (safe/no-op if disabled) ---
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

    # Kafka listener (topic per camera)
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
    # This keeps the container alive without creating any video files.
    if not app_config.ENABLE_RECORDING:
        print("[boot] ENABLE_RECORDING=false => dry-run idle mode; no recording files will be created")
        while True:
            time.sleep(60)

    while True:
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
