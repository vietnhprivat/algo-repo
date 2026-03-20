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
