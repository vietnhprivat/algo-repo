"""Synthetic data fixtures for the PR smoke test.

Builds hourly DK1 prices + TotalLoad forecasts covering the range used by
`configs/smoke.py` (training window ~2 weeks before target_date 2025-06-01,
plus the target date and one day of "future actuals" for reconciliation).
"""
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl

from domain.curves import Forecast, Observations

AREA = "DK1"
PRICE_CURVE = f"ENTSOE {AREA} EnergyPrice Dayahead EUR"
LOAD_CURVE = f"ENTSOE {AREA} TotalLoad Dayahead"

DATA_START = datetime(2025, 5, 1, 0, 0, tzinfo=timezone.utc)
DATA_END = datetime(2025, 6, 3, 0, 0, tzinfo=timezone.utc)


def _hourly_index() -> list[datetime]:
    hours = int((DATA_END - DATA_START).total_seconds() // 3600)
    return [DATA_START + timedelta(hours=i) for i in range(hours)]


def _synthetic_prices(timestamps: list[datetime], seed: int = 7) -> list[float]:
    rng = np.random.default_rng(seed)
    hours = np.arange(len(timestamps))
    daily = 10 * np.sin(2 * np.pi * hours / 24)
    weekly = 5 * np.sin(2 * np.pi * hours / (24 * 7))
    noise = rng.normal(0, 2, size=len(timestamps))
    return (50 + daily + weekly + noise).astype(np.float32).tolist()


def _synthetic_load(timestamps: list[datetime], seed: int = 13) -> list[float]:
    rng = np.random.default_rng(seed)
    hours = np.arange(len(timestamps))
    daily = 300 * np.sin(2 * np.pi * hours / 24 - np.pi / 2)
    noise = rng.normal(0, 50, size=len(timestamps))
    return (1500 + daily + noise).astype(np.float32).tolist()


def build_price_observations() -> Observations:
    ts = _hourly_index()
    values = _synthetic_prices(ts)
    ingested = datetime.now(timezone.utc)
    df = pl.DataFrame(
        {
            "source": ["SMOKE"] * len(ts),
            "curve_name": [PRICE_CURVE] * len(ts),
            "area": [AREA] * len(ts),
            "timezone": ["Europe/Copenhagen"] * len(ts),
            "timestamp_utc": ts,
            "value": values,
            "ingested_utc": [ingested] * len(ts),
        },
        schema=Observations.SCHEMA,
    )
    return Observations(curve_name=PRICE_CURVE, data_frame=df)


def build_load_forecasts() -> Forecast:
    ts = _hourly_index()
    values = _synthetic_load(ts)
    issued = datetime.now(timezone.utc)
    df = pl.DataFrame(
        {
            "source": ["SMOKE"] * len(ts),
            "curve_name": [LOAD_CURVE] * len(ts),
            "area": [AREA] * len(ts),
            "area_timezone": ["Europe/Copenhagen"] * len(ts),
            "model": ["SMOKE"] * len(ts),
            "issued_utc": [issued] * len(ts),
            "issued_timezone": ["UTC"] * len(ts),
            "timestamp_utc": ts,
            "value": values,
            "ingested_utc": [issued] * len(ts),
        },
        schema=Forecast.SCHEMA,
    )
    return Forecast(curve_name=LOAD_CURVE, data_frame=df)
