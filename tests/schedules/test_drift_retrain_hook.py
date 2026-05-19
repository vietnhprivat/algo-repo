class _StubConfig:
    def __init__(self, name, retrain_on_drift):
        self.experiment_name = name
        self.retrain_on_drift = retrain_on_drift


class TestDriftRetrainHook:
    def test_triggers_retrain_when_drift_and_flag(self, monkeypatch):
        from schedules import drift
        calls = []
        monkeypatch.setattr(
            drift, "triggered_retrain_flow",
            lambda **kw: calls.append(kw),
        )
        monkeypatch.setattr(
            drift, "_configs_for_area",
            lambda area: [_StubConfig("dk1_lear", retrain_on_drift=True)],
        )
        drift._maybe_trigger_retrain(
            area="DK1", drift_detected=True, drift_report_id="r1",
        )
        assert len(calls) == 1
        assert calls[0]["config_name"] == "dk1_lear"
        assert calls[0]["triggered_by"] == "drift"
        assert calls[0]["drift_report_id"] == "r1"
        assert calls[0]["area"] == "DK1"

    def test_no_retrain_when_drift_false(self, monkeypatch):
        from schedules import drift
        calls = []
        monkeypatch.setattr(
            drift, "triggered_retrain_flow",
            lambda **kw: calls.append(kw),
        )
        drift._maybe_trigger_retrain(
            area="DK1", drift_detected=False, drift_report_id=None,
        )
        assert calls == []

    def test_no_retrain_when_flag_false(self, monkeypatch):
        from schedules import drift
        calls = []
        monkeypatch.setattr(
            drift, "triggered_retrain_flow",
            lambda **kw: calls.append(kw),
        )
        monkeypatch.setattr(
            drift, "_configs_for_area",
            lambda area: [_StubConfig("dk1_lear", retrain_on_drift=False)],
        )
        drift._maybe_trigger_retrain(
            area="DK1", drift_detected=True, drift_report_id="r1",
        )
        assert calls == []
