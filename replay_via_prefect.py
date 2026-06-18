"""Throwaway: replay the REAL daily_forecast_flow per day so runs register in
the Prefect UI. Run with PREFECT_API_URL=http://localhost:4200/api (the
host-reachable server; the .env value points at the docker-internal hostname).
Safe to delete.

Usage:
    PREFECT_API_URL=http://localhost:4200/api uv run python replay_via_prefect.py <c1,c2,...> <start> <end>
"""

from __future__ import annotations

import datetime as dt
import sys

from schedules.forecast import daily_forecast_flow


def daterange(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def main() -> None:
    configs = sys.argv[1].split(",")
    start = dt.date.fromisoformat(sys.argv[2])
    end = dt.date.fromisoformat(sys.argv[3])
    ok = skip = 0
    for cfg in configs:
        for d in daterange(start, end):
            ds = d.isoformat()
            try:
                daily_forecast_flow(config_name=cfg, target_date=ds)
                ok += 1
                print(f"OK   {cfg} {ds}", flush=True)
            except Exception as exc:  # noqa: BLE001
                skip += 1
                print(f"SKIP {cfg} {ds} :: {type(exc).__name__}: {exc}", flush=True)
    print(f"DONE configs={configs} ok={ok} skip={skip}", flush=True)


if __name__ == "__main__":
    main()
