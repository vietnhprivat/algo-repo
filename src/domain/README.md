# domain

Core domain models for the energy data platform. No external dependencies — pure Python dataclasses, Polars schemas, and enums.

---

## Areas (`areas.py`)

**`Area` (frozen dataclass):**

| Field | Type | Example |
|-------|------|---------|
| `tag` | `str` | `"DK1"` |
| `name` | `str` | `"Denmark - West"` |
| `energy_identification_code` | `str` | `"10YDK-1--------W"` |
| `country` | `str` | `"DK"` |
| `currency` | `str` | `"DKK"` |
| `timezone` | `ZoneInfo` | `ZoneInfo("Europe/Copenhagen")` |

**Lookup functions:**

```python
from domain.areas import get_area_from_tag, get_area_from_energy_code

area = get_area_from_tag("DK1")              # raises ValueError if unknown
area = get_area_from_energy_code("10YDK-1--------W")
```

**32 bidding zones defined:**

| Region | Tags |
|--------|------|
| Nordic | `DK1`, `DK2`, `NO`, `SE`, `FI` |
| Continental EU | `DE`, `AT`, `CH`, `CZ`, `SK`, `HU`, `RO`, `BG`, `HR`, `SI` |
| Western EU | `NL`, `BE`, `FR`, `GB`, `IE` |
| Southern EU | `ES`, `PT`, `IT`, `GR` |
| Baltic | `LT`, `LV`, `EE` |
| Balkans / Other | `PL`, `UA`, `RS`, `BA`, `ME`, `MK`, `XK` |

---

## Curve Naming Convention

Curve names use **spaces** as separators throughout the codebase — never dots.

| Data type | Pattern | Example |
|-----------|---------|---------|
| Energy prices | `ENTSOE {area} EnergyPrice {contract} {currency}` | `ENTSOE DK1 EnergyPrice A01 DKK` |
| Total load | `ENTSOE {area} TotalLoad {process}` | `ENTSOE DK1 TotalLoad Dayahead` |
| Generation | `ENTSOE {area} Generation {process}` | `ENTSOE DE Generation Realised` |
| Wind/Solar | `ENTSOE {area} {PsrName} {process}` | `ENTSOE DK1 WindOnshore Dayahead` |

---

## Domain Models (`curves.py`)

Three schema-enforced data containers. All use `enforce_schema()` on construction.

| Class | Key fields | Stored in |
|-------|-----------|-----------|
| `Observations` | `source`, `curve_name`, `area`, `timezone`, `timestamp_utc`, `value` (Float32), `ingested_utc` | `algo.timeseries` |
| `Forecast` | `source`, `curve_name`, `area`, `area_timezone`, `model`, `issued_utc`, `issued_timezone`, `timestamp_utc`, `value` (Float32), `ingested_utc` | `algo.forecasts` |
| `EnergyPriceObservation` | `source`, `area`, `area_timezone`, `start_utc`, `end_utc`, `auction_type`, `business_type`, `contract_type`, `price` (Float64), `currency`, `ingestion_timestamp` | `algo.energy_prices` |

**Construction:**

```python
obs = Observations(curve_name="ENTSOE DK1 TotalLoad Dayahead", data_frame=df)
fcast = Forecast(curve_name="ENTSOE DK1 TotalLoad Dayahead", data_frame=df)
epo = EnergyPriceObservation(data_frame=df)   # no curve_name arg
```

**Empty placeholder:**

```python
obs = Observations.empty("ENTSOE DK1 TotalLoad Dayahead")
```

**Delta merge (get only changed rows):**

```python
delta = Observations.get_updated_observations(existing, new)
delta = Forecast.get_updated_forecast(existing, new)
```

Returns only rows where `value` changed or is new — used to avoid re-inserting unchanged data.

### `enforce_schema(df, schema) → pl.DataFrame`

Validates column presence, order, and dtypes. Raises `ValueError` with a detailed message on any mismatch. Does **not** coerce types — the caller must cast before construction.

```python
# ValueError: "Schema mismatch: column 'value' expected Float32, got Float64"
```

---

## Currency (`currency.py`)

**`Currency(str, Enum)`** — 19 European ISO 4217 codes.

```python
from domain.currency import Currency

Currency.DKK         # <Currency.DKK: 'DKK'>
str(Currency.DKK)    # "DKK"
```

| Group | Members |
|-------|---------|
| Eurozone | `EUR` |
| Non-eurozone EU | `BGN`, `CZK`, `DKK`, `HRK`, `HUF`, `PLN`, `RON`, `SEK` |
| Non-EU European | `GBP`, `CHF`, `NOK`, `ISK`, `UAH`, `RUB`, `TRY`, `BYN`, `GEL`, `AMD`, `AZN` |

Being a `str` subclass means `Currency` values can be passed anywhere a plain string is expected without explicit `.value` access.
