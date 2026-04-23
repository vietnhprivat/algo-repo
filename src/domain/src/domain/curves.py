from datetime import timezone
import polars as pl



class Forecast:
    SCHEMA = {
        "source":                pl.Utf8,
        "curve_name":            pl.Utf8,
        "area":                  pl.Utf8,
        "area_timezone":         pl.Utf8,
        "model":                 pl.Utf8,
        "issued_utc":            pl.Datetime(time_zone = timezone.utc),
        "issued_timezone":       pl.Utf8,
        "timestamp_utc":         pl.Datetime(time_zone = timezone.utc),
        "value":                 pl.Float32,
        "ingested_utc":          pl.Datetime(time_zone = timezone.utc),
    }

    def __init__(
        self, 
        curve_name: str,
        data_frame: pl.DataFrame
    ):
        if not curve_name or not curve_name.strip():
            raise ValueError("curve_name must have a value")

        self.curve_name = curve_name
        self.data_frame = enforce_schema(data_frame, self.SCHEMA)

    @staticmethod
    def empty(curve_name: str) -> "Forecast":
        return Forecast(
            curve_name = curve_name,
            data_frame = pl.DataFrame(schema = Forecast.SCHEMA)
        )



class Observations:
    SCHEMA = {
        "source":          pl.Utf8,
        "curve_name":      pl.Utf8,
        "area":            pl.Utf8,
        "timezone":        pl.Utf8,
        "timestamp_utc":   pl.Datetime(time_zone = timezone.utc),
        "value":           pl.Float32,
        "ingested_utc":    pl.Datetime(time_zone = timezone.utc),
    }


    def __init__(
        self, 
        curve_name: str,
        data_frame: pl.DataFrame
    ):
        if not curve_name or not curve_name.strip():
            raise ValueError("curve_name must have a value")
        
        self.curve_name = curve_name
        self.data_frame = enforce_schema(data_frame, self.SCHEMA)


    @staticmethod
    def empty(curve_name: str) -> "Observations":
        return Observations(
            curve_name = curve_name,
            data_frame = pl.DataFrame(schema = Observations.SCHEMA)
        )
    


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
