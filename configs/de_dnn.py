from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="de_dnn",
    area="DE",
    model_type="dnn",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    calibration_windows=[730],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.6, EPEX-DE): load + wind & solar.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={
        "Renewables": ["WindOnshore", "WindOffshore", "Solar"]
    },
    target_scaler="asinh",
    resample_to_hourly=True,
    # Tuned via `forecast-cli tune de_dnn --study-name de_dnn_tune_v5_paperexog`
    # on paper-exact exogenous (TotalLoad + Renewables) at hourly resolution.
    # 30-trial TPE; best = trial 11, val MAE 12.212. algo.hyperparam_trials.
    model_params={
        "hidden_units": 373,
        "activation": "relu",
        "dropout": 0.2039415317758791,
        "learning_rate": 0.0006927908325618224,
        "batch_norm": True,
        "l1_reg": 7.115104131682743e-07,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
