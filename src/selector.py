from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
from zoneinfo import ZoneInfo


def _parse_iso(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str)


def day_window_ist(now_ist: datetime, day_start_hour: int) -> Tuple[datetime, datetime]:
    """
    Returns [start, end) for the current IST day window.
    Example: day_start_hour=6 => 6am today to 6am tomorrow.
    If now is before 6am, window started yesterday 6am.
    """
    start = now_ist.replace(hour=day_start_hour, minute=0, second=0, microsecond=0)
    if now_ist.hour < day_start_hour:
        start = start - timedelta(days=1)
    end = start + timedelta(days=1)
    return start, end


def day_key_ddmmyy(start_ist: datetime) -> str:
    return start_ist.strftime("%d%m%y")


def select_for_upload(
    chunks: Dict[str, Dict[str, Any]],
    tz_name: str,
    day_start_hour: int,
    normal_samples_per_day: int,
    normal_bin_hours: int,
    random_seed: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    """
    Returns (anomaly_records, selected_normal_records, day_key_ddmmyy)

    Rules:
      - anomaly: keep all verdict=1
      - normal pool: verdict=0 OR verdict missing/None
      - select 12 normals with binning across 2hr buckets in IST
    """
    tz = ZoneInfo(tz_name)
    now_ist = datetime.now(tz)
    start, end = day_window_ist(now_ist, day_start_hour)
    key = day_key_ddmmyy(start)

    in_window: List[Dict[str, Any]] = []
    for rec in chunks.values():
        started = rec.get("started_at_ist")
        if not started:
            continue
        dt = _parse_iso(started)
        if start <= dt < end:
            in_window.append(rec)

    anomalies = [r for r in in_window if r.get("verdict") == 1 and r.get("zip_path")]
    normals = [r for r in in_window if (r.get("verdict") in (0, None)) and r.get("zip_path")]

    # Bin normals by time (2hr bins)
    bins: Dict[int, List[Dict[str, Any]]] = {}
    for r in normals:
        dt = _parse_iso(r["started_at_ist"])
        offset_hours = int((dt - start).total_seconds() // 3600)
        bin_idx = offset_hours // max(1, normal_bin_hours)
        bins.setdefault(bin_idx, []).append(r)

    rnd = random.Random(random_seed)

    # Shuffle inside each bin
    for b in bins.values():
        rnd.shuffle(b)

    selected: List[Dict[str, Any]] = []

    # Round-robin pick to maximize diversity
    bin_ids = sorted(bins.keys())
    while len(selected) < normal_samples_per_day:
        progressed = False
        for bid in bin_ids:
            if len(selected) >= normal_samples_per_day:
                break
            if bins.get(bid):
                selected.append(bins[bid].pop())
                progressed = True
        if not progressed:
            break

    return anomalies, selected, key
