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
import pandas as pd  # noqa: E402

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
            if np.isnan(value):
                txt, color = "--", "black"
            else:
                r, g, b, _ = im.cmap(im.norm(value))
                txt = f"{round(float(value), 4):.3f}"
                # white text on dark cells (very low / very high p), black on light
                color = "white" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.5 else "black"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8, color=color)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_forecast_week(forecasts_by_model, actuals, out_path: Path, start=None, days: int = 7) -> None:
    if start is None:
        selected = actuals.index[:days]
    else:
        start = pd.Timestamp(start)
        selected = actuals.index[(actuals.index >= start) & (actuals.index < start + pd.Timedelta(days=days))]
    n_periods = actuals.shape[1]
    x = np.arange(len(selected) * n_periods)
    fig, ax = plt.subplots(figsize=(9.0, 3.2))
    ax.plot(x, actuals.loc[selected].to_numpy(float).reshape(-1), color="black", lw=1.6, label="Actual")
    for name, frame in forecasts_by_model.items():
        ax.plot(x, frame.loc[selected].to_numpy(float).reshape(-1), lw=1.0, alpha=0.85, label=name)
    ax.axhline(0, color="0.6", lw=0.6, zorder=0)
    for day in range(1, len(selected)):
        ax.axvline(day * n_periods, color="grey", lw=0.4, ls=":")
    day_centres = [d * n_periods + n_periods / 2 for d in range(len(selected))]
    ax.set_xticks(day_centres)
    ax.set_xticklabels([d.strftime("%a\n%d %b") for d in selected], fontsize=7)
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
    ax.set_xlabel("hour of day")
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
        plot_mae_by_hour(forecasts_by_model, actuals, args.out_dir / f"mae_by_hour_{slug}.pdf")
        if market == "DK1":
            # Forecast-week contrast: a calm low-renewable week vs a high-renewable week.
            plot_forecast_week(forecasts_by_model, actuals, args.out_dir / "forecast_calm_dk1.pdf", start="2026-02-02")
            plot_forecast_week(forecasts_by_model, actuals, args.out_dir / "forecast_renew_dk1.pdf", start="2026-05-25")
        print(f"wrote figures for {market} -> {args.out_dir}")


if __name__ == "__main__":
    main()
