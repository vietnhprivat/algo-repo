"""`forecast-cli tune <config>` — Optuna TPE search for DNN hyperparameters."""
from datetime import datetime, timezone
from typing import Optional

import optuna
import typer

from forecast_cli.config_loader import load_config
from price_forecasting.tuning.dnn_search import build_dnn_search_space
from price_forecasting.tuning.objective import dnn_validation_objective
from price_forecasting.tuning.optuna_storage import build_persistence_callback


def tune_command(
    config_name: str = typer.Argument(...),
    n_trials: int = typer.Option(100, "--n-trials", "-n"),
    study_name: Optional[str] = typer.Option(None, "--study-name"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run Optuna TPE search for a config's DNN hyperparameters."""
    config = load_config(config_name)
    if config.model_type != "dnn":
        raise typer.BadParameter(
            f"tune supports model_type='dnn' only; {config_name} uses "
            f"model_type={config.model_type!r}"
        )
    if not config.val_start_date or not config.val_end_date:
        raise typer.BadParameter(
            "tune requires val_start_date and val_end_date on the config"
        )

    name = study_name or f"{config_name}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    typer.echo(f"study_name={name} n_trials={n_trials}")
    if dry_run:
        return

    from infrastructure_clickhouse.client_factory import create_client
    from infrastructure_clickhouse.ingest import insert_hyperparam_trial

    client = create_client()

    class _Inserter:
        def insert_hyperparam_trial(self, **kwargs):
            insert_hyperparam_trial(client, **kwargs)

    cb = build_persistence_callback(
        client=_Inserter(),
        study_name=name,
        area=config.area,
        model_type=config.model_type,
        config_name=config_name,
        val_start_utc=datetime.fromisoformat(config.val_start_date).replace(tzinfo=timezone.utc),
        val_end_utc=datetime.fromisoformat(config.val_end_date).replace(tzinfo=timezone.utc),
    )

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=42, multivariate=True),
    )
    try:
        study.optimize(
            lambda t: dnn_validation_objective(t, config, build_dnn_search_space),
            n_trials=n_trials,
            callbacks=[cb],
            show_progress_bar=True,
        )
    finally:
        client.close()

    typer.echo(f"best_value={study.best_value:.6f}")
    typer.echo(f"best_params={study.best_params}")
