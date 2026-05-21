"""Optuna -> W&B sweep callback."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from observability_wandb.optuna_callback import build_wandb_sweep_callback

from tests.observability_wandb.conftest import FakeWandb


@dataclasses.dataclass
class _FakeStudy:
    study_name: str


@dataclasses.dataclass
class _FakeTrial:
    number: int
    params: dict[str, Any]
    value: float
    state: Any


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_PROJECT", "algo-research")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_callback_logs_one_run_per_trial(
    enabled_env: None, fake_wandb: FakeWandb
) -> None:
    callback = build_wandb_sweep_callback(
        wandb_module=fake_wandb,
        study_name="dnn_dk1_v1",
        area="DK1",
        model_type="dnn",
        config_name="dk1_dnn",
    )
    study = _FakeStudy(study_name="dnn_dk1_v1")
    trial = _FakeTrial(
        number=3,
        params={"hidden_units": 128, "learning_rate": 1e-3},
        value=4.7,
        state="COMPLETE",
    )

    callback(study, trial)

    call = fake_wandb.init_calls[0]
    assert call["project"] == "algo-research"
    assert call["group"] == "dnn_dk1_v1"
    assert call["job_type"] == "sweep-trial"
    assert call["config"] == {
        "hidden_units": 128,
        "learning_rate": 1e-3,
        "trial_number": 3,
        "area": "DK1",
        "model_type": "dnn",
        "config_name": "dk1_dnn",
    }
    assert fake_wandb.runs[0].summary == {"value": 4.7, "state": "COMPLETE"}
    assert fake_wandb.runs[0].finished is True


def test_callback_noops_when_disabled(
    monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    callback = build_wandb_sweep_callback(
        wandb_module=fake_wandb,
        study_name="s",
        area="DK1",
        model_type="dnn",
        config_name="dk1_dnn",
    )
    callback(_FakeStudy(study_name="s"), _FakeTrial(0, {}, 0.0, "COMPLETE"))
    assert fake_wandb.init_calls == []
