"""Throwaway catch-up replay: re-run the live forecast path over a past window.

Mirrors schedules.forecast.daily_forecast_flow exactly (load_config ->
LiveRunner.run_live_with_metadata -> track_prediction) but without the Prefect
flow wrapper, so it runs against the local DB/W&B with no Prefect server.

Usage:
    uv run python replay_catchup.py <config1,config2,...> <start_iso> <end_iso>
Dates whose data is still incomplete raise and are skipped.
Not part of the production schedule -- safe to delete.
"""

from __future__ import annotations

import datetime as dt
import sys

from forecast_cli.config_loader import load_config
from forecast_cli.tracking import track_prediction
from price_forecasting import LiveRunner


def replay_one(config_name: str, target_date: str) -> str:
    config = load_config(config_name)
    runner = LiveRunner(config)
    result = runner.run_live_with_metadata(target_date)
    return track_prediction(
        config,
        target_date,
        result.prediction,
        training_duration_seconds=result.training_duration_seconds,
        data_start_utc=result.data_start_utc,
        data_end_utc=result.data_end_utc,
        trained_models=result.trained_models,
        config_name=config_name,
    )


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
                run_id = replay_one(cfg, ds)
                ok += 1
                print(f"OK   {cfg} {ds} -> {run_id}", flush=True)
            except Exception as exc:  # noqa: BLE001 - log and keep going
                skip += 1
                print(f"SKIP {cfg} {ds} :: {type(exc).__name__}: {exc}", flush=True)
    print(f"DONE configs={configs} ok={ok} skip={skip}", flush=True)


if __name__ == "__main__":
    main()
