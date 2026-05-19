import pandas as pd

from data_cli.entsoe.services import assert_curve_quality


class TestAssertCurveQuality:
    def test_zero_rows_flagged(self):
        issues = assert_curve_quality([], curve_name="ENTSOE DK1 EnergyPrice Dayahead")
        assert any(i.kind == "empty" for i in issues)

    def test_non_monotonic_timestamps_flagged(self):
        rows = [
            {"timestamp_utc": pd.Timestamp("2025-01-02"), "value": 50.0},
            {"timestamp_utc": pd.Timestamp("2025-01-01"), "value": 50.0},
        ]
        issues = assert_curve_quality(rows, curve_name="ENTSOE DK1 EnergyPrice Dayahead")
        assert any(i.kind == "non_monotonic" for i in issues)

    def test_implausible_price_flagged(self):
        rows = [
            {"timestamp_utc": pd.Timestamp("2025-01-01"), "value": -10000.0},
            {"timestamp_utc": pd.Timestamp("2025-01-02"), "value": 50.0},
        ]
        issues = assert_curve_quality(rows, curve_name="ENTSOE DK1 EnergyPrice Dayahead")
        assert any(i.kind == "out_of_range" for i in issues)

    def test_implausible_load_flagged(self):
        rows = [
            {"timestamp_utc": pd.Timestamp("2025-01-01"), "value": -5.0},
            {"timestamp_utc": pd.Timestamp("2025-01-02"), "value": 50000.0},
        ]
        issues = assert_curve_quality(rows, curve_name="ENTSOE DK1 TotalLoad Dayahead")
        assert any(i.kind == "out_of_range" for i in issues)

    def test_clean_data_no_issues(self):
        rows = [
            {"timestamp_utc": pd.Timestamp("2025-01-01"), "value": 50.0},
            {"timestamp_utc": pd.Timestamp("2025-01-02"), "value": 52.0},
        ]
        issues = assert_curve_quality(rows, curve_name="ENTSOE DK1 EnergyPrice Dayahead")
        assert issues == []
