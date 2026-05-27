from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="de_dnn",
    area="DE",
    model_type="dnn",
    results_dir="results",
    test_start_date="2025-10-24",
    test_end_date="2026-05-19",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    calibration_windows=[730],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    target_scaler="asinh",
    # Tuned via `forecast-cli tune de_dnn -n 50 --study-name de_dnn_tune_v4`
    # (val MAE 20.50 on trial 18). Optimum found early and stable: a 50-trial
    # TPE search did not improve on the value first located at trial 18.
    # See algo.hyperparam_trials for the full study.
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
