"""Richer W&B charts on backtest runs.

Beyond the per-day MAE/RMSE scalars, a backtest run should log
predicted-vs-actual overlay, a per-hour error profile, and a residual
distribution, built from the run's hourly (predicted, actual) records.
"""

from __future__ import annotations

from datetime import datetime, timezone

from observability_wandb.tracker import WandbTracker


def _hourly_predictions(n_days: int = 2) -> list[dict]:
    rows: list[dict] = []
    for d in range(n_days):
        for h in range(24):
            ts = datetime(2026, 1, 1 + d, h, tzinfo=timezone.utc)
            rows.append(
                {"timestamp_utc": ts, "predicted": 50.0 + h, "actual": 48.0 + h + d}
            )
    return rows


class TestBacktestCharts:
    def test_logs_overlay_per_hour_and_residual_charts(self, enabled_env, fake_wandb):
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_backtest_run(
            run_id="r1",
            config={},
            summary={"mae": 1.0},
            per_day=[{"target_date": "2026-01-01", "mae": 1.0, "rmse": 2.0}],
            tags=["DK1", "lear"],
            predictions=_hourly_predictions(),
        )

        run = fake_wandb.runs[0]
        logged_keys = set().union(*[set(p) for p, _ in run.logged]) if run.logged else set()
        assert "forecast/pred_vs_actual" in logged_keys
        assert "forecast/mae_by_hour" in logged_keys
        assert "forecast/residuals" in logged_keys

        kinds = {c.kind for c in fake_wandb.plot.calls}
        assert {"line_series", "bar", "histogram"} <= kinds
        assert run.finished is True

    def test_no_charts_when_predictions_absent(self, enabled_env, fake_wandb):
        """Backward compatible: omitting predictions logs no chart objects."""
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_backtest_run(
            run_id="r2",
            config={},
            summary={"mae": 1.0},
            per_day=[{"target_date": "2026-01-01", "mae": 1.0, "rmse": 2.0}],
            tags=["DK1", "lear"],
        )

        assert fake_wandb.plot.calls == []
        assert fake_wandb.runs[0].finished is True
