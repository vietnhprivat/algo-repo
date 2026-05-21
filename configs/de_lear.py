from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="de_lear",
    area="DE",
    model_type="lear",
    results_dir="results",
    test_start_date="2024-05-20",
    test_end_date="2026-05-19",
    val_start_date="2023-07-30",
    val_end_date="2024-05-19",
    calibration_windows=[56, 84, 1092, 1456],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    target_scaler="asinh",
    model_params={"alpha": "auto"},
)
