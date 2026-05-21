"""log_model_blob round-trip test."""

from __future__ import annotations

import base64

import pytest

from observability_wandb.artifacts import log_model_blob
from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


def test_log_model_blob_decodes_and_attaches(
    enabled_env: None, fake_wandb: FakeWandb
) -> None:
    tracker = WandbTracker(wandb_module=fake_wandb)
    run = fake_wandb.init(project="algo-research", id="r-1")
    raw = b"joblib-bytes-here"
    encoded = base64.b64encode(raw).decode("ascii")

    log_model_blob(
        tracker=tracker,
        run=run,
        artifact_id="art-7",
        blob_b64=encoded,
        metadata={"area": "DK1"},
    )

    assert run.artifacts_logged[0].name == "art-7"
    assert next(iter(run.artifacts_logged[0].files.values())) == raw


def test_log_model_blob_noops_when_disabled(
    monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    tracker = WandbTracker(wandb_module=fake_wandb)
    run = fake_wandb.init(project="x", id="x")

    log_model_blob(
        tracker=tracker,
        run=run,
        artifact_id="art-7",
        blob_b64=base64.b64encode(b"x").decode(),
        metadata={},
    )
    assert run.artifacts_logged == []
