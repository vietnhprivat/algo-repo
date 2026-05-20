"""Smoke-test config used by `.github/workflows/pr_smoke.yml`.

Sized for speed and the synthetic data range in `tests/smoke/fixtures.py`:
short calibration window, narrow test/val windows, standard scaler.
Not deployed to production — only registered by `tests/smoke/deploy.py`.
"""
from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="smoke",
    area="DK1",
    model_type="lear",
    results_dir="results",
    test_start_date="2025-06-01",
    test_end_date="2025-06-02",
    val_start_date="2025-05-25",
    val_end_date="2025-05-31",
    calibration_windows=[14],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    target_scaler="standard",
    model_params={"alpha": 0.01},
)
