from __future__ import annotations

import time


from src.config import app_config
from src.recorder import record_chunk_avi
from src.bundler import bundle_recording

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

    while True:
        for i in range(len(names)):
            camera_name = names[i]
            camera_ip = ips[i]
            rtsp_url = urls[i]

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

            if rec.ok:
                print(f"[record] OK camera={camera_name} file={rec.video_path} dur={rec.duration_sec}s")
            else:
                print(f"[record] WARN camera={camera_name} file={rec.video_path} err={rec.error}")

            zip_path = bundle_recording(
                output_dir=app_config.OUTPUT_DIR,
                record=rec,
                factory_name=app_config.FACTORY_NAME,
                target_class=app_config.TARGET_CLASS,
                zip_mode=app_config.ZIP_MODE,
                daily_max_size_mb=app_config.DAILY_MAX_SIZE_MB,
                enable_bundling=app_config.ENABLE_BUNDLING,
                enable_manifest=app_config.ENABLE_MANIFEST,
            )

            if zip_path:
                print(f"[bundle] OK mode={app_config.ZIP_MODE} zip={zip_path}")

        # tiny sleep to avoid tight loops in stub mode
        time.sleep(0.2)


if __name__ == "__main__":
    main()
