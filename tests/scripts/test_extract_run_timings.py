"""Tests for the pure helpers of extract_run_timings."""

from scripts.report.extract_run_timings import (
    EXPERIMENTS,
    fmt_hms,
    format_backtest_table,
    format_tuning_table,
    parse_timings_log,
)


class TestParseTimingsLog:
    def test_parses_well_formed_lines(self) -> None:
        text = "tune:dk1_dnn\t2026-06-04T13:00:00\t2026-06-04T13:22:31\t1351\n"
        rows = parse_timings_log(text)
        assert len(rows) == 1
        assert rows[0]["label"] == "tune:dk1_dnn"
        assert rows[0]["seconds"] == 1351.0

    def test_skips_blank_comment_and_malformed_lines(self) -> None:
        text = "\n# a comment\nbad line without tabs\nx\t2026\t2026\tnotanumber\n"
        assert parse_timings_log(text) == []


class TestFmtHms:
    def test_under_an_hour(self) -> None:
        assert fmt_hms(125) == "2:05"

    def test_over_an_hour(self) -> None:
        assert fmt_hms(3725) == "1:02:05"


class TestFormatBacktestTable:
    def test_one_row_per_experiment_with_dash_for_missing(self) -> None:
        table = format_backtest_table({"dk1_lear": 9084.0})
        for name in EXPERIMENTS:
            assert name in table
        # dk1_lear present -> formatted; de_lear missing -> em dash
        assert "2:31:24" in table  # 9084s
        assert table.count("| — |") >= 1  # at least one missing wall-clock


class TestFormatTuningTable:
    def test_empty_rows_message(self) -> None:
        assert "No tuning timings" in format_tuning_table([])

    def test_rows_render(self) -> None:
        rows = [{"label": "tune:dk1_dnn", "start": "a", "end": "b", "seconds": 1351.0}]
        out = format_tuning_table(rows)
        assert "tune:dk1_dnn" in out
        assert "22:31" in out  # 1351s = 22:31
