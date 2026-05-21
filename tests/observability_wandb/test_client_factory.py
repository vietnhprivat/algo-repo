"""Tests for env-driven W&B settings."""

import pytest

from observability_wandb.client_factory import Settings, is_enabled, load_settings


class TestLoadSettings:
    def test_reads_all_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WANDB_API_KEY", "k123")
        monkeypatch.setenv("WANDB_ENTITY", "dtu-thesis")
        monkeypatch.setenv("WANDB_PROJECT", "algo-research")
        monkeypatch.setenv("WANDB_MODE", "online")

        settings = load_settings()

        assert settings == Settings(
            api_key="k123",
            entity="dtu-thesis",
            default_project="algo-research",
            mode="online",
        )

    def test_default_project_is_algo_research(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WANDB_PROJECT", raising=False)
        monkeypatch.setenv("WANDB_API_KEY", "k")
        monkeypatch.setenv("WANDB_ENTITY", "e")

        assert load_settings().default_project == "algo-research"

    def test_default_mode_is_disabled_when_no_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WANDB_API_KEY", raising=False)
        monkeypatch.delenv("WANDB_MODE", raising=False)

        assert load_settings().mode == "disabled"


class TestIsEnabled:
    def test_returns_false_when_mode_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WANDB_MODE", "disabled")
        monkeypatch.setenv("WANDB_API_KEY", "k")
        assert is_enabled() is False

    def test_returns_false_when_api_key_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WANDB_API_KEY", raising=False)
        monkeypatch.setenv("WANDB_MODE", "online")
        assert is_enabled() is False

    def test_returns_true_when_online_and_keyed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WANDB_API_KEY", "k")
        monkeypatch.setenv("WANDB_MODE", "online")
        monkeypatch.setenv("WANDB_ENTITY", "e")
        assert is_enabled() is True
