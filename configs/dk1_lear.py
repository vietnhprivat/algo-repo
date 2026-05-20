from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_lear",
    area="DK1",
    model_type="lear",
    results_dir="results",
    # Lago et al. 2021 recommend >= 1 year, prefer 2 years.
    test_start_date="2024-05-20",
    test_end_date="2026-05-19",
    # Validation window: 42 weeks immediately preceding test (Lago §4.3.2).
    val_start_date="2023-07-30",
    val_end_date="2024-05-19",
    # Paper-correct ensemble windows (Lago Table 2).
    calibration_windows=[56, 84, 1092, 1456],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    target_scaler="asinh",
    model_params={"alpha": 0.01},
)
