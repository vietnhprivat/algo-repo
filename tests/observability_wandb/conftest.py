"""Shared fixtures for observability_wandb tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakeRun:
    project: str
    id: str
    config: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    logged: list[tuple[dict[str, Any], int | None]] = field(default_factory=list)
    finished: bool = False
    tags: list[str] = field(default_factory=list)
    artifacts_logged: list[Any] = field(default_factory=list)

    def log(self, payload: dict[str, Any], step: int | None = None) -> None:
        self.logged.append((dict(payload), step))

    def finish(self) -> None:
        self.finished = True

    def log_artifact(self, artifact: Any) -> None:
        self.artifacts_logged.append(artifact)


@dataclass
class FakeArtifact:
    name: str
    type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)

    def add_file(self, path: str, name: str | None = None) -> None:
        with open(path, "rb") as fh:
            self.files[name or path] = fh.read()


@dataclass
class FakeWandb:
    runs: list[FakeRun] = field(default_factory=list)
    init_calls: list[dict[str, Any]] = field(default_factory=list)

    def init(self, **kwargs: Any) -> FakeRun:
        self.init_calls.append(dict(kwargs))
        run = FakeRun(
            project=kwargs.get("project", ""),
            id=kwargs.get("id") or f"run-{len(self.runs)}",
            config=dict(kwargs.get("config") or {}),
            tags=list(kwargs.get("tags") or []),
        )
        self.runs.append(run)
        return run

    def Artifact(self, name: str, type: str, metadata: dict[str, Any] | None = None) -> FakeArtifact:  # noqa: N802 — mirrors wandb API
        return FakeArtifact(name=name, type=type, metadata=dict(metadata or {}))


@pytest.fixture
def fake_wandb() -> Iterator[FakeWandb]:
    yield FakeWandb()


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "dtu-thesis")
    monkeypatch.setenv("WANDB_PROJECT", "algo-research")
    monkeypatch.setenv("WANDB_MODE", "online")
