# data-cli

CLI tool for backfilling historical data from external sources into ClickHouse.

## Requirements

- A `.env` file in the project root with the required credentials (see `.env.example`)
- ClickHouse running and accessible
- `ENTSOE_API_KEY` set for ENTSOE commands

## Usage

```bash
uv run python -m data_cli.main <source> <command> <subcommand> [options]
```

Run `--help` at any level to see available commands and options:

```bash
uv run python -m data_cli.main --help
uv run python -m data_cli.main entsoe --help
uv run python -m data_cli.main entsoe backfill --help
uv run python -m data_cli.main entsoe backfill price-document --help
uv run python -m data_cli.main entsoe backfill total-load --help
```

## Sources

### ENTSOE

#### `entsoe backfill price-document`

Backfills energy price data (document type A44) from the ENTSOE Transparency Platform into `algo.timeseries`.

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--area` | `-a` | Area tag (case-insensitive). See valid tags below. |
| `--start` | `-s` | Start datetime UTC (flexible format) |
| `--end` | `-e` | End datetime UTC (flexible format). Optional — defaults to now. |

**Datetime formats accepted:**

| Format | Example |
|--------|---------|
| ISO date | `2022-12-24` |
| ISO date with time | `2022-12-24-14:00` |
| Compact (YYYYMMDDHHmm) | `202212241400` |
| Human readable | `1 jan 2022`, `1 January 2022` |

**Valid area tags:**

`AT`, `BA`, `BE`, `BG`, `CH`, `CZ`, `DE`, `DK1`, `DK2`, `EE`, `ES`, `FI`, `FR`, `GB`, `GR`, `HR`, `HU`, `IE`, `IT`, `LT`, `LV`, `ME`, `MK`, `NL`, `NO`, `PL`, `PT`, `RO`, `RS`, `SE`, `SI`, `SK`, `UA`, `XK`

**Examples:**

```bash
# Backfill DK1 for all of 2024
uv run python -m data_cli.main entsoe backfill price-document -a dk1 -s 2024-01-01 -e 2025-01-01

# Backfill Germany using human-readable dates
uv run python -m data_cli.main entsoe backfill price-document -a de -s "1 jan 2022" -e "1 feb 2022"

# Backfill with specific hours using compact format
uv run python -m data_cli.main entsoe backfill price-document -a DK1 -s 202412240000 -e 202412250000

# Backfill with hour precision using date-hour format
uv run python -m data_cli.main entsoe backfill price-document -a dk1 -s 2022-06-01-00:00 -e 2022-07-01-00:00
```

#### `entsoe backfill total-load`

Backfills total load data (document type A65) from the ENTSOE Transparency Platform into `algo.forecasts`. Supports multiple process types: day-ahead forecasts, realised load, week/month/year-ahead forecasts.

Requests are automatically batched in 10-month chunks (API limit is 1 year per request).

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--area` | `-a` | Area tag (case-insensitive). See valid tags above. |
| `--start` | `-s` | Start datetime UTC (flexible format) |
| `--end` | `-e` | End datetime UTC (flexible format). Optional — defaults to now. |
| `--processtype` | `-p` | Process type code. Optional — defaults to `A01` (Dayahead). |

**Process types:**

| Code | Name | Description |
|------|------|-------------|
| `A01` | Dayahead | Day-ahead total load forecast (default) |
| `A16` | Realised | Actual realised total load |
| `A31` | WeekAhead | Week-ahead total load forecast |
| `A32` | MonthAhead | Month-ahead total load forecast |
| `A33` | YearAhead | Year-ahead total load forecast |

**Examples:**

```bash
# Day-ahead load forecast for DK1 (default process type A01)
uv run python -m data_cli.main entsoe backfill total-load -a dk1 -s 2024-01-01 -e 2024-06-01

# Realised (actual) load for Germany
uv run python -m data_cli.main entsoe backfill total-load -a de -s 2024-01-01 -e 2024-06-01 -p A16

# Week-ahead forecast for Denmark West
uv run python -m data_cli.main entsoe backfill total-load -a dk1 -s "1 jan 2024" -e "1 jul 2024" -p A31

# Month-ahead forecast for Norway
uv run python -m data_cli.main entsoe backfill total-load -a no -s 2024-01-01 -e 2025-01-01 -p A32

# Year-ahead forecast for France, full year
uv run python -m data_cli.main entsoe backfill total-load -a fr -s 2023-01-01 -e 2024-01-01 -p A33

# Long backfill (auto-batched in 10-month chunks)
uv run python -m data_cli.main entsoe backfill total-load -a de -s 2020-01-01 -e 2024-01-01 -p A01
```
