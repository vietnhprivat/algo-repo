from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_lear",
    area="DK1",
    model_type="lear",
    results_dir="results",
    test_start_date="2026-01-01",
    test_end_date="2026-03-22",
    calibration_windows=[56, 84,
                        #  1092, 1456
                        ],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    model_params={"alpha": 0.01},
)
