"""Build the modelling-side comparison tables for the report.

Reads the six final runs' outputs from results/ (forecast + actual CSVs),
aligns all models of a market on their common test days, recomputes metrics
and GW p-value matrices on that common set, pulls training durations from
algo.experiment_runs, and writes Report/metrics/model_comparison.md with
markdown tables plus LaTeX-ready versions.

Per-model raw day counts and the common-day count are reported explicitly —
models drop gap/DST days differently, so silent truncation would misread as
full coverage.

Usage:
    uv run python -m scripts.report.extract_model_comparison
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from infrastructure_clickhouse.client_factory import create_client
from price_forecasting.evaluation.summary import (
    build_dm_matrix,
    build_weekly_naive,
    compute_metrics_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
OUTPUT_PATH = REPO_ROOT / "Report" / "metrics" / "model_comparison.md"

MARKETS: dict[str, dict[str, str]] = {
    "DK1": {
        "LEAR": "dk1_lear",
        "DNN": "dk1_dnn",
        "Transformer": "dk1_transformer",
    },
    "DE": {
        "LEAR": "de_lear",
        "DNN": "de_dnn",
        "Transformer": "de_transformer",
    },
}

NAIVE = "Naive (weekly)"

# Published ensemble rMAE, Lago et al. 2021 Table 3 (Nord Pool / EPEX-DE rows).
# Different test periods (2016-2018) — rankings + rMAE compared, never MAE.
PAPER_RMAE = {
    "DK1": {"LEAR": 0.420, "DNN": 0.407},  # Nord Pool
    "DE": {"LEAR": 0.433, "DNN": 0.374},   # EPEX-DE
}
# Llorente & Portela 2025 Table 5 MAE (ranking evidence only): Transformer
# beats DNN on NP (2.33 vs 3.40) and EPEX-DE (4.03 vs 4.34).


def load_run(experiment_name: str, results_dir: Path = RESULTS_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (forecasts, actuals) wide frames with parsed DatetimeIndex."""
    forecasts = pd.read_csv(
        results_dir / f"{experiment_name}_forecasts.csv", index_col=0, parse_dates=True
    )
    actuals = pd.read_csv(
        results_dir / f"{experiment_name}_actuals.csv", index_col=0, parse_dates=True
    )
    return forecasts, actuals


def common_index(frames: list[pd.DataFrame]) -> pd.DatetimeIndex:
    """Intersection of all frames' indices, sorted."""
    index = frames[0].index
    for frame in frames[1:]:
        index = index.intersection(frame.index)
    return index.sort_values()


def errors_matrix(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> np.ndarray:
    """(n_days, n_periods) error array actuals - forecasts on the common index."""
    aligned_actuals, aligned_forecasts = actuals.align(forecasts, join="inner", axis=0)
    return aligned_actuals.to_numpy(dtype=float) - aligned_forecasts.to_numpy(dtype=float)


def build_headline_table(
    forecasts_by_model: dict[str, pd.DataFrame], actuals: pd.DataFrame
) -> pd.DataFrame:
    """MAE / RMSE / sMAPE / rMAE per model plus the weekly-naive row.

    Inputs are expected to be pre-aligned on the market's common test days.
    The naive baseline is built from the supplied actuals; its 7-day warmup
    is dropped for the naive row's own metrics (rMAE of the naive vs itself
    is 1.0 by construction).
    """
    naive = build_weekly_naive(actuals)
    rows: dict[str, dict[str, float]] = {}
    for model_name, forecasts in forecasts_by_model.items():
        metrics = compute_metrics_summary(forecasts, actuals, naive)
        rows[model_name] = {
            "MAE": metrics["mae"],
            "RMSE": metrics["rmse"],
            "sMAPE": metrics["smape"],
            "rMAE": metrics["rmae"],
        }
    naive_valid = naive.dropna()
    naive_metrics = compute_metrics_summary(naive_valid, actuals, naive)
    rows[NAIVE] = {
        "MAE": naive_metrics["mae"],
        "RMSE": naive_metrics["rmse"],
        "sMAPE": naive_metrics["smape"],
        "rMAE": naive_metrics["rmae"],
    }
    return pd.DataFrame(rows).T[["MAE", "RMSE", "sMAPE", "rMAE"]]


def build_gw_inputs(
    forecasts_by_model: dict[str, pd.DataFrame], actuals: pd.DataFrame
) -> dict[str, np.ndarray]:
    """Error arrays for the GW matrix: all models + naive, on the days where
    the naive is defined (post-warmup), guaranteeing identical shapes."""
    naive_valid = build_weekly_naive(actuals).dropna()
    gw_days = naive_valid.index
    gw_actuals = actuals.loc[gw_days]
    errors: dict[str, np.ndarray] = {}
    for model_name, forecasts in forecasts_by_model.items():
        errors[model_name] = errors_matrix(forecasts.loc[gw_days], gw_actuals)
    errors[NAIVE] = errors_matrix(naive_valid, gw_actuals)
    return errors


def fetch_training_durations(experiment_names: list[str]) -> dict[str, float]:
    """Latest tracked training_duration_seconds per experiment from ClickHouse."""
    client = create_client()
    try:
        result = client.query(
            "SELECT experiment_name, argMax(training_duration_seconds, created_utc) "
            "FROM algo.experiment_runs FINAL "
            "WHERE experiment_name IN {names:Array(String)} "
            "GROUP BY experiment_name",
            parameters={"names": experiment_names},
        )
        return {row[0]: float(row[1]) for row in result.result_rows}
    finally:
        client.close()


def to_latex_booktabs(table: pd.DataFrame, caption: str, label: str) -> str:
    body = table.to_latex(float_format="%.3f", na_rep="--")
    return (
        "\\begin{table}[h]\n  \\centering\n"
        f"  \\caption{{{caption}}}\n  \\label{{{label}}}\n"
        f"{body}"
        "\\end{table}\n"
    )


def build_market_section(
    market: str,
    experiments: dict[str, str],
    durations: dict[str, float],
    results_dir: Path = RESULTS_DIR,
) -> str:
    raw_forecasts: dict[str, pd.DataFrame] = {}
    raw_counts: dict[str, int] = {}
    actuals_frames: list[pd.DataFrame] = []
    for model_name, experiment_name in experiments.items():
        forecasts, actuals = load_run(experiment_name, results_dir)
        raw_forecasts[model_name] = forecasts
        raw_counts[model_name] = len(forecasts)
        actuals_frames.append(actuals)

    common = common_index(list(raw_forecasts.values()) + actuals_frames)
    forecasts_by_model = {
        name: frame.loc[common] for name, frame in raw_forecasts.items()
    }
    actuals = actuals_frames[0].loc[common]

    headline = build_headline_table(forecasts_by_model, actuals)
    gw = build_dm_matrix(build_gw_inputs(forecasts_by_model, actuals), norm=1)

    cost = pd.DataFrame.from_dict(
        {
            model_name: durations.get(experiment_name, float("nan")) / len(common)
            for model_name, experiment_name in experiments.items()
        },
        orient="index",
        columns=["seconds/recalibration-day"],
    )

    paper = pd.DataFrame.from_dict(
        PAPER_RMAE[market], orient="index", columns=["paper rMAE (Lago T3)"]
    )
    paper["ours rMAE"] = headline["rMAE"]

    coverage = ", ".join(f"{name}: {count}" for name, count in raw_counts.items())
    lines = [
        f"\n## {market}\n",
        f"Raw test days per run — {coverage}; common days used: {len(common)} "
        f"(GW matrix additionally drops the 7-day naive warmup).\n",
        "### Headline metrics (common days)\n",
        headline.round(3).to_markdown() + "\n",
        "### GW p-values (column better than row)\n",
        gw.round(4).to_markdown() + "\n",
        "### Computation cost\n",
        cost.round(1).to_markdown() + "\n",
        "### vs published benchmarks (rMAE; periods differ — rankings only)\n",
        paper.round(3).to_markdown() + "\n",
        "### LaTeX\n```latex\n",
        to_latex_booktabs(
            headline.round(3),
            caption=f"{market}: final benchmark metrics (test 2025-10-24--2026-05-31, common days).",
            label=f"tab:results-{market.lower()}-headline",
        ),
        to_latex_booktabs(
            gw.round(4),
            caption=f"{market}: GW multivariate p-values (column better than row).",
            label=f"tab:results-{market.lower()}-gw",
        ),
        "```\n",
    ]
    return "\n".join(lines)


def main() -> None:
    sections: list[str] = ["# Model comparison — final benchmark\n"]
    sections.append(
        "Generated by `scripts/report/extract_model_comparison.py`. "
        "Test window 2025-10-24 → 2026-05-31; per market, all models are "
        "compared on their common surviving test days.\n"
    )
    all_experiments = [
        experiment for market in MARKETS.values() for experiment in market.values()
    ]
    durations = fetch_training_durations(all_experiments)

    for market, experiments in MARKETS.items():
        sections.append(build_market_section(market, experiments, durations))

    OUTPUT_PATH.write_text("\n".join(sections))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
