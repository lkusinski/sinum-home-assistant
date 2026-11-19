# Sinum Energy Center — API research and integration plan

Research snapshot: **2026-11-19**. Read-only probing of the Sinum cloud proxy
(`https://backend.prd.sinum24.com/proxy`). The values below are sanitized; no
installation-specific identifiers or credentials belong in this document.

## Available endpoints

All endpoints use the normal authenticated cloud client (Bearer token +
`X-Device-ID`) and return a `{"data": ...}` envelope.

| Endpoint | Shape | Notes |
|---|---|---|
| `GET /energy-center/flow-monitor` | `flow`, `summary`, `voltage`, `building_consumption_details` | Live power flows between PV, grid, battery and building; battery SOC/status. |
| `GET /energy-center/energy-consumption` | `available`, `today`, `total` | House, outlets and car-charger consumption. |
| `GET /energy-center/energy-production` | `available`, `today`, `total` | PV production, autoconsumption, storage and grid export. |
| `GET /energy-center/energy-storage` | `available`, `energy_charged_today`, `energy_discharged_today`, `power`, `state_of_charge`, `status` | Battery storage summary. |
| `GET /energy-center/prices` | `currency`, `prices`, `next_day_prices` | May be empty when no price source is configured. |
| `GET /energy-center/associations` | `battery`, `grid`, `pv` | References the virtual devices used by the energy center. |

## Observed behaviour

- `flow-monitor`, `energy-consumption` and `energy-storage` are available on a
  normal cloud hub; `energy-production` can return `available: false` when no
  PV source is associated.
- `prices` can be empty and the currency may differ from PLN.
- The energy center is an **aggregated, clean source**: it is usually simpler
  and more stable than reconstructing the same data from individual virtual
  devices.
- The integration does not currently expose any energy-center entities.

## Integration status (1.7.0)

Implemented in `sensor.py` as the **Sinum Energy Center** device:

- `energy_pv_power`, `energy_grid_power`, `energy_building_power`,
  `energy_battery_power`
- `energy_battery_soc`
- `energy_consumption_today`, `energy_consumption_total`
- `energy_production_today`, `energy_production_total`
- `energy_grid_export_today`
- `energy_storage_charged_today`, `energy_storage_discharged_today`
- `energy_storage_power`, `energy_storage_status`
- `energy_price_currency` (diagnostic)

The coordinator refreshes the energy-center payload at most once per minute
and keeps the previous snapshot between refreshes.

## Integration plan

1. Add `async_get_energy_center()` methods to the API client for the six
   endpoints above.
2. Fetch them in the coordinator with a low-frequency cache (for example every
   30–60 s); tolerate `404`/`501` on older hubs.
3. Add a new `Sinum Energy Center` device and sensors:
   - PV power/production today/total, grid import/export, building
     consumption, battery power, SOC, charged/discharged today, status.
   - Optional price sensor with currency attribute.
4. Use HA device classes/state classes (`power`, `energy`, `battery`,
   `monetary`) and `TOTAL_INCREASING` for cumulative counters.
5. Handle `available: false` as `unknown`/`unavailable`, not as zero, so the
   HA Energy dashboard does not record fake values.
6. Add diagnostics (endpoint availability, last update) and tests with mocked
   payloads.
7. Document dashboard/Energy-dashboard examples.

## Safety

- Energy-center endpoints are read-only; no service calls are needed.
- Do not write to the energy center (`/clear-data`, price settings) from the
  integration.
- Keep units and currency explicit; do not assume PLN.
