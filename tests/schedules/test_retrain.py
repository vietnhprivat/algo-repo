import pytest


class TestTriggeredRetrainFlow:
    def test_records_event_on_success(self, monkeypatch):
        from schedules import retrain
        captured = []
        monkeypatch.setattr(retrain, "_insert_retrain_event", lambda **kw: captured.append(kw))
        monkeypatch.setattr(retrain, "daily_forecast_flow", lambda **kw: {"run_id": "run-abc"})

        result = retrain.triggered_retrain_flow(
            config_name="dk1_lear", triggered_by="drift",
            drift_report_id="r1", area="DK1",
        )
        assert result["status"] == "completed"
        assert result["new_run_id"] == "run-abc"
        # Two rows recorded: status=running, then status=completed
        statuses = [c["status"] for c in captured]
        assert statuses == ["running", "completed"]
        assert captured[-1]["triggered_by"] == "drift"
        assert captured[-1]["drift_report_id"] == "r1"
        assert captured[-1]["new_run_id"] == "run-abc"
        # created_utc is immutable; updated_utc must be strictly increasing
        # so ReplacingMergeTree keeps the terminal row.
        assert captured[0]["created_utc"] == captured[-1]["created_utc"]
        assert captured[-1]["updated_utc"] > captured[0]["updated_utc"]

    def test_records_failed_event_when_forecast_raises(self, monkeypatch):
        from schedules import retrain
        captured = []
        monkeypatch.setattr(retrain, "_insert_retrain_event", lambda **kw: captured.append(kw))

        def fail(**kw):
            raise RuntimeError("forecast failed")

        monkeypatch.setattr(retrain, "daily_forecast_flow", fail)

        with pytest.raises(RuntimeError, match="forecast failed"):
            retrain.triggered_retrain_flow(
                config_name="dk1_lear", triggered_by="drift",
                drift_report_id="r1", area="DK1",
            )
        statuses = [c["status"] for c in captured]
        assert statuses == ["running", "failed"]
        assert "forecast failed" in (captured[-1]["notes"] or "")
        assert captured[0]["created_utc"] == captured[-1]["created_utc"]
        assert captured[-1]["updated_utc"] > captured[0]["updated_utc"]
