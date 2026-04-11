"""Tests for the reconciliation Prefect flow and tasks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from schedules.reconciliation import (
    _ensure_utc,
    find_unreconciled_runs_task,
    reconcile_area_task,
    reconcile_predictions_flow,
)

TS1 = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
TS2 = datetime(2026, 4, 10, 13, 0, 0, tzinfo=timezone.utc)


def _make_run(run_id: str = "run-1", area: str = "DK1") -> dict:
    return {
        "run_id": run_id,
        "area": area,
        "experiment_name": "dk1_lear",
        "model_type": "lear",
        "config_json": "{}",
        "metrics_json": "{}",
        "training_duration_seconds": 5.0,
        "data_start_utc": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "data_end_utc": datetime(2026, 4, 9, tzinfo=timezone.utc),
        "model_artifact_id": None,
    }


def _make_prediction(run_id: str, ts: datetime, predicted: float = 50.0) -> dict:
    return {"run_id": run_id, "timestamp_utc": ts, "predicted": predicted, "actual": 0.0}


class TestEnsureUtc:
    def test_naive_datetime_gets_utc(self):
        naive = datetime(2026, 4, 10, 12, 0, 0)
        result = _ensure_utc(naive)
        assert result.tzinfo is not None
        assert result == datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)

    def test_utc_aware_stays_utc(self):
        aware = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
        result = _ensure_utc(aware)
        assert result == aware


class TestFindUnreconciledRunsTask:
    @patch("schedules.reconciliation.get_unreconciled_runs")
    @patch("schedules.reconciliation.create_client")
    def test_returns_runs_from_query(self, mock_create_client, mock_get_runs):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        runs = [_make_run("run-1"), _make_run("run-2")]
        mock_get_runs.return_value = runs

        result = find_unreconciled_runs_task.fn()

        mock_get_runs.assert_called_once_with(mock_client)
        assert result == runs

    @patch("schedules.reconciliation.get_unreconciled_runs")
    @patch("schedules.reconciliation.create_client")
    def test_closes_client(self, mock_create_client, mock_get_runs):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_get_runs.return_value = []

        find_unreconciled_runs_task.fn()

        mock_client.close.assert_called_once()

    @patch("schedules.reconciliation.get_unreconciled_runs")
    @patch("schedules.reconciliation.create_client")
    def test_empty_result(self, mock_create_client, mock_get_runs):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_get_runs.return_value = []

        result = find_unreconciled_runs_task.fn()

        assert result == []


class TestReconcileAreaTask:
    @patch("schedules.reconciliation.insert_experiment_run")
    @patch("schedules.reconciliation.insert_experiment_predictions")
    @patch("schedules.reconciliation.get_actual_prices_for_period")
    @patch("schedules.reconciliation.get_predictions_for_runs")
    @patch("schedules.reconciliation.create_client")
    def test_reconciles_run_with_matching_actuals(
        self,
        mock_create_client,
        mock_get_preds,
        mock_get_actuals,
        mock_insert_preds,
        mock_insert_run,
    ):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        run = _make_run("run-1", "DK1")
        preds = [
            _make_prediction("run-1", TS1, predicted=55.0),
            _make_prediction("run-1", TS2, predicted=60.0),
        ]
        actuals = [
            {"timestamp_utc": TS1, "price": 50.0},
            {"timestamp_utc": TS2, "price": 58.0},
        ]
        mock_get_preds.return_value = preds
        mock_get_actuals.return_value = actuals

        result = reconcile_area_task.fn("DK1", [run])

        assert result["reconciled"] == 1
        assert result["skipped"] == 0
        mock_insert_preds.assert_called_once()
        mock_insert_run.assert_called_once()

    @patch("schedules.reconciliation.insert_experiment_run")
    @patch("schedules.reconciliation.insert_experiment_predictions")
    @patch("schedules.reconciliation.get_actual_prices_for_period")
    @patch("schedules.reconciliation.get_predictions_for_runs")
    @patch("schedules.reconciliation.create_client")
    def test_skips_run_with_missing_actuals(
        self,
        mock_create_client,
        mock_get_preds,
        mock_get_actuals,
        mock_insert_preds,
        mock_insert_run,
    ):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        run = _make_run("run-1", "DK1")
        preds = [_make_prediction("run-1", TS1, predicted=55.0)]
        # No matching actual for TS1
        mock_get_preds.return_value = preds
        mock_get_actuals.return_value = []

        result = reconcile_area_task.fn("DK1", [run])

        assert result["skipped"] == 1
        assert result["reconciled"] == 0
        mock_insert_preds.assert_not_called()
        mock_insert_run.assert_not_called()

    @patch("schedules.reconciliation.get_predictions_for_runs")
    @patch("schedules.reconciliation.create_client")
    def test_returns_early_when_no_predictions(self, mock_create_client, mock_get_preds):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_get_preds.return_value = []

        result = reconcile_area_task.fn("DK1", [_make_run("run-1")])

        assert result == {"area": "DK1", "reconciled": 0, "skipped": 0}

    @patch("schedules.reconciliation.insert_experiment_run")
    @patch("schedules.reconciliation.insert_experiment_predictions")
    @patch("schedules.reconciliation.get_actual_prices_for_period")
    @patch("schedules.reconciliation.get_predictions_for_runs")
    @patch("schedules.reconciliation.create_client")
    def test_closes_client_on_success(
        self,
        mock_create_client,
        mock_get_preds,
        mock_get_actuals,
        mock_insert_preds,
        mock_insert_run,
    ):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        run = _make_run("run-1", "DK1")
        preds = [_make_prediction("run-1", TS1, predicted=55.0)]
        actuals = [{"timestamp_utc": TS1, "price": 50.0}]
        mock_get_preds.return_value = preds
        mock_get_actuals.return_value = actuals

        reconcile_area_task.fn("DK1", [run])

        mock_client.close.assert_called_once()

    @patch("schedules.reconciliation.insert_experiment_run")
    @patch("schedules.reconciliation.insert_experiment_predictions")
    @patch("schedules.reconciliation.get_actual_prices_for_period")
    @patch("schedules.reconciliation.get_predictions_for_runs")
    @patch("schedules.reconciliation.create_client")
    def test_metrics_inserted_with_run(
        self,
        mock_create_client,
        mock_get_preds,
        mock_get_actuals,
        mock_insert_preds,
        mock_insert_run,
    ):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        run = _make_run("run-1", "DK1")
        preds = [_make_prediction("run-1", TS1, predicted=55.0)]
        actuals = [{"timestamp_utc": TS1, "price": 50.0}]
        mock_get_preds.return_value = preds
        mock_get_actuals.return_value = actuals

        reconcile_area_task.fn("DK1", [run])

        _, kwargs = mock_insert_run.call_args
        import json

        metrics = json.loads(kwargs["metrics_json"])
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "smape" in metrics


class TestReconcilePredictionsFlow:
    @patch("schedules.reconciliation.reconcile_area_task")
    @patch("schedules.reconciliation.find_unreconciled_runs_task")
    def test_returns_early_when_no_runs(self, mock_find, mock_reconcile):
        mock_find.return_value = []

        result = reconcile_predictions_flow.fn()

        assert result == {"total_runs": 0, "areas": {}}
        mock_reconcile.assert_not_called()

    @patch("schedules.reconciliation.reconcile_area_task")
    @patch("schedules.reconciliation.find_unreconciled_runs_task")
    def test_groups_runs_by_area_and_reconciles_each(self, mock_find, mock_reconcile):
        runs = [
            _make_run("run-1", "DK1"),
            _make_run("run-2", "DK1"),
            _make_run("run-3", "NL"),
        ]
        mock_find.return_value = runs
        mock_reconcile.side_effect = [
            {"area": "DK1", "reconciled": 2, "skipped": 0},
            {"area": "NL", "reconciled": 1, "skipped": 0},
        ]

        result = reconcile_predictions_flow.fn()

        assert mock_reconcile.call_count == 2
        assert result["total_runs"] == 3
        assert result["total_reconciled"] == 3
        assert result["total_skipped"] == 0

    @patch("schedules.reconciliation.reconcile_area_task")
    @patch("schedules.reconciliation.find_unreconciled_runs_task")
    def test_counts_skipped_runs(self, mock_find, mock_reconcile):
        runs = [_make_run("run-1", "DK1"), _make_run("run-2", "DK1")]
        mock_find.return_value = runs
        mock_reconcile.return_value = {"area": "DK1", "reconciled": 1, "skipped": 1}

        result = reconcile_predictions_flow.fn()

        assert result["total_reconciled"] == 1
        assert result["total_skipped"] == 1

    @patch("schedules.reconciliation.reconcile_area_task")
    @patch("schedules.reconciliation.find_unreconciled_runs_task")
    def test_passes_correct_runs_to_area_task(self, mock_find, mock_reconcile):
        dk1_run = _make_run("run-1", "DK1")
        nl_run = _make_run("run-2", "NL")
        mock_find.return_value = [dk1_run, nl_run]
        mock_reconcile.return_value = {"area": "any", "reconciled": 1, "skipped": 0}

        reconcile_predictions_flow.fn()

        calls = mock_reconcile.call_args_list
        call_areas = {c[0][0]: c[0][1] for c in calls}
        assert call_areas["DK1"] == [dk1_run]
        assert call_areas["NL"] == [nl_run]
