class TestAccuracyAlert:
    def test_alert_triggered_when_today_mae_exceeds_threshold(self, monkeypatch):
        from schedules import reconciliation
        captured = {}
        monkeypatch.setattr(reconciliation, "notify", lambda **kw: captured.update(kw))
        reconciliation._maybe_alert_accuracy_degradation(
            area="DK1", config_name="dk1_lear",
            today_mae=15.0, baseline_median_mae=8.0, threshold_multiplier=1.5,
        )
        assert "Accuracy degradation" in captured["subject"]
        assert "DK1" in captured["subject"]
        assert captured["severity"] == "warning"

    def test_no_alert_when_within_threshold(self, monkeypatch):
        from schedules import reconciliation
        captured = {}
        monkeypatch.setattr(reconciliation, "notify", lambda **kw: captured.update(kw))
        reconciliation._maybe_alert_accuracy_degradation(
            area="DK1", config_name="dk1_lear",
            today_mae=10.0, baseline_median_mae=8.0, threshold_multiplier=1.5,
        )
        assert captured == {}

    def test_no_alert_when_baseline_missing(self, monkeypatch):
        from schedules import reconciliation
        captured = {}
        monkeypatch.setattr(reconciliation, "notify", lambda **kw: captured.update(kw))
        reconciliation._maybe_alert_accuracy_degradation(
            area="DK1", config_name="dk1_lear",
            today_mae=100.0, baseline_median_mae=None, threshold_multiplier=1.5,
        )
        assert captured == {}

    def test_no_alert_when_baseline_zero(self, monkeypatch):
        from schedules import reconciliation
        captured = {}
        monkeypatch.setattr(reconciliation, "notify", lambda **kw: captured.update(kw))
        reconciliation._maybe_alert_accuracy_degradation(
            area="DK1", config_name="dk1_lear",
            today_mae=100.0, baseline_median_mae=0.0, threshold_multiplier=1.5,
        )
        assert captured == {}
