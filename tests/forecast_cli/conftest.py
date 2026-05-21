"""Shared fixtures for forecast_cli tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def fake_wandb() -> Iterator[FakeWandb]:
    yield FakeWandb()
