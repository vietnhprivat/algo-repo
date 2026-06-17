from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk2_lear",
    area="DK2",
    model_type="lear",
    results_dir="results",
    # Shared final-benchmark test window (mirrors dk1_lear).
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    # DK2 price history starts 2026-04-28 (15-min, ~7 weeks), so the paper
    # ensemble windows do not fit yet. Use short windows until the history
    # grows — the same data-history reasoning the thesis applies to DE.
    calibration_windows=[14],
    refit_interval_days=1,
    # Paper-exact Nord Pool exogenous: load + wind generation (same as DK1).
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
    target_scaler="asinh",
    resample_to_hourly=True,
    model_params={"alpha": "auto"},
)
