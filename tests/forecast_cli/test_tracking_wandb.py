"""Backtest dual-write to W&B (in addition to ClickHouse)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "dtu-thesis")
    monkeypatch.setenv("WANDB_PROJECT", "algo-research")
    monkeypatch.setenv("WANDB_MODE", "online")


def _make_wide_frames(n_days: int = 3, n_periods: int = 24) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    cols = [f"h{i}" for i in range(n_periods)]
    rng = np.random.default_rng(0)
    forecasts = pd.DataFrame(
        rng.standard_normal((n_days, n_periods)) * 5 + 50, index=dates, columns=cols
    )
    actuals = pd.DataFrame(
        rng.standard_normal((n_days, n_periods)) * 5 + 50, index=dates, columns=cols
    )
    return forecasts, actuals


def _patch_ch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ClickHouse infrastructure so no real connection is attempted."""
    from forecast_cli import tracking

    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )
    fake_client = MagicMock()
    monkeypatch.setattr(tracking, "create_client", lambda: fake_client, raising=True)


def _make_config():
    from price_forecasting.configs import ExperimentConfig

    return ExperimentConfig(
        experiment_name="test_exp",
        results_dir="/tmp/results",
        area="DK1",
        model_type="lear",
    )


def test_backtest_dual_writes_to_wandb(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling track_backtest_run with a tracker writes to W&B in addition to CH."""
    _patch_ch(monkeypatch)

    tracker = WandbTracker(wandb_module=fake_wandb)
    forecasts, actuals = _make_wide_frames()
    config = _make_config()
    metrics = {"mae": 4.95, "rmse": 6.7, "smape": 12.0}

    from forecast_cli.tracking import track_backtest_run

    track_backtest_run(
        config,
        forecasts,
        actuals,
        metrics,
        tracker=tracker,
    )

    assert len(fake_wandb.init_calls) == 1
    assert fake_wandb.init_calls[0]["job_type"] == "backtest"
    assert fake_wandb.runs[0].finished is True


def test_predict_dual_writes_to_wandb(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling track_prediction with a tracker writes to W&B in addition to CH."""
    from forecast_cli import tracking

    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )
    monkeypatch.setattr(
        tracking, "insert_model_artifact", lambda *a, **k: None, raising=True
    )
    fake_client = MagicMock()
    monkeypatch.setattr(tracking, "create_client", lambda: fake_client, raising=True)

    tracker = WandbTracker(wandb_module=fake_wandb)
    config = _make_config()
    predictions = pd.Series([50.0 + i for i in range(24)], dtype=float)

    tracking.track_prediction(
        config,
        "2026-05-22",
        predictions,
        trained_models={"model_key": "fake_model_object"},
        tracker=tracker,
    )

    assert len(fake_wandb.init_calls) == 1
    assert fake_wandb.init_calls[0]["job_type"] == "predict"
    assert fake_wandb.runs[0].finished is True
    # prediction rows were logged (one per period)
    assert len(fake_wandb.runs[0].logged) == 24
    # artifact was attached because trained_models was provided
    assert len(fake_wandb.runs[0].artifacts_logged) == 1


def test_predict_no_artifact_when_no_trained_models(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no trained_models are given, no artifact is attached."""
    from forecast_cli import tracking

    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )
    fake_client = MagicMock()
    monkeypatch.setattr(tracking, "create_client", lambda: fake_client, raising=True)

    tracker = WandbTracker(wandb_module=fake_wandb)
    config = _make_config()
    predictions = pd.Series([50.0] * 24, dtype=float)

    tracking.track_prediction(
        config,
        "2026-05-22",
        predictions,
        tracker=tracker,
    )

    assert len(fake_wandb.init_calls) == 1
    assert fake_wandb.init_calls[0]["job_type"] == "predict"
    assert fake_wandb.runs[0].artifacts_logged == []


def test_backtest_disabled_tracker_skips_wandb(
    monkeypatch: pytest.MonkeyPatch,
    fake_wandb: FakeWandb,
) -> None:
    """When W&B is disabled the tracker is a no-op and no init is called."""
    monkeypatch.setenv("WANDB_MODE", "disabled")
    _patch_ch(monkeypatch)

    tracker = WandbTracker(wandb_module=fake_wandb)
    forecasts, actuals = _make_wide_frames()
    config = _make_config()

    from forecast_cli.tracking import track_backtest_run

    track_backtest_run(
        config,
        forecasts,
        actuals,
        {"mae": 1.0},
        tracker=tracker,
    )

    assert fake_wandb.init_calls == []


def test_backtest_continues_when_wandb_raises(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A W&B failure must not break the backtest tracking."""
    _patch_ch(monkeypatch)

    class _RaisingFakeWandb(FakeWandb):
        def init(self, **kwargs):
            raise RuntimeError("W&B outage")

    raising = _RaisingFakeWandb()
    tracker = WandbTracker(wandb_module=raising)
    forecasts, actuals = _make_wide_frames()
    config = _make_config()
    metrics = {"mae": 4.95, "rmse": 6.7, "smape": 12.0}

    from forecast_cli.tracking import track_backtest_run

    # Must not raise even though W&B init throws.
    run_id = track_backtest_run(
        config,
        forecasts,
        actuals,
        metrics,
        tracker=tracker,
    )
    assert run_id  # ClickHouse path still returned a run_id


def test_predict_continues_when_wandb_raises(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A W&B failure must not break the live prediction tracking."""
    from forecast_cli import tracking

    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )
    monkeypatch.setattr(
        tracking, "insert_model_artifact", lambda *a, **k: None, raising=True
    )
    fake_client = MagicMock()
    monkeypatch.setattr(tracking, "create_client", lambda: fake_client, raising=True)

    class _RaisingFakeWandb(FakeWandb):
        def init(self, **kwargs):
            raise RuntimeError("W&B outage")

    raising = _RaisingFakeWandb()
    tracker = WandbTracker(wandb_module=raising)
    config = _make_config()
    predictions = pd.Series([50.0 + i for i in range(24)], dtype=float)

    # Must not raise even though W&B init throws.
    run_id = tracking.track_prediction(
        config,
        "2026-05-22",
        predictions,
        trained_models={"model_key": "fake_model_object"},
        tracker=tracker,
    )
    assert run_id  # ClickHouse path still returned a run_id
