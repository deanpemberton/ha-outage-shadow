"""Pure adapter from Solcast detailedForecast entries to simulation intervals.

Forecast rows use pv_estimate / pv_estimate10 / pv_estimate90 in kW.
No HA credentials or network access. Caller supplies a timezone-aware
outage timestamp, measured remaining backup demand and verified islanded PV
availability factor. Never assume all grid-tied solar works during islanding.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import isfinite
from typing import Mapping, Sequence

from .energy import Interval


SOLAR_KEYS = {
    "p10": "pv_estimate10",
    "p50": "pv_estimate",
    "p90": "pv_estimate90",
}


def from_solcast(
    rows: Sequence[Mapping[str, object]],
    *,
    outage_at: datetime,
    demand_kw: float,
    scenario: str = "p50",
    islanded_solar_fraction: float = 1.0,
    slot_minutes: int = 30,
) -> list[Interval]:
    if outage_at.tzinfo is None:
        raise ValueError("outage_at must be timezone-aware")
    if scenario not in SOLAR_KEYS:
        raise ValueError("Unknown solar scenario")
    if not isfinite(demand_kw) or demand_kw < 0:
        raise ValueError("Invalid demand")
    if not isfinite(islanded_solar_fraction) or not 0 <= islanded_solar_fraction <= 1:
        raise ValueError("Invalid islanded solar fraction")
    if slot_minutes <= 0:
        raise ValueError("Invalid slot duration")
    parsed = []
    for row in rows:
        start = datetime.fromisoformat(str(row["period_start"]))
        if start.tzinfo is None:
            raise ValueError("Forecast timestamps must be timezone-aware")
        value = float(row[SOLAR_KEYS[scenario]])
        if not isfinite(value) or value < 0:
            raise ValueError("Invalid solar forecast")
        parsed.append((start, value))
    parsed.sort(key=lambda pair: pair[0])
    duration = timedelta(minutes=slot_minutes)
    cursor = outage_at
    output = []
    for start, solar in parsed:
        end = start + duration
        if end <= cursor:
            continue
        if start > cursor + timedelta(seconds=1):
            raise ValueError("Forecast gap; cannot silently bridge")
        if start < cursor:
            start = cursor
        hours = (end - start).total_seconds() / 3600
        if hours <= 0:
            continue
        output.append(Interval(hours, solar * islanded_solar_fraction, demand_kw))
        cursor = end
    return output
