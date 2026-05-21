"""Tests that GIT_SHA env var threads into experiment_run inserts."""

import os
from unittest.mock import patch

from infrastructure_clickhouse.ingest import insert_experiment_run


class FakeClient:
    def __init__(self):
        self.inserts = []

    def insert_arrow(self, table, arrow_table):
        self.inserts.append((table, arrow_table.to_pandas()))


class TestGitShaCapture:
    def test_insert_experiment_run_round_trips_git_sha(self):
        from datetime import datetime, timezone

        client = FakeClient()
        insert_experiment_run(
            client,
            run_id="r1",
            created_utc=datetime(2026, 5, 21, tzinfo=timezone.utc),
            experiment_name="exp",
            area="DK1",
            model_type="lear",
            config_json="{}",
            metrics_json="{}",
            git_sha="deadbeef" * 5,  # 40-char fake sha
        )
        assert client.inserts, "expected an insert call"
        table, df = client.inserts[0]
        assert table == "algo.experiment_runs"
        assert df["git_sha"].iloc[0] == "deadbeef" * 5

    def test_insert_experiment_run_defaults_git_sha_to_empty_string(self):
        from datetime import datetime, timezone

        client = FakeClient()
        insert_experiment_run(
            client,
            run_id="r1",
            created_utc=datetime(2026, 5, 21, tzinfo=timezone.utc),
            experiment_name="exp",
            area="DK1",
            model_type="lear",
            config_json="{}",
            metrics_json="{}",
        )
        _, df = client.inserts[0]
        assert df["git_sha"].iloc[0] == ""

    def test_tracking_reads_git_sha_from_env(self):
        """track_prediction should pick up GIT_SHA from environment."""
        from forecast_cli.tracking import _resolve_git_sha

        with patch.dict(os.environ, {"GIT_SHA": "cafebabe" * 5}, clear=False):
            assert _resolve_git_sha() == "cafebabe" * 5

        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_git_sha() == ""
