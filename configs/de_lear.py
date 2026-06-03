from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="de_lear",
    area="DE",
    model_type="lear",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    calibration_windows=[56, 84, 1092],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.6, EPEX-DE): zonal load + aggregated
    # wind & solar generation forecasts.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={
        "Renewables": ["WindOnshore", "WindOffshore", "Solar"]
    },
    target_scaler="asinh",
    model_params={"alpha": "auto"},
)
