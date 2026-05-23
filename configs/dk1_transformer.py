"""DK1 day-ahead forecasting config — pure-Transformer model
(Llorente & Portela, 2025).

NOT a production deployment: this config is not present in
src/schedules/src/schedules/deploy_forecast.py:FORECAST_CONFIGS. It exists so
the Transformer implementation can be exercised via:

    uv run python -m forecast_cli.main backtest dk1_transformer
    uv run python -m forecast_cli.main predict  dk1_transformer -d <YYYY-MM-DD>

Defaults below follow the paper's Nord Pool / EPEX search ranges.
"""

from price_forecasting import ExperimentConfig
from price_forecasting.data import default_transformers_for_transformer

_EXOG = ["TotalLoad", "Generation"]
_SEQ = 14  # m days of past prices (paper search: m in {14, 28})

config = ExperimentConfig(
    experiment_name="dk1_transformer",
    area="DK1",
    model_type="transformer",
    results_dir="results",
    test_start_date="2026-01-01",
    test_end_date="2026-03-22",
    calibration_windows=[1092],
    refit_interval_days=7,
    exogenous_curve_types=_EXOG,
    target_scaler="asinh",
    feature_transformers=default_transformers_for_transformer(
        exogenous_columns=_EXOG,
        sequence_length_days=_SEQ,
    ),
    model_params={
        "seq_length_days": _SEQ,
        "n_exog": len(_EXOG),
        "embedding_dim": 128,
        "n_heads": 8,
        "n_encoder_layers": 6,
        "ff_dim": 1024,
        "dropout": 0.2,
        "mlp_hidden": 128,
        "gradient_clip_val": None,
        "lr_scheduler_step": 70,
        "lr_scheduler_gamma": 0.1,
        "epochs": 200,
        "batch_size": 32,
        "learning_rate": 1e-4,
        "validation_fraction": 0.16,
        "early_stopping_patience": 25,
        "random_seed": 42,
    },
)
