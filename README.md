# Outage Shadow for Home Assistant

A read-only Home Assistant custom integration for **experimental** battery/solar outage survival scenarios. It does not control switches, loads, or Powerwall settings, and it does not calculate grid restoration probabilities.

## Installation

1. In HACS, add `deanpemberton/ha-outage-shadow` as a **custom repository**, category **Integration**.
2. Download the integration in HACS and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration**, search for **Outage Shadow**, and finish setup.
4. Review the 12 scenario sensors (6, 12, 24, 48 hours × P10, P50, P90). Each exposes minimum SOC, first shortfall, forecast timestamp, and validation status as attributes.

## Data sources and assumptions

The integration reads these existing Home Assistant entities, if present: `sensor.powerwall_charge`, `input_number.outage_v1_battery_capacity`, `input_number.outage_v1_battery_cutoff`, `sensor.outage_v1_historical_expected_load`, and the three `sensor.solcast_pv_forecast_forecast_*` entities (today, tomorrow and day 3). Other installations will need to adapt entity IDs. The load is an **unvalidated proxy**, and the islanded solar availability is provisionally 85%. Neither represents a verified backup-power capability. Insufficient or invalid forecast coverage produces unknown results.

The integration archives a bounded set of issued forecasts and modeled inputs in HA local storage, without external telemetry uploads. Its 30-minute update frequency is not a substitute for validating actual islanded loads or solar inverter operation.

## Safety and privacy

No live household telemetry, credentials, historical records, or configuration files are included in this repository. The original model research and evidence remain in a separate private repository. Predictions must not be used for safety-critical electrical control.

## Development

Code syntax and metadata are checked by GitHub Actions. A successful syntax check is **not** a substitute for integration-level testing in Home Assistant.
