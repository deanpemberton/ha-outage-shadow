"""Read-only scenario outcomes. No commands or actuator entities."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = [
        ShadowSensor(coordinator, hours, scenario)
        for hours in (6, 12, 24, 48)
        for scenario in ("p10", "p50", "p90")
    ]
    entities.append(RestorationEvidenceSensor(coordinator))
    async_add_entities(entities)


class RestorationEvidenceSensor(CoordinatorEntity, SensorEntity):
    """Descriptive local restoration evidence; not a probability."""
    _attr_unique_id = f"{DOMAIN}_melling_restoration_evidence"
    _attr_name = "Outage Melling restoration evidence"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, coordinator):
        super().__init__(coordinator)

    @property
    def native_value(self):
        return self.coordinator.data.get("restoration", {}).get("evidence", {}).get("status", "unknown")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("restoration", {})


class ShadowSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:battery-clock-outline"

    def __init__(self, coordinator, hours, scenario):
        super().__init__(coordinator)
        self._key = f"{hours}h_{scenario}"
        self._attr_unique_id = f"{DOMAIN}_{self._key}"
        self._attr_name = f"Outage Python shadow {hours}h {scenario.upper()}"

    @property
    def native_value(self):
        return self.coordinator.data.get("results", {}).get(self._key, {}).get("status", "unknown")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        result = data.get("results", {}).get(self._key, {})
        return {"minimum_soc_percent": result.get("minimum_soc"),
                "first_shortfall_hours": result.get("first_shortfall_hours"),
                "reason": result.get("reason"),
                "forecast_at": data.get("updated"),
                "assumed_load_kw": data.get("demand_kw"),
                "model_version": data.get("model"),
                "validation": data.get("validation")}
