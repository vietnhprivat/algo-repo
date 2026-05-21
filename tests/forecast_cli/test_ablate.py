"""ablate command: end-to-end with stubbed BacktestRunner."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_ablate_runs_one_w_and_b_run_per_variant(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forecast_cli.commands import ablate

    captured: list[Any] = []

    def fake_backtest(cfg: Any, **_: Any) -> dict[str, float]:
        captured.append(cfg.calibration_windows)
        return {"mae": 5.0 + len(captured), "rmse": 7.0, "smape": 11.0, "rmae": 0.9}

    monkeypatch.setattr(ablate, "_run_backtest", fake_backtest, raising=True)

    # Patch wandb.init so the ablate command doesn't try to hit real W&B
    import wandb as wandb_module
    monkeypatch.setattr(wandb_module, "init", fake_wandb.init, raising=True)

    runner = CliRunner()
    result = runner.invoke(
        ablate.app,
        [
            "dk1_lear",
            "--vary", "calibration_windows",
            "--over", "[[56,84],[56,84,1092],[56,84,1092,1456]]",
            "--study-name", "ablate-cw-test",
        ],
        env={
            "WANDB_API_KEY": "k",
            "WANDB_ENTITY": "e",
            "WANDB_MODE": "online",
        },
    )

    if result.exit_code != 0:
        print(result.output)
        print(result.exception)

    assert result.exit_code == 0
    # 3 variants, 3 backtest runs, 3 W&B runs
    assert len(captured) == 3
    # Each W&B run is a sweep-trial under the same group/study
    assert len(fake_wandb.init_calls) == 3
    groups = {c["group"] for c in fake_wandb.init_calls}
    assert groups == {"ablate-cw-test"}
