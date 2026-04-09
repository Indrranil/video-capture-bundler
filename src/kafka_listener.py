from __future__ import annotations

import json
import threading
from typing import Dict, Optional

from kafka import KafkaConsumer

from src.state_store import StateStore


def _parse_verdict(payload_str: str) -> Optional[int]:
    """
    Kafka messages are assumed to be JSON string.
    We only need verdict.
    """
    try:
        obj = json.loads(payload_str)
    except Exception:
        return None

    # Most likely: obj["verdict"] or obj["payload"]["verdict"]
    if isinstance(obj, dict):
        if "verdict" in obj:
            return int(obj["verdict"])
        payload = obj.get("payload")
        if isinstance(payload, dict) and "verdict" in payload:
            return int(payload["verdict"])

    return None


class KafkaVerdictListener:
    """
    One consumer per topic, mapped to camera via CAMERA_TOPICS (cam:topic).
    """

    def __init__(
        self,
        kafka_host: str,
        kafka_port: int,
        group_id: str,
        camera_to_topic: Dict[str, str],
        state: StateStore,
        verdict_anomaly: int,
        verdict_normal: int,
    ) -> None:
        self.bootstrap = f"{kafka_host}:{kafka_port}"
        self.group_id = group_id
        self.camera_to_topic = camera_to_topic
        self.topic_to_camera = {t: c for c, t in camera_to_topic.items()}
        self.state = state
        self.verdict_anomaly = verdict_anomaly
        self.verdict_normal = verdict_normal

        self._threads: list[threading.Thread] = []
        self._stop = False

    def start(self) -> None:
        for camera, topic in self.camera_to_topic.items():
            t = threading.Thread(target=self._consume_topic, args=(topic,), daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop = True

    def _consume_topic(self, topic: str) -> None:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap,
            group_id=self.group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda x: x.decode("utf-8"),
        )

        camera = self.topic_to_camera.get(topic, topic)

        for msg in consumer:
            if self._stop:
                break

            verdict = _parse_verdict(msg.value)
            if verdict is None:
                continue

            # team: 1 anomaly, 0 normal
            if verdict not in (self.verdict_anomaly, self.verdict_normal):
                continue

            # team: "Fetch current time whenever event is received" => done in state_store
            updated_chunk = self.state.mark_verdict_for_camera_current_chunk(camera, verdict)
            # (optional) you can log updated_chunk if you want
