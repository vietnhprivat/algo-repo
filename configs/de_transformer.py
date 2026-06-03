"""DE day-ahead forecasting config — pure-Transformer model
(Llorente & Portela, 2025).

Mirror of dk1_transformer.py with area='DE'. Production deployment
defined in src/schedules/src/schedules/deploy_forecast.py:FORECAST_CONFIGS.
"""

from price_forecasting import ExperimentConfig
from price_forecasting.data import default_transformers_for_transformer

# Paper-exact exogenous (Lago EPEX-DE: load + aggregated wind & solar).
# NOTE: _EXOG must equal config.exogenous_columns (curve types + aggregate
# names, in order) — the wide feature layout is positional. If you change
# exogenous_curve_types/exogenous_aggregates below, update _EXOG to match.
_EXOG = ["TotalLoad", "Renewables"]
_SEQ = 14  # m days of past prices (paper search: m in {14, 28})

config = ExperimentConfig(
    experiment_name="de_transformer",
    area="DE",
    model_type="transformer",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    # Window verified against usable sequence rows before test start
    # (plan Task 4 step 7, measured 2026-06-04: 1265 rows >= 1092). With
    # wind/solar backfilled to 2022-03 the previous 365d data-sparsity cap
    # no longer binds.
    calibration_windows=[1092],
    refit_interval_days=7,
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={
        "Renewables": ["WindOnshore", "WindOffshore", "Solar"]
    },
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
