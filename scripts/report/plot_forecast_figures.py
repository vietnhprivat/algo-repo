"""Render the forecasting-results figures for the report.

Reads the six final runs' forecast/actual CSVs from results/, aligns each
market's models on their common test days, and writes three figures per market
into Report/figures/results_models/:

  - gw_heatmap_{market}.pdf     Giacomini--White pairwise p-value matrix
  - forecast_week_{market}.pdf  one representative week, predicted vs actual
  - mae_by_hour_{market}.pdf    mean absolute error by delivery period

Runnable now; a market whose run outputs are absent is skipped with a note, so
this produces the final figures only once the tracked backtests have completed.

Usage:
    uv run python -m scripts.report.plot_forecast_figures
    uv run python -m scripts.report.plot_forecast_figures --help
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Match the thesis body font (Liberation Sans, the Arial-metric DTU font) so the
# rendered figures are typographically consistent with the surrounding text.
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Liberation Sans", "Arial", "DejaVu Sans"]

from price_forecasting.evaluation.summary import build_dm_matrix  # noqa: E402
from scripts.report.extract_model_comparison import (  # noqa: E402
    MARKETS,
    build_gw_inputs,
    common_index,
    load_run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIG_DIR = REPO_ROOT / "Report" / "figures" / "results_models"


def _market_frames(experiments: dict[str, str], results_dir: Path):
    """(forecasts_by_model, actuals) aligned on the market's common test days."""
    raw_forecasts: dict[str, "object"] = {}
    actuals_frames = []
    for model_name, experiment_name in experiments.items():
        forecasts, actuals = load_run(experiment_name, results_dir)
        raw_forecasts[model_name] = forecasts
        actuals_frames.append(actuals)
    common = common_index(list(raw_forecasts.values()) + actuals_frames)
    forecasts_by_model = {name: frame.loc[common] for name, frame in raw_forecasts.items()}
    return forecasts_by_model, actuals_frames[0].loc[common]


def plot_gw_heatmap(forecasts_by_model, actuals, out_path: Path) -> None:
    matrix = build_dm_matrix(build_gw_inputs(forecasts_by_model, actuals), norm=1)
    labels = list(matrix.columns)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    im = ax.imshow(data, vmin=0.0, vmax=1.0, cmap="RdYlGn_r")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            value = data[i, j]
            ax.text(
                j, i, "--" if np.isnan(value) else f"{round(float(value), 4):.3f}",
                ha="center", va="center", fontsize=8,
            )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_forecast_week(forecasts_by_model, actuals, out_path: Path, days: int = 7) -> None:
    selected = actuals.index[:days]
    n_periods = actuals.shape[1]
    x = np.arange(len(selected) * n_periods)
    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    ax.plot(x, actuals.loc[selected].to_numpy(float).reshape(-1), color="black", lw=1.6, label="Actual")
    for name, frame in forecasts_by_model.items():
        ax.plot(x, frame.loc[selected].to_numpy(float).reshape(-1), lw=1.0, alpha=0.85, label=name)
    for day in range(1, len(selected)):
        ax.axvline(day * n_periods, color="grey", lw=0.4, ls=":")
    ax.set_xlabel("hour of week")
    ax.set_ylabel("price (EUR/MWh)")
    ax.legend(ncol=4, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_mae_by_hour(forecasts_by_model, actuals, out_path: Path) -> None:
    actual = actuals.to_numpy(float)
    n_periods = actuals.shape[1]
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    for name, frame in forecasts_by_model.items():
        mae = np.mean(np.abs(actual - frame.to_numpy(float)), axis=0)
        ax.plot(range(n_periods), mae, marker="o", ms=2.5, lw=1.0, label=name)
    ax.set_xlabel("delivery period")
    ax.set_ylabel("MAE (EUR/MWh)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help="directory of {experiment}_forecasts.csv / _actuals.csv")
    parser.add_argument("--out-dir", type=Path, default=FIG_DIR, help="output directory for figure PDFs")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for market, experiments in MARKETS.items():
        slug = market.lower()
        missing = [e for e in experiments.values() if not (args.results_dir / f"{e}_forecasts.csv").exists()]
        if missing:
            print(f"skipping {market}: missing run outputs for {missing} (run the backtests first)")
            continue
        forecasts_by_model, actuals = _market_frames(experiments, args.results_dir)
        plot_gw_heatmap(forecasts_by_model, actuals, args.out_dir / f"gw_heatmap_{slug}.pdf")
        plot_forecast_week(forecasts_by_model, actuals, args.out_dir / f"forecast_week_{slug}.pdf")
        plot_mae_by_hour(forecasts_by_model, actuals, args.out_dir / f"mae_by_hour_{slug}.pdf")
        print(f"wrote 3 figures for {market} -> {args.out_dir}")


if __name__ == "__main__":
    main()
