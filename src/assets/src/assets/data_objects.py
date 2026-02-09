from datetime import timezone
import polars as pl


class EnergyPriceObservation:
    SCHEMA = {
        "source": pl.Utf8,
        "area": pl.Utf8,
        "area_timezone": pl.Utf8,
        "start_utc": pl.Datetime(time_zone=timezone.utc),
        "end_utc": pl.Datetime(time_zone=timezone.utc),
        "auction_type": pl.Utf8,
        "business_type": pl.Utf8,
        "contract_type": pl.Utf8,
        "price": pl.Float64,
        "currency": pl.Utf8,
        "ingestion_timestamp": pl.Datetime(time_zone=timezone.utc),
    }

    def __init__(self, data_frame: pl.DataFrame):
        self.data_frame = enforce_schema(data_frame, self.SCHEMA)


def enforce_schema(df: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if not isinstance(df, pl.DataFrame):
        raise TypeError("df must be a polars.DataFrame")

    errors: list[str] = []
    expected_columns = list(schema.keys())
    actual_columns = list(df.columns)

    if actual_columns != expected_columns:
        missing = [c for c in expected_columns if c not in df.columns]
        extra = [c for c in df.columns if c not in schema]
        if missing:
            errors.append(f"missing columns: {missing}")
        if extra:
            errors.append(f"unexpected columns: {extra}")
        if not missing and not extra:
            errors.append(
                f"column order mismatch: expected {expected_columns}, got {actual_columns}"
            )

    for col, expected_dtype in schema.items():
        if col not in df.columns:
            continue
        actual_dtype = df.schema.get(col)
        if actual_dtype != expected_dtype:
            errors.append(
                f"column '{col}' has dtype {actual_dtype}, expected {expected_dtype}"
            )

    if errors:
        message = "Schema mismatch: " + "; ".join(errors)
        raise ValueError(message)

    return df
