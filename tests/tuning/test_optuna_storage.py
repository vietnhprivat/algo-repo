import json
from datetime import datetime, timezone

import optuna

from price_forecasting.tuning.optuna_storage import build_persistence_callback


class _FakeClient:
    def __init__(self):
        self.rows = []

    def insert_hyperparam_trial(self, **kwargs):
        self.rows.append(kwargs)


class TestOptunaStorage:
    def test_persistence_callback_inserts_completed_trials(self):
        fake = _FakeClient()
        cb = build_persistence_callback(
            client=fake,
            study_name="test_study",
            area="DK1",
            model_type="dnn",
            config_name="dk1_dnn",
            val_start_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
            val_end_utc=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        study = optuna.create_study(direction="minimize")
        study.optimize(
            lambda trial: (trial.suggest_float("x", -5, 5)) ** 2,
            n_trials=5, callbacks=[cb], show_progress_bar=False,
        )
        assert len(fake.rows) == 5
        assert all(r["state"] == "COMPLETE" for r in fake.rows)
        assert all(r["study_name"] == "test_study" for r in fake.rows)
        assert all("x" in json.loads(r["params_json"]) for r in fake.rows)
        assert all(r["trial_number"] == i for i, r in enumerate(fake.rows))

    def test_persistence_callback_records_duration(self):
        fake = _FakeClient()
        cb = build_persistence_callback(
            client=fake,
            study_name="t",
            area="DK1",
            model_type="dnn",
            config_name="dk1_dnn",
            val_start_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
            val_end_utc=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        study = optuna.create_study(direction="minimize")
        study.optimize(
            lambda trial: trial.suggest_float("x", 0, 1),
            n_trials=2, callbacks=[cb], show_progress_bar=False,
        )
        for r in fake.rows:
            assert r["duration_seconds"] is not None
            assert r["duration_seconds"] >= 0.0
