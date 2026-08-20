from __future__ import annotations

from typing import List

from fastapi import APIRouter

from src.config import app_config
from src.state_store import StateStore
from src.webui.schemas import ChunkSummary

router = APIRouter(prefix="/api", tags=["capture"])


@router.get("/captures", response_model=List[ChunkSummary])
def list_captures() -> List[ChunkSummary]:
    state = StateStore(output_dir=app_config.OUTPUT_DIR, tz_name=app_config.TIMEZONE)
    chunks = state.list_chunks()
    rows = sorted(chunks.values(), key=lambda r: r.get("started_at_ist") or "", reverse=True)
    return [ChunkSummary(**row) for row in rows[:20]]
