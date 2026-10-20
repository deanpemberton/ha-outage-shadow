"""Audited descriptive restoration evidence, NOT household restoration probabilities.

2025 Wellington Electricity Schedule 10a; unplanned feeder rows. Melling
selection matches MEL-prefixed circuits only. Small samples and incident
dependence prohibit calibrated outage restoration forecasts.
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Evidence:
    scope: str
    observations: int
    thresholds: tuple[tuple[int, int], ...]
    longest_minutes: float | None
    feeder_ids: tuple[str, ...]
    status: str = "descriptive_only"

    def count_within(self, hours: int) -> int | None:
        return dict(self.thresholds).get(hours)

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "observations": self.observations,
            "thresholds": {f"{h}h": {"count": n, "total": self.observations}
                           for h, n in self.thresholds},
            "longest_minutes": self.longest_minutes,
            "feeder_ids": list(self.feeder_ids),
            "calibrated": False,
            "status": self.status,
            "source": "Wellington Electricity 2025 Schedule 10a audited unplanned feeder rows",
            "limitations": "Feeder rows are not independent incidents or random household exposures; no storm-tail calibration.",
        }

MELLING_2025 = Evidence("Melling (assumed)", 10,
                        ((3, 5), (6, 9), (12, 10), (24, 10), (48, 10)),
                        400.0, ("MEL3", "MEL4", "MEL6", "MEL8"))
NETWORK_2025 = Evidence("Wellington Electricity network", 208,
                        ((3, 127), (6, 174), (12, 197), (24, 202), (48, 205)),
                        12602.0, ())

def compare(survival: dict, evidence: Evidence = MELLING_2025) -> dict:
    """Compare battery status against observed windows without probability claims."""
    windows = {}
    for hours in (6, 12, 24, 48):
        state = survival.get(f"{hours}h_p10", {}).get("status", "unknown")
        windows[f"{hours}h"] = {
            "battery_status": state,
            "observed_restored": evidence.count_within(hours),
            "observed_total": evidence.observations,
        }
    return {"evidence": evidence.as_dict(), "windows": windows,
            "restoration_probability": None,
            "interpretation": "Historical comparison only; not a calibrated prediction."}
