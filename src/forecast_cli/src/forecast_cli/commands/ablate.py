"""`forecast-cli ablate` — drive a config-field sweep into a W&B sweep.

Examples
--------
    forecast-cli ablate dk1_lear \\
        --vary calibration_windows \\
        --over '[[56,84],[56,84,1092],[56,84,1092,1456]]'
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

import typer

from forecast_cli.config_loader import load_config
from observability_wandb.client_factory import is_enabled, load_settings

app = typer.Typer(add_completion=False, help="Drive a config-field ablation.")


def _run_backtest(cfg: Any, **_: Any) -> dict[str, float]:
    """Indirection so tests can stub the slow path.

    Runs ``BacktestRunner(cfg).execute()``, computes the metrics summary,
    and returns a dict with keys mae, rmse, smape, rmae.
    """
    from price_forecasting.backtesting.runner import BacktestRunner
    from price_forecasting.evaluation import build_weekly_naive, compute_metrics_summary

    runner = BacktestRunner(cfg)
    outputs = runner.execute()

    forecasts = outputs["forecasts"]
    actuals = outputs["actuals"]
    naive = build_weekly_naive(actuals)
    return compute_metrics_summary(forecasts, actuals, naive)


def _git_sha() -> str:
    return os.environ.get("GIT_SHA", "")


@app.command()
def main(
    config_name: str = typer.Argument(..., help="Config under configs/."),
    vary: str = typer.Option(..., "--vary", help="ExperimentConfig field to vary."),
    over: str = typer.Option(..., "--over", help="JSON list of values for the field."),
    study_name: str | None = typer.Option(
        None, "--study-name", help="W&B group/sweep name (defaults to ablate-<vary>-<config>-<sha>)."
    ),
) -> None:
    base_cfg = load_config(config_name)
    values = json.loads(over)
    if not isinstance(values, list):
        raise typer.BadParameter("--over must be a JSON list.")

    sweep = study_name or f"ablate-{vary}-{config_name}-{_git_sha()[:7]}"

    if not is_enabled():
        typer.echo(
            "W&B disabled (WANDB_MODE=disabled or WANDB_API_KEY missing); "
            "running backtests but not logging."
        )
    settings = load_settings()
    import wandb

    for idx, value in enumerate(values):
        cfg = dataclasses.replace(base_cfg, **{vary: value})
        summary = _run_backtest(cfg)
        if is_enabled():
            run = wandb.init(
                project=settings.default_project,
                entity=settings.entity,
                group=sweep,
                job_type="sweep-trial",
                tags=[cfg.area, cfg.model_type, "ablate", vary],
                config={
                    "ablation_field": vary,
                    "ablation_value": value,
                    "trial_number": idx,
                    "area": cfg.area,
                    "model_type": cfg.model_type,
                    "config_name": config_name,
                },
            )
            try:
                for key, val in summary.items():
                    run.summary[key] = val
            finally:
                run.finish()
        typer.echo(f"[{idx + 1}/{len(values)}] {vary}={value!r} -> {summary}")
