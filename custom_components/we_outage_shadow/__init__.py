"""Read-only household outage shadow model."""
from datetime import timedelta
from homeassistant.helpers.storage import Store
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .energy import Battery, horizons
from .forecast import from_solcast

DOMAIN = "we_outage_shadow"
PLATFORMS = ["sensor"]
_LOGGER = logging.getLogger(__name__)
FORECASTS = (
    "sensor.solcast_pv_forecast_forecast_today",
    "sensor.solcast_pv_forecast_forecast_tomorrow",
    "sensor.solcast_pv_forecast_forecast_day_3",
)


def _number(hass, entity_id):
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unknown", "unavailable"):
        raise ValueError(f"Missing input: {entity_id}")
    return float(state.state)


class ShadowCoordinator(DataUpdateCoordinator):
    def __init__(self, hass):
        super().__init__(hass, _LOGGER, name="Wellington Outage Shadow",
                         update_interval=timedelta(minutes=30))

    async def _async_update_data(self):
        try:
            soc = _number(self.hass, "sensor.powerwall_charge") / 100
            capacity = _number(self.hass, "input_number.outage_v1_battery_capacity")
            cutoff = _number(self.hass, "input_number.outage_v1_battery_cutoff") / 100
            # V1 proxy is provisional and NOT an islanded measurement.
            demand = _number(self.hass, "sensor.outage_v1_historical_expected_load")
            if demand < 0 or demand > 20:
                raise ValueError("Invalid load")
            battery = Battery(capacity, soc, cutoff)
            now = dt_util.utcnow()
            rows = []
            input_times = {}
            for entity_id in FORECASTS:
                state = self.hass.states.get(entity_id)
                if state is None:
                    raise ValueError(f"Missing forecast: {entity_id}")
                if (now - state.last_updated).total_seconds() > 36 * 3600:
                    raise ValueError(f"Stale forecast: {entity_id}")
                input_times[entity_id] = state.last_updated.isoformat()
                detailed = state.attributes.get("detailedForecast")
                if not isinstance(detailed, list):
                    raise ValueError(f"Missing detailedForecast: {entity_id}")
                rows.extend(detailed)
            rows = sorted({r["period_start"]: r for r in rows}.values(),
                          key=lambda r: r["period_start"])
            output = {}
            for scenario in ("p10", "p50", "p90"):
                slots = from_solcast(rows, outage_at=now, demand_kw=demand,
                                     scenario=scenario, islanded_solar_fraction=0.85)
                for hours, result in horizons(battery, slots).items():
                    output[f"{hours}h_{scenario}"] = {
                        "status": "unknown" if result.survived is None else
                                  "survives" if result.survived else "cutoff",
                        "minimum_soc": round(result.min_soc_fraction * 100, 2)
                                       if result.min_soc_fraction is not None else None,
                        "first_shortfall_hours": result.first_shortfall_hours,
                        "reason": result.reason,
                    }
            snapshot = {"issued_at": now.isoformat(), "soc_fraction": soc,
                        "capacity_kwh": capacity, "cutoff_fraction": cutoff,
                        "assumed_demand_kw": demand, "solar_fraction": 0.85,
                        "forecast_updated": input_times, "results": output,
                        "model": "0.1.0"}
            if hasattr(self, "snapshot_store"):
                await self.snapshot_store.record(snapshot)
            return {"results": output, "updated": now.isoformat(),
                    "demand_kw": demand, "model": "0.1.0",
                    "validation": "unvalidated islanded load and PV"}
        except (ValueError, TypeError, KeyError, OverflowError) as err:
            _LOGGER.warning("Outage shadow inputs unavailable: %s", err)
            return {"results": {}, "updated": dt_util.utcnow().isoformat(),
                    "validation": f"unknown: {err}", "model": "0.1.0"}


class SnapshotArchive:
    """Bounded local-only forecast issue-time archive (no credentials)."""
    def __init__(self, hass, entry_id):
        self.store = Store(hass, 1, f"we_outage_shadow.{entry_id}.snapshots")

    async def record(self, snapshot):
        history = await self.store.async_load() or []
        history.append(snapshot)
        await self.store.async_save(history[-672:])


async def async_setup_entry(hass, entry):
    coordinator = ShadowCoordinator(hass)
    coordinator.snapshot_store = SnapshotArchive(hass, entry.entry_id)
    await coordinator.async_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
