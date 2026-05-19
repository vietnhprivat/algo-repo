class TestNotify:
    def test_noop_when_webhook_unset(self, monkeypatch):
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        from schedules.alerting import notify
        result = notify(subject="t", message="m", severity="info")
        assert result is None

    def test_posts_to_webhook(self, monkeypatch):
        captured = {}

        def fake_post(url, json, timeout):
            captured["url"] = url
            captured["json"] = json
            class _R:
                status_code = 200
            return _R()

        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        import requests
        monkeypatch.setattr(requests, "post", fake_post)

        from schedules.alerting import notify
        notify(subject="Drift on DK1", message="ks p=0.001", severity="warning")
        assert captured["url"] == "https://hooks.slack.com/x"
        assert "Drift on DK1" in captured["json"]["text"]
        assert ":warning:" in captured["json"]["text"]

    def test_swallow_request_exception(self, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("connection refused")

        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
        import requests
        monkeypatch.setattr(requests, "post", boom)

        from schedules.alerting import notify
        # Must not raise — log only.
        notify(subject="t", message="m", severity="error")
