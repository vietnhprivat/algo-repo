import pytest
from datetime import datetime, timezone

import polars as pl

from domain.curves import Observations, enforce_schema


def _make_valid_df(n_rows: int = 2) -> pl.DataFrame:
    now = datetime.now(timezone.utc)
    return pl.DataFrame(
        {
            "source": ["ENTSOE"] * n_rows,
            "curve_name": ["ENTSOE DK1 TotalLoad Dayahead"] * n_rows,
            "area": ["DK1"] * n_rows,
            "timezone": ["Europe/Copenhagen"] * n_rows,
            "timestamp_utc": [now] * n_rows,
            "value": [42.5] * n_rows,
            "ingested_utc": [now] * n_rows,
        },
        schema={
            "source": pl.Utf8,
            "curve_name": pl.Utf8,
            "area": pl.Utf8,
            "timezone": pl.Utf8,
            "timestamp_utc": pl.Datetime(time_zone=str(timezone.utc)),
            "value": pl.Float32,
            "ingested_utc": pl.Datetime(time_zone=str(timezone.utc)),
        },
    )


class TestEnforceSchema:
    def test_valid_dataframe_passes(self):
        df = _make_valid_df()
        result = enforce_schema(df, Observations.SCHEMA)
        assert result.shape == df.shape

    def test_missing_column_raises(self):
        df = _make_valid_df().drop("value")
        with pytest.raises(ValueError, match="missing columns"):
            enforce_schema(df, Observations.SCHEMA)

    def test_extra_column_raises(self):
        df = _make_valid_df().with_columns(pl.lit("extra").alias("bonus"))
        with pytest.raises(ValueError, match="unexpected columns"):
            enforce_schema(df, Observations.SCHEMA)

    def test_wrong_dtype_raises(self):
        df = _make_valid_df().with_columns(pl.col("value").cast(pl.Int64))
        with pytest.raises(ValueError, match="column 'value'"):
            enforce_schema(df, Observations.SCHEMA)

    def test_non_dataframe_raises_type_error(self):
        with pytest.raises(TypeError, match="must be a polars.DataFrame"):
            enforce_schema("not a df", Observations.SCHEMA)  # type: ignore[arg-type]


class TestObservations:
    def test_creates_successfully_with_valid_data(self):
        df = _make_valid_df()
        obs = Observations("ENTSOE DK1 TotalLoad Dayahead", df)
        assert obs.data_frame.shape == df.shape

    def test_rejects_invalid_schema(self):
        df = _make_valid_df().drop("source")
        with pytest.raises(ValueError):
            Observations("ENTSOE DK1 TotalLoad Dayahead", df)
