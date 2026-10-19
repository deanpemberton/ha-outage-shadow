"""Deterministic, read-only islanded household energy simulation.

All power in kW, energy in kWh, time in hours. This is an engineering
scenario model, NOT a calibrated restoration probability or switching system.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Optional, Sequence


@dataclass(frozen=True)
class Battery:
    capacity_kwh: float
    soc_fraction: float
    cutoff_fraction: float = 0.05
    max_charge_kw: float = 5.0
    max_discharge_kw: float = 5.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95

    def validate(self) -> None:
        values = vars(self).values()
        if not all(isfinite(v) for v in values):
            raise ValueError("Battery parameters must be finite")
        if self.capacity_kwh <= 0 or min(self.max_charge_kw, self.max_discharge_kw) <= 0:
            raise ValueError("Capacity and power limits must be positive")
        if not (0 <= self.cutoff_fraction < 1 and self.cutoff_fraction <= self.soc_fraction <= 1):
            raise ValueError("Invalid SOC or cutoff")
        if not (0 < self.charge_efficiency <= 1 and 0 < self.discharge_efficiency <= 1):
            raise ValueError("Invalid battery efficiency")


@dataclass(frozen=True)
class Interval:
    hours: float
    solar_kw: float
    essential_kw: float
    backed_up_kw: float = 0.0
    stoppable_kw: float = 0.0
    # Non-essential circuits are deliberately NOT included in backed-up load.
    # Stoppable load is assumed successfully switched off on islanding.


@dataclass(frozen=True)
class Step:
    elapsed_hours: float
    soc_fraction: float
    served_kw: float
    solar_used_kw: float
    solar_curtailed_kw: float


@dataclass(frozen=True)
class Result:
    survived: Optional[bool]
    first_shortfall_hours: Optional[float]
    hours_simulated: float
    min_soc_fraction: Optional[float]
    final_soc_fraction: Optional[float]
    steps: tuple[Step, ...]
    reason: Optional[str] = None


def simulate(battery: Battery, intervals: Sequence[Interval],
             *, solar_availability: float = 1.0) -> Result:
    """Stop on FIRST unmet demand; later sunlight cannot revive a failed run.

    Unknown/incomplete forecast data returns survived=None, not a false success.
    The timestep is evaluated with a net-energy balance; for fine outage timing
    use <=30 minute intervals. The inverter/islanding configuration must be
    verified independently.
    """
    battery.validate()
    if not isfinite(solar_availability) or not 0 <= solar_availability <= 1:
        raise ValueError("solar_availability must be between zero and one")
    if not intervals:
        return Result(None, None, 0, None, None, (), "no forecast intervals")
    energy = battery.capacity_kwh * battery.soc_fraction
    minimum = energy
    floor = battery.capacity_kwh * battery.cutoff_fraction
    elapsed = 0.0
    steps: list[Step] = []
    for i, slot in enumerate(intervals):
        if not all(isfinite(v) for v in vars(slot).values()) or slot.hours <= 0 or min(
            slot.solar_kw, slot.essential_kw, slot.backed_up_kw, slot.stoppable_kw
        ) < 0:
            return Result(None, None, elapsed, minimum / battery.capacity_kwh,
                          energy / battery.capacity_kwh, tuple(steps),
                          f"invalid interval {i}")
        demand = slot.essential_kw + slot.backed_up_kw
        pv = slot.solar_kw * solar_availability
        direct = min(pv, demand)
        deficit = demand - direct
        excess = pv - direct
        if deficit > battery.max_discharge_kw + 1e-9:
            return Result(False, elapsed, elapsed, minimum / battery.capacity_kwh,
                          energy / battery.capacity_kwh, tuple(steps),
                          "discharge power limit")
        if deficit > 0:
            required = deficit * slot.hours / battery.discharge_efficiency
            available = max(0.0, energy - floor)
            if required > available + 1e-9:
                time_to_cutoff = available * battery.discharge_efficiency / deficit
                failure_at = elapsed + time_to_cutoff
                return Result(False, failure_at, failure_at, floor / battery.capacity_kwh,
                              floor / battery.capacity_kwh, tuple(steps),
                              "battery cutoff")
            energy -= required
        else:
            charge_kw = min(excess, battery.max_charge_kw)
            energy = min(battery.capacity_kwh,
                         energy + charge_kw * slot.hours * battery.charge_efficiency)
        minimum = min(minimum, energy)
        elapsed += slot.hours
        solar_used = direct + (min(excess, battery.max_charge_kw) if deficit == 0 else 0)
        steps.append(Step(elapsed, energy / battery.capacity_kwh, demand,
                          solar_used, max(0.0, pv - solar_used)))
    return Result(True, None, elapsed, minimum / battery.capacity_kwh,
                  energy / battery.capacity_kwh, tuple(steps))


def horizons(battery: Battery, intervals: Sequence[Interval],
             targets: Sequence[float] = (6, 12, 24, 48),
             **kwargs: float) -> dict[float, Result]:
    """Compute exact target horizons; incomplete horizon is UNKNOWN."""
    output = {}
    for target in targets:
        if target <= 0:
            raise ValueError("Horizon must be positive")
        chosen = []
        elapsed = 0.0
        for interval in intervals:
            if elapsed >= target:
                break
            hours = min(interval.hours, target - elapsed)
            chosen.append(Interval(hours, interval.solar_kw, interval.essential_kw,
                                   interval.backed_up_kw, interval.stoppable_kw))
            elapsed += hours
        if elapsed < target - 1e-8:
            output[target] = Result(None, None, elapsed, None, None, (),
                                    "forecast shorter than requested horizon")
        else:
            output[target] = simulate(battery, chosen, **kwargs)
    return output
