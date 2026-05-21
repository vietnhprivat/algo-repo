"""Tracker-level no-op semantics."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


class TestNoOpWhenDisabled:
    def test_log_backtest_run_noops_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
    ) -> None:
        monkeypatch.setenv("WANDB_MODE", "disabled")
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_backtest_run(
            run_id="r1",
            config={"area": "DK1"},
            summary={"mae": 5.0},
            per_day=[],
            tags=[],
        )

        assert fake_wandb.init_calls == []
        assert fake_wandb.runs == []

    def test_enabled_when_key_present(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        assert tracker.is_enabled is True


class TestLogBacktestRun:
    def test_init_finish_and_per_day_logged(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        per_day = [
            {"target_date": "2026-01-01", "mae": 5.1, "rmse": 7.0},
            {"target_date": "2026-01-02", "mae": 4.8, "rmse": 6.4},
        ]
        tracker.log_backtest_run(
            run_id="r-001",
            config={"area": "DK1", "model_type": "lear", "alpha": 0.01},
            summary={"mae": 4.95, "rmse": 6.7, "smape": 12.0, "rmae": 0.82},
            per_day=per_day,
            tags=["DK1", "lear", "git:abc123"],
        )

        assert len(fake_wandb.init_calls) == 1
        call = fake_wandb.init_calls[0]
        assert call["project"] == "algo-research"
        assert call["entity"] == "dtu-thesis"
        assert call["id"] == "r-001"
        assert call["job_type"] == "backtest"
        assert call["tags"] == ["DK1", "lear", "git:abc123"]
        assert call["config"] == {
            "area": "DK1",
            "model_type": "lear",
            "alpha": 0.01,
        }

        run = fake_wandb.runs[0]
        assert run.finished is True
        assert [step for _, step in run.logged] == [0, 1]
        assert run.logged[0][0]["mae"] == 5.1
        assert run.logged[1][0]["rmse"] == 6.4
        assert run.summary == {
            "mae": 4.95,
            "rmse": 6.7,
            "smape": 12.0,
            "rmae": 0.82,
        }
