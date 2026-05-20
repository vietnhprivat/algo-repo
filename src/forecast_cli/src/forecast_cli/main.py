"""Forecast CLI — run price forecasting experiments and live predictions."""

import typer

from data_cli.utils import parse_flexible_datetime
from forecast_cli.commands.tune import tune_command
from forecast_cli.config_loader import load_config
from forecast_cli.tracking import track_backtest_run, track_prediction
from price_forecasting import (
    BacktestRunner,
    LiveRunner,
    build_weekly_naive,
    compute_metrics_summary,
)

app = typer.Typer(
    help="Run price forecasting experiments and live predictions.",
)


@app.command()
def backtest(
    config_name: str = typer.Argument(
        ..., help="Name of config file in configs/ (without .py)"
    ),
    track: bool = typer.Option(
        False, "--track", help="Store run and predictions in ClickHouse"
    ),
) -> None:
    """Run a rolling-window backtest experiment."""
    config = load_config(config_name)

    typer.echo(f"Running backtest: {config.experiment_name}")
    typer.echo(f"  Area:      {config.area}")
    typer.echo(f"  Model:     {config.model_type}")
    typer.echo(f"  Windows:   {config.calibration_windows}")
    if config.exogenous_curve_types:
        typer.echo(f"  Exogenous: {', '.join(config.exogenous_curve_types)}")
    typer.echo(f"  Split:     {config.train_ratio}/{config.validation_ratio}/{config.test_ratio}")
    typer.echo("")

    runner = BacktestRunner(config)
    outputs = runner.execute()

    forecasts = outputs["forecasts"]
    actuals = outputs["actuals"]

    naive = build_weekly_naive(actuals)
    metrics = compute_metrics_summary(forecasts, actuals, naive)

    typer.echo("")
    typer.echo("Metrics Summary:")
    typer.echo(f"  MAE:   {metrics['mae']:.2f}")
    typer.echo(f"  RMSE:  {metrics['rmse']:.2f}")
    typer.echo(f"  sMAPE: {metrics['smape']:.2f}%")
    if "rmae" in metrics:
        typer.echo(f"  rMAE:  {metrics['rmae']:.4f}")

    if track:
        run_id = track_backtest_run(config, forecasts, actuals, metrics)
        typer.echo(f"\nTracked run {run_id} in ClickHouse.")


@app.command()
def predict(
    config_name: str = typer.Argument(
        ..., help="Name of config file in configs/ (without .py)"
    ),
    date: str = typer.Option(
        ..., "-d", "--date", help="Target date for prediction (e.g. 2026-03-22)"
    ),
    track: bool = typer.Option(
        False, "--track", help="Store prediction in ClickHouse"
    ),
) -> None:
    """Generate price predictions for a target date."""
    config = load_config(config_name)
    target_dt = parse_flexible_datetime(date)
    target_date_str = target_dt.strftime("%Y-%m-%d")

    typer.echo(f"Prediction for {config.area} on {target_date_str} ({config.model_type})")
    typer.echo("")

    runner = LiveRunner(config)
    prediction = runner.run_live(target_date_str)

    n_periods = len(prediction)
    minutes_per_period = 1440 // n_periods
    typer.echo(f"{'Period':>6}  {'Time':>5}  {'Price':>10}")
    for period_index in range(n_periods):
        value = prediction.iloc[period_index]
        hh = (period_index * minutes_per_period) // 60
        mm = (period_index * minutes_per_period) % 60
        typer.echo(f"  {period_index:>4}  {hh:02d}:{mm:02d}  {value:>10.2f}")

    if track:
        run_id = track_prediction(config, target_date_str, prediction)
        typer.echo(f"\nTracked prediction {run_id} in ClickHouse.")


app.command("tune")(tune_command)


if __name__ == "__main__":
    app()
