from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_dnn",
    area="DK1",
    model_type="dnn",
    results_dir="results",
    test_start_date="2024-05-20",
    test_end_date="2026-05-19",
    val_start_date="2023-07-30",
    val_end_date="2024-05-19",
    # DNN: longer calibration window; ensemble of 4 (Lago §4.4).
    calibration_windows=[1456],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    target_scaler="asinh",
    # Replace with `forecast-cli tune dk1_dnn` best_params.
    model_params={
        "hidden_units": 256,
        "activation": "relu",
        "dropout": 0.1,
        "learning_rate": 1e-3,
        "batch_norm": False,
        "l1_reg": 1e-4,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
