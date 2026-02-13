import pytest
from datetime import datetime, timezone

import polars as pl

from domain.curves import EnergyPriceObservation, enforce_schema


def _make_valid_df(n_rows: int = 2) -> pl.DataFrame:
    """Create a minimal valid DataFrame matching EnergyPriceObservation.SCHEMA."""
    now = datetime.now(timezone.utc)
    return pl.DataFrame(
        {
            "source": ["ENTSOE"] * n_rows,
            "area": ["DE"] * n_rows,
            "area_timezone": ["Europe/Berlin"] * n_rows,
            "start_utc": [now] * n_rows,
            "end_utc": [now] * n_rows,
            "auction_type": ["Implicit"] * n_rows,
            "business_type": ["Production"] * n_rows,
            "contract_type": ["Daily"] * n_rows,
            "price": [42.5] * n_rows,
            "currency": ["EUR"] * n_rows,
            "ingestion_timestamp": [now] * n_rows,
        },
        schema={
            "source": pl.Utf8,
            "area": pl.Utf8,
            "area_timezone": pl.Utf8,
            "start_utc": pl.Datetime(time_zone=str(timezone.utc)),
            "end_utc": pl.Datetime(time_zone=str(timezone.utc)),
            "auction_type": pl.Utf8,
            "business_type": pl.Utf8,
            "contract_type": pl.Utf8,
            "price": pl.Float64,
            "currency": pl.Utf8,
            "ingestion_timestamp": pl.Datetime(time_zone=str(timezone.utc)),
        },
    )


class TestEnforceSchema:
    def test_valid_dataframe_passes(self):
        df = _make_valid_df()
        result = enforce_schema(df, EnergyPriceObservation.SCHEMA)
        assert result.shape == df.shape

    def test_missing_column_raises(self):
        df = _make_valid_df().drop("price")
        with pytest.raises(ValueError, match="missing columns"):
            enforce_schema(df, EnergyPriceObservation.SCHEMA)

    def test_extra_column_raises(self):
        df = _make_valid_df().with_columns(pl.lit("extra").alias("bonus"))
        with pytest.raises(ValueError, match="unexpected columns"):
            enforce_schema(df, EnergyPriceObservation.SCHEMA)

    def test_wrong_dtype_raises(self):
        df = _make_valid_df().with_columns(pl.col("price").cast(pl.Int64))
        with pytest.raises(ValueError, match="column 'price'"):
            enforce_schema(df, EnergyPriceObservation.SCHEMA)

    def test_non_dataframe_raises_type_error(self):
        with pytest.raises(TypeError, match="must be a polars.DataFrame"):
            enforce_schema("not a df", EnergyPriceObservation.SCHEMA)  # type: ignore[arg-type]


class TestEnergyPriceObservation:
    def test_creates_successfully_with_valid_data(self):
        df = _make_valid_df()
        obs = EnergyPriceObservation(df)
        assert obs.data_frame.shape == df.shape

    def test_rejects_invalid_schema(self):
        df = _make_valid_df().drop("source")
        with pytest.raises(ValueError):
            EnergyPriceObservation(df)
