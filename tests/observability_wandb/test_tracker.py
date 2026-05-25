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


class TestLogPredictRun:
    def test_logs_prediction_table_with_correct_metadata(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        prediction = [
            {"period": 0, "timestamp_utc": "2026-05-22T00:00:00Z", "predicted": 50.1},
            {"period": 1, "timestamp_utc": "2026-05-22T01:00:00Z", "predicted": 48.4},
        ]
        tracker.log_predict_run(
            run_id="predict-2026-05-22-dk1",
            config={"area": "DK1", "target_date": "2026-05-22"},
            prediction=prediction,
            tags=["DK1", "lear", "predict"],
        )

        call = fake_wandb.init_calls[0]
        assert call["job_type"] == "predict"
        assert call["id"] == "predict-2026-05-22-dk1"

        run = fake_wandb.runs[0]
        assert run.finished is True
        assert len(run.logged) == 2
        assert run.logged[0][0]["predicted"] == 50.1


class TestLogProdReconciled:
    def test_first_call_inits_run_in_algo_prod_project(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1",
            config_name="dk1_lear",
            target_date="2026-05-21",
            metrics={"mae": 4.5, "rmse": 6.1, "smape": 11.0},
        )

        call = fake_wandb.init_calls[0]
        assert call["project"] == "algo-prod"
        assert call["entity"] == "dtu-thesis"
        assert call["id"] == "prod-dk1-dk1_lear"
        assert call["resume"] == "allow"
        assert "DK1" in call["tags"]
        assert "dk1_lear" in call["tags"]

        run = fake_wandb.runs[0]
        assert run.finished is False  # continuous, do not finish
        assert len(run.logged) == 1
        assert run.logged[0][0]["mae"] == 4.5
        assert run.logged[0][0]["target_date"] == "2026-05-21"

    def test_second_call_reuses_run_no_reinit(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-20", metrics={"mae": 5.0},
        )
        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-21", metrics={"mae": 4.5},
        )

        assert len(fake_wandb.init_calls) == 1
        assert len(fake_wandb.runs[0].logged) == 2

    def test_distinct_runs_per_area_config(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-21", metrics={"mae": 4.5},
        )
        tracker.log_prod_reconciled(
            area="DE", config_name="de_lear",
            target_date="2026-05-21", metrics={"mae": 3.8},
        )

        assert len(fake_wandb.init_calls) == 2
        ids = {c["id"] for c in fake_wandb.init_calls}
        assert ids == {"prod-dk1-dk1_lear", "prod-de-de_lear"}

    def test_model_artifact_id_is_logged_when_present(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1",
            config_name="dk1_lear",
            target_date="2026-05-21",
            metrics={"mae": 4.5},
            model_artifact_id="art-uuid-9",
        )

        payload = fake_wandb.runs[0].logged[0][0]
        assert payload["model_artifact_id"] == "art-uuid-9"

    def test_model_artifact_id_omitted_when_none(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1",
            config_name="dk1_lear",
            target_date="2026-05-21",
            metrics={"mae": 4.5},
        )

        payload = fake_wandb.runs[0].logged[0][0]
        assert "model_artifact_id" not in payload


class TestLogPredictRunWithArtifact:
    def test_init_predict_job_type_rows_artifact_and_finish(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        import base64

        tracker = WandbTracker(wandb_module=fake_wandb)
        prediction = [
            {"period": 0, "timestamp_utc": "2026-05-22T00:00:00Z", "predicted": 51.0},
            {"period": 1, "timestamp_utc": "2026-05-22T01:00:00Z", "predicted": 49.5},
        ]
        blob_b64 = base64.b64encode(b"\x00fake-model-bytes").decode("ascii")

        tracker.log_predict_run_with_artifact(
            run_id="predict-art-001",
            config={"area": "DK1", "target_date": "2026-05-22"},
            prediction=prediction,
            tags=["DK1", "lear", "predict"],
            artifact_id="artifact-uuid-1",
            artifact_blob_b64=blob_b64,
        )

        assert len(fake_wandb.init_calls) == 1
        call = fake_wandb.init_calls[0]
        assert call["job_type"] == "predict"
        assert call["id"] == "predict-art-001"

        run = fake_wandb.runs[0]
        assert len(run.logged) == 2
        assert run.logged[0][0]["predicted"] == 51.0
        assert run.logged[1][0]["predicted"] == 49.5

        assert len(run.artifacts_logged) == 1
        artifact = run.artifacts_logged[0]
        assert artifact.name == "artifact-uuid-1"

        assert run.finished is True

    def test_skips_artifact_when_no_blob(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        prediction = [{"period": 0, "predicted": 50.0}]

        tracker.log_predict_run_with_artifact(
            run_id="predict-no-art",
            config={"area": "DK1"},
            prediction=prediction,
            tags=["DK1"],
            artifact_id=None,
            artifact_blob_b64=None,
        )

        run = fake_wandb.runs[0]
        assert len(run.logged) == 1
        assert run.artifacts_logged == []
        assert run.finished is True

    def test_noops_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
    ) -> None:
        monkeypatch.setenv("WANDB_MODE", "disabled")
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_predict_run_with_artifact(
            run_id="predict-disabled",
            config={"area": "DK1"},
            prediction=[{"period": 0, "predicted": 50.0}],
            tags=["DK1"],
        )

        assert fake_wandb.init_calls == []


class TestLogArtifact:
    def test_attaches_artifact_to_run(
        self,
        enabled_env: None,
        fake_wandb: FakeWandb,
        tmp_path,
    ) -> None:
        blob = tmp_path / "model.joblib"
        blob.write_bytes(b"\x00\x01fake-joblib")

        tracker = WandbTracker(wandb_module=fake_wandb)
        run = fake_wandb.init(project="algo-research", id="r-1")

        tracker.log_artifact(
            run=run,
            artifact_id="art-uuid-1",
            artifact_type="model",
            local_path=str(blob),
            metadata={"area": "DK1", "model_type": "lear"},
        )

        assert len(run.artifacts_logged) == 1
        artifact = run.artifacts_logged[0]
        assert artifact.name == "art-uuid-1"
        assert artifact.type == "model"
        assert artifact.metadata == {"area": "DK1", "model_type": "lear"}
        assert b"fake-joblib" in next(iter(artifact.files.values()))
