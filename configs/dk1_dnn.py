from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_dnn",
    area="DK1",
    model_type="dnn",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    # 42-week validation window for Optuna tuning (ex-ante: ends the day
    # before the test window starts).
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    # DNN: single long window (Lago §4.3 uses 4 years; 730d kept as the
    # documented data/compute-constrained deviation). Ensemble of 4 (Lago §4.4).
    calibration_windows=[730],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.1, Nord Pool): load + wind generation.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
    target_scaler="asinh",
    resample_to_hourly=True,
    # Tuned via `forecast-cli tune dk1_dnn --study-name dk1_dnn_tune_v5_paperexog`
    # on paper-exact exogenous (TotalLoad + Wind) at hourly resolution.
    # 30-trial TPE; best = trial 26, val MAE 19.069 (optimum improved from the
    # trial-6 plateau at trial 26, so 30 trials was warranted). algo.hyperparam_trials.
    model_params={
        "hidden_units": 191,
        "activation": "tanh",
        "dropout": 0.20294297230504066,
        "learning_rate": 0.00047588549478188745,
        "batch_norm": False,
        "l1_reg": 6.84305397641749e-08,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
