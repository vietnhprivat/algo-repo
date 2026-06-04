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
    # INTERIM — re-tune pending (plan Task 7): tuned on TotalLoad-only
    # features (study de_dnn_tune_v4); replaced by the paper-exog re-tune.
    model_params={
        "hidden_units": 58,
        "activation": "elu",
        "dropout": 0.13216185974066028,
        "learning_rate": 0.004855834388063902,
        "batch_norm": False,
        "l1_reg": 0.0005710947096868873,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
