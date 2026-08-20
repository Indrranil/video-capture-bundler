from __future__ import annotations

import os
import signal
from typing import Optional

import docker


def _restart_via_docker(name: str) -> Optional[str]:
    """Returns None on success, or an error string."""
    try:
        client = docker.from_env()
        client.containers.get(name).restart()
        return None
    except Exception as e:
        return str(e)


def _restart_via_pidfile(output_dir: str) -> Optional[str]:
    """Sends SIGHUP to the PID src.main wrote at startup, asking it to re-exec itself so a
    fresh AppConfig() picks up the new .env values. Returns None on success, or an error
    string. This is the fallback for native (non-Docker) runs, where there's no container
    to restart."""
    if not hasattr(signal, "SIGHUP"):
        return "SIGHUP not supported on this platform"

    path = os.path.join(output_dir, "state", "main.pid")
    if not os.path.exists(path):
        return f"no PID file at {path} — is src.main running?"

    try:
        with open(path, encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        return None
    except Exception as e:
        return str(e)


def restart_recorder(output_dir: str, container_name: Optional[str] = None) -> str:
    """
    Best-effort restart of the recorder so a saved config/camera change actually takes
    effect — AppConfig is a module-level singleton loaded once at import, so there's no
    in-process reload. Tries a Docker container restart first (docker-compose deployments);
    falls back to signalling the PID src.main wrote at startup (native runs) if no such
    container exists. Never raises — a failed restart shouldn't make the save itself look
    like it failed; the caller surfaces the returned message to the user instead.
    """
    container_name = container_name or os.environ.get("RECORDER_CONTAINER_NAME", "video-capture-bundler")

    docker_error = _restart_via_docker(container_name)
    if docker_error is None:
        return f"Restarted container '{container_name}'."

    pid_error = _restart_via_pidfile(output_dir)
    if pid_error is None:
        return "Restarted the recorder process."

    return (
        f"Saved, but couldn't restart the recorder automatically "
        f"(docker: {docker_error}; native: {pid_error}). Restart it yourself."
    )
