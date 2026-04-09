# src/services/api_client.py
from __future__ import annotations

import requests
from enum import Enum
from typing import Any, Dict, Optional, Tuple

class APIEndpoint(str, Enum):
    SIGNIN = "/auth/signin"
    CREATE_PIPELINE_SESSION = "/pipeline-session/new"
    CREATE_PIPELINE_SESSION_OUTPUT = "/pipeline-session-output/new"
    CREATE_PIPELINE_SESSION_OUTPUT_UNIT = "/pipeline-session-output-unit/new"

class APIResponseStatus(str, Enum):
    OK = "ok"
    ERR = "err"

class APIClient:
    def __init__(self, host: str, email: str, password: str, timeout_sec: int = 15) -> None:
        self.host = host.rstrip("/")
        self.email = email
        self.password = password
        self.timeout_sec = timeout_sec
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}

        # Lazy auth; call ensure_auth() before requests
        self._authed = False

    def ensure_auth(self) -> bool:
        if self._authed:
            return True
        if not (self.host and self.email and self.password):
            return False

        try:
            url = self.host + APIEndpoint.SIGNIN.value
            resp = requests.post(
                url,
                json={"email": self.email, "password": self.password},
                timeout=self.timeout_sec,
            )
            if not resp.ok:
                return False
            data = resp.json() if resp.content else {}
            token = data.get("access_token") or data.get("token") or data.get("accessToken")
            if not token:
                return False
            self._headers["Authorization"] = f"Bearer {token}"
            self._authed = True
            return True
        except Exception:
            return False

    def post(self, endpoint: APIEndpoint, data: Dict[str, Any]) -> Tuple[APIResponseStatus, Optional[Dict[str, Any]]]:
        if not self.ensure_auth():
            return APIResponseStatus.ERR, None

        try:
            url = self.host + endpoint.value
            resp = requests.post(url, json=data, headers=self._headers, timeout=self.timeout_sec)
            if not resp.ok:
                return APIResponseStatus.ERR, None
            payload = resp.json() if resp.content else {}
            return APIResponseStatus.OK, payload
        except Exception:
            return APIResponseStatus.ERR, None
