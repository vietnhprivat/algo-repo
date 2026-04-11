"""Tests for shared logging bootstrap."""

import logging
import sys
import types

from infrastructure_clickhouse.logging_setup import (
    build_log_extra,
    configure_logging,
    get_logger,
)


class FakeLokiHandler(logging.Handler):
    def __init__(self, **kwargs):
        super().__init__()
        self.url = kwargs["url"]
        self.tags = kwargs["tags"]
        self.version = kwargs["version"]


class TestLoggingSetup:
    def setup_method(self):
        self.root_logger = logging.getLogger()
        self._remove_algo_handlers()

    def teardown_method(self):
        self._remove_algo_handlers()
        sys.modules.pop("logging_loki", None)

    def _remove_algo_handlers(self):
        for handler in list(self.root_logger.handlers):
            if handler.get_name() in {"algo-console", "algo-loki"}:
                self.root_logger.removeHandler(handler)

    def test_configure_logging_console_only(self, monkeypatch):
        monkeypatch.delenv("LOKI_URL", raising=False)

        root_logger = configure_logging()

        handler_names = [handler.get_name() for handler in root_logger.handlers]
        assert "algo-console" in handler_names
        assert "algo-loki" not in handler_names

    def test_configure_logging_with_loki_handler(self, monkeypatch):
        monkeypatch.setitem(
            sys.modules,
            "logging_loki",
            types.SimpleNamespace(LokiHandler=FakeLokiHandler),
        )

        root_logger = configure_logging(loki_url="http://loki:3100")

        loki_handler = next(
            handler
            for handler in root_logger.handlers
            if handler.get_name() == "algo-loki"
        )
        assert loki_handler.url == "http://loki:3100/loki/api/v1/push"
        assert loki_handler.tags["job"] == "algo-repo"
        assert loki_handler.version == "1"

    def test_get_logger_is_idempotent_and_preserves_context(self, monkeypatch, caplog):
        monkeypatch.setitem(
            sys.modules,
            "logging_loki",
            types.SimpleNamespace(LokiHandler=FakeLokiHandler),
        )

        logger_a = get_logger("tests.logger_a", service="service-a")
        logger_b = get_logger("tests.logger_b", service="service-b")

        handler_names = [
            handler.get_name()
            for handler in logging.getLogger().handlers
            if handler.get_name() in {"algo-console", "algo-loki"}
        ]
        assert handler_names.count("algo-console") == 1
        assert handler_names.count("algo-loki") == 0
        assert build_log_extra(area="DK1", run_id=None, target_date="") == {"area": "DK1"}

        with caplog.at_level(logging.INFO):
            logger_a.info("hello", extra=build_log_extra(area="DK1"))
            logger_b.info("world", extra=build_log_extra(config_name="dk1_lear"))

        assert caplog.records[0].service == "service-a"
        assert caplog.records[0].area == "DK1"
        assert caplog.records[0].tags["service"] == "service-a"
        assert caplog.records[0].tags["area"] == "DK1"
        assert caplog.records[1].service == "service-b"
        assert caplog.records[1].config_name == "dk1_lear"
