from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_lear",
    area="DK1",
    model_type="lear",
    results_dir="results",
    # Shared final-benchmark test window (all six configs identical) — the
    # longest window keeping DNN tuning ex-ante (val ends 2025-10-23).
    # Lago et al. 2021 recommend >= 1 year; 31 weeks is the documented,
    # data-constrained deviation (spec 2026-06-04).
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    # Validation window: 42 weeks immediately preceding test (Lago §4.3.2).
    # Used by `forecast-cli tune` only; backtests train on all pre-test data.
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    # Paper-correct ensemble windows (Lago Table 2); 1456d removed (dips into 2022).
    calibration_windows=[56, 84, 1092],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.1, Nord Pool): load + wind generation.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
    target_scaler="asinh",
    resample_to_hourly=True,
    model_params={"alpha": "auto"},
)
