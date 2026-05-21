"""Pytest configuration for schedules tests.

Activates Prefect's in-process test harness so that @flow-decorated functions
can be called directly (without a running Prefect server) in tests that need to
exercise the full flow path rather than calling `.fn(...)`.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from prefect.testing.utilities import prefect_test_harness

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture(autouse=True, scope="session")
def prefect_harness():
    with prefect_test_harness():
        yield


@pytest.fixture
def fake_wandb() -> Iterator[FakeWandb]:
    yield FakeWandb()
