"""Durable run-timing record for the report's computation-cost section.

Merges two sources into Report/metrics/run_timings.md:
  1. Backtest wall-clock from algo.experiment_runs.training_duration_seconds
     (persisted by `forecast-cli backtest --track`).
  2. Tuning wall-clock (and any redundant captures) from the plain-text log
     results/run_timings.log, appended by launch wrappers.

Usage:
    uv run python -m scripts.report.extract_run_timings
"""

from __future__ import annotations

from pathlib import Path

from infrastructure_clickhouse.client_factory import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMINGS_LOG = REPO_ROOT / "results" / "run_timings.log"
OUTPUT_PATH = REPO_ROOT / "Report" / "metrics" / "run_timings.md"

HARDWARE = "NVIDIA RTX 3060 GPU, 16 CPU cores"

EXPERIMENTS = ["dk1_lear", "de_lear", "dk1_dnn", "de_dnn",
               "dk1_transformer", "de_transformer"]

# Static run metadata (refit cadence / calibration window / ensemble / resolution).
META: dict[str, dict[str, str]] = {
    "dk1_lear": {"refit": "daily", "window": "56/84/1092", "ensemble": "1", "resolution": "hourly (24)"},
    "de_lear": {"refit": "daily", "window": "56/84/1092", "ensemble": "1", "resolution": "hourly (24, from 15-min)"},
    "dk1_dnn": {"refit": "daily", "window": "730", "ensemble": "4", "resolution": "hourly (24)"},
    "de_dnn": {"refit": "daily", "window": "730", "ensemble": "4", "resolution": "hourly (24, from 15-min)"},
    "dk1_transformer": {"refit": "weekly", "window": "1092", "ensemble": "1", "resolution": "hourly (24)"},
    "de_transformer": {"refit": "weekly", "window": "1092", "ensemble": "1", "resolution": "hourly (24, from 15-min)"},
}


def parse_timings_log(text: str) -> list[dict]:
    """Parse the TSV timings log. Lines: label<TAB>start_iso<TAB>end_iso<TAB>seconds.
    Blank lines and lines starting with '#' are ignored. Malformed lines are skipped."""
    rows: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        label, start, end, seconds = parts
        try:
            secs = float(seconds)
        except ValueError:
            continue
        rows.append({"label": label, "start": start, "end": end, "seconds": secs})
    return rows


def fmt_hms(seconds: float) -> str:
    """Human-readable H:MM:SS (or M:SS under an hour)."""
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_backtest_table(durations: dict[str, float]) -> str:
    """Markdown table of backtest wall-clock + static metadata, one row per experiment."""
    header = (
        "| Experiment | Model | Resolution | Refit | Window(s) | Ensemble | Wall-clock | Seconds |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for name in EXPERIMENTS:
        meta = META[name]
        model = name.split("_", 1)[1]
        secs = durations.get(name)
        wall = fmt_hms(secs) if secs is not None else "—"
        secs_str = f"{secs:.0f}" if secs is not None else "—"
        lines.append(
            f"| {name} | {model} | {meta['resolution']} | {meta['refit']} | "
            f"{meta['window']} | {meta['ensemble']} | {wall} | {secs_str} |"
        )
    return header + "\n".join(lines) + "\n"


def format_tuning_table(rows: list[dict]) -> str:
    """Markdown table of tuning / extra-log timings."""
    if not rows:
        return "_No tuning timings logged yet (results/run_timings.log absent or empty)._\n"
    header = "| Label | Start | End | Wall-clock |\n|---|---|---|---|\n"
    lines = [
        f"| {r['label']} | {r['start']} | {r['end']} | {fmt_hms(r['seconds'])} |"
        for r in rows
    ]
    return header + "\n".join(lines) + "\n"


def fetch_backtest_durations() -> dict[str, float]:
    client = create_client()
    try:
        result = client.query(
            "SELECT experiment_name, argMax(training_duration_seconds, created_utc) "
            "FROM algo.experiment_runs FINAL "
            "WHERE experiment_name IN {names:Array(String)} "
            "GROUP BY experiment_name",
            parameters={"names": EXPERIMENTS},
        )
        return {row[0]: float(row[1]) for row in result.result_rows}
    finally:
        client.close()


def main() -> None:
    durations = fetch_backtest_durations()
    log_rows = parse_timings_log(TIMINGS_LOG.read_text()) if TIMINGS_LOG.exists() else []

    sections = [
        "# Run timings — final benchmark\n",
        f"Hardware: {HARDWARE}. Backtest wall-clock is the full rolling-window "
        "run (all refits), read from `algo.experiment_runs.training_duration_seconds` "
        "(persisted by `forecast-cli backtest --track`). Tuning timings are from "
        "`results/run_timings.log`.\n",
        "## Backtests\n",
        format_backtest_table(durations),
        "\n## Tuning and other timed steps\n",
        format_tuning_table(log_rows),
        "\n## Notes\n",
        "- All runs are modelled at hourly resolution (24 periods); the 15-min "
        "DE and post-2025-10 DK1 prices are downsampled to an hourly mean, so "
        "both markets fit the same number of per-period Lasso models.\n",
        "- DNN and Transformer are MIMO (one GPU network for all periods); the "
        "Transformer refits weekly, so its run is dominated by ~32 trainings.\n",
        "- Single-refit GPU probe (2026-06-04): dk1_dnn 4-net ensemble ~10s; "
        "dk1_transformer ~17s.\n",
    ]
    OUTPUT_PATH.write_text("\n".join(sections))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
