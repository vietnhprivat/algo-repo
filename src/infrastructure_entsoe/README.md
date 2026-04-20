# infrastructure-entsoe

HTTP client for the ENTSOE Transparency Platform API. Handles rate limiting, request chunking, ZIP and raw XML responses, and maps XML documents to domain model objects.

---

## Client

`EntsoeClient` (extends `EntsoeClientBase`) exposes four fetch methods. All return domain model lists ready for batch insert.

**Rate limit:** 400 calls / 60 seconds via `@limits` decorator (shared across all methods).

| Method | Doc type | Chunk size | Paginates | Returns |
|--------|----------|------------|-----------|---------|
| `fetch_energy_prices(area, start, end)` | A44 | 12 months | Yes (offset +100, max 4900 results) | `list[Observations]` |
| `fetch_total_load_forecasts(area, start, end, process_type, process_type_name)` | A65 | 10 months | No | `list[Forecast]` |
| `fetch_generation_forecasts(area, start, end, process_type, process_type_name)` | A71 | 10 months | No | `list[Forecast]` |
| `fetch_wind_solar_forecasts(area, start, end, process_type, process_type_name, psr_type)` | A69 | 10 months | No | `list[Forecast]` |

Use as a context manager:

```python
from infrastructure_entsoe.client_factory import create_entsoe_client

with create_entsoe_client() as client:
    observations = client.fetch_energy_prices(area, start, end)
```

`create_entsoe_client()` reads `ENTSOE_API_KEY` from the environment (via `.env`). Raises `ValueError` if not set.

---

## ZIP vs Raw XML

ENTSOE returns either a raw XML document or a ZIP archive containing multiple XML files (e.g. when pagination offsets are large). The client detects this automatically:

- ZIP: identified by `Content-Type: application/zip` header **or** magic bytes `b"PK"` at start of body
- All `.xml` files are extracted from the ZIP and processed individually

---

## Curve Naming

Output curve names follow a strict space-separated convention (never dots):

| Data type | Pattern | Example |
|-----------|---------|---------|
| Energy prices (A44) | `ENTSOE {area} EnergyPrice {contract_type} {currency}` | `ENTSOE DK1 EnergyPrice A01 DKK` |
| Total load / generation (A65, A71) | `ENTSOE {area} {DataType} {process_type_name}` | `ENTSOE DK1 TotalLoad Dayahead` |
| Wind / solar (A69) | `ENTSOE {area} {PsrName} {process_type_name}` | `ENTSOE DK1 WindOnshore Dayahead` |

---

## Process Types

| Code | Name | Supported by |
|------|------|-------------|
| `A01` | Dayahead (default) | A44, A65, A69, A71 |
| `A16` | Realised | A65, A71 |
| `A18` | IntradayTotal | A69 |
| `A31` | WeekAhead | A65, A71 |
| `A32` | MonthAhead | A65, A71 |
| `A33` | YearAhead | A65, A71 |
| `A40` | Intraday | A69 |

---

## PSR Types (wind/solar filter)

| Code | Name | `psr_type` arg |
|------|------|---------------|
| `B16` | Solar | `"B16"` |
| `B18` | Wind Offshore | `"B18"` |
| `B19` | Wind Onshore | `"B19"` |

Pass `psr_type=None` (default) to fetch all supported production types in one call.

---

## Error Handling

- **Non-200 response:** logs a WARNING with status code and continues to the next chunk. No exception raised — partial results are returned.
- **"No matching data found" response:** parsed as empty result, silently skipped.
- **Missing XML field:** `get_required_text()` raises `ValueError` with field name.

---

## `mappers.py`

Parses XML bytes → Polars DataFrames → domain objects. Key behaviours:

- **Resolution mapping:** `PT15M → 15min`, `PT30M → 30min`, `PT60M → 60min` (timedelta)
- **Position mapping:** `_map_A03_curve()` converts 1-indexed period positions to UTC timestamps using `start_utc + (position - 1) × resolution`
- **Forward-fill:** missing positions within a period are forward-filled in Polars before constructing domain objects
- **Timezone:** all timestamps normalised to UTC; original timezone preserved as a string field

---

## `entsoe_types.py`

Eight enums covering all ENTSOE document type codes. Use `ProcessType.from_str(name)` for case-insensitive lookup. Relevant types:

| Enum | Key members |
|------|------------|
| `DocumentType` | `PriceDocument (A44)`, `SystemTotalLoad (A65)`, `WindAndSolarForecast (A69)`, `GenerationForecast (A71)` |
| `ProcessType` | `Dayahead (A01)`, `Realised (A16)`, `IntradayTotal (A18)`, `WeekAhead (A31)`, `MonthAhead (A32)`, `YearAhead (A33)`, `Intraday (A40)` |
| `PsrType` | `SOLAR (B16)`, `WIND_OFFSHORE (B18)`, `WIND_ONSHORE (B19)` — plus 25 other generation types |
| `BusinessType` | 50+ types covering production, reserves, imbalances, unavailability |

---

## Module Layout

```
infrastructure_entsoe/
├── client.py          # EntsoeClient + EntsoeClientBase (fetch methods, rate limit)
├── client_factory.py  # create_entsoe_client() — reads ENTSOE_API_KEY
├── entsoe_types.py    # 8 enums for ENTSOE type codes
├── mappers.py         # XML → domain object parsers (A44, A65, A69, A71)
└── main.py            # Script entry: DK1 energy price example
```
