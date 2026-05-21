"""Smoke: optuna_storage re-exports the W&B callback factory."""

from __future__ import annotations


def test_wandb_callback_reexport_present() -> None:
    from price_forecasting.tuning import optuna_storage

    assert hasattr(optuna_storage, "build_wandb_callback")
