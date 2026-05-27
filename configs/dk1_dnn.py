from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_dnn",
    area="DK1",
    model_type="dnn",
    results_dir="results",
    test_start_date="2025-10-24",
    test_end_date="2026-05-19",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    # DNN: longer calibration window; ensemble of 4 (Lago §4.4).
    calibration_windows=[730],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    target_scaler="asinh",
    # Tuned via `forecast-cli tune dk1_dnn -n 50 --study-name dk1_dnn_tune_v3`
    # (val MAE 21.24 on trial 26). Optimum found early and stable: a 50-trial
    # TPE search did not improve on the value first located at trial 26.
    # See algo.hyperparam_trials for the full study.
    model_params={
        "hidden_units": 198,
        "activation": "tanh",
        "dropout": 0.02680613227742755,
        "learning_rate": 0.000627980254004135,
        "batch_norm": False,
        "l1_reg": 0.0006727849421606088,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
