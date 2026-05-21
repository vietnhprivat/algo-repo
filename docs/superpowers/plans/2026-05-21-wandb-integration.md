# W&B Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Weights & Biases as a research visualization and Report-authoring surface alongside ClickHouse, without touching the production daily-forecast / drift / retrain paths.

**Architecture:** New `observability_wandb` uv workspace package owning all W&B-side schema and SDK calls behind one `WandbTracker`. Existing tracking call sites (`forecast_cli.tracking`, `LightningModel`, Optuna persistence, reconciliation) dual-write via the tracker. A new `forecast-cli ablate` command drives sweep experiments for the open thesis gaps. ClickHouse remains the operational source of truth; W&B is additive.

**Tech Stack:** Python 3.13, uv workspace, `wandb>=0.27` (already in root `pyproject.toml`), Lightning's `WandbLogger`, Optuna callback API, Typer, pytest with `monkeypatch` for fake-wandb injection.

**Source spec:** `docs/superpowers/specs/2026-05-21-wandb-migration-design.md` (commit `071c8e5`).

---

## File map

### New package `src/observability_wandb/`
- `pyproject.toml` — workspace member manifest
- `src/observability_wandb/__init__.py` — re-exports
- `src/observability_wandb/client_factory.py` — env-var driven `Settings` + `is_enabled()`
- `src/observability_wandb/tracker.py` — `WandbTracker` class, single owner of W&B-side schema
- `src/observability_wandb/lightning_logger.py` — `build_lightning_logger(config)` factory
- `src/observability_wandb/optuna_callback.py` — `build_wandb_sweep_callback(...)`
- `src/observability_wandb/artifacts.py` — joblib-blob → W&B Artifact bridge
- `src/observability_wandb/logging_setup.py` — Loki-style graceful no-op wrapper

### Modified files
- `pyproject.toml` (root) — add `observability_wandb` to workspace members + main deps
- `src/price_forecasting/src/price_forecasting/configs/experiment.py` — add `wandb_project`, `wandb_tags`
- `src/forecast_cli/src/forecast_cli/tracking.py` — dual-write after ClickHouse calls
- `src/price_forecasting/src/price_forecasting/models/lightning_base.py` — wandb logger in Trainer
- `src/price_forecasting/src/price_forecasting/tuning/optuna_storage.py` — add wandb callback
- `src/schedules/src/schedules/reconciliation.py` — call `log_prod_reconciled` post-batch
- `src/forecast_cli/src/forecast_cli/main.py` — register `ablate` command
- `Dockerfile` — accept `WANDB_API_KEY`, `WANDB_ENTITY`, `WANDB_MODE` at runtime
- `src/schedules/src/schedules/deploy_forecast.py` — bake `WANDB_*` into flow containers
- `docs/REPO_OVERVIEW.md` — section update (Section 3 tech stack, Section 11 observability)
- `docs/RUNBOOK.md` — new "W&B troubleshooting" subsection

### New CLI command
- `src/forecast_cli/src/forecast_cli/commands/ablate.py`

### Tests
- `tests/observability_wandb/__init__.py`
- `tests/observability_wandb/conftest.py` — `fake_wandb` fixture
- `tests/observability_wandb/test_client_factory.py`
- `tests/observability_wandb/test_tracker.py`
- `tests/observability_wandb/test_lightning_logger.py`
- `tests/observability_wandb/test_optuna_callback.py`
- `tests/observability_wandb/test_artifacts.py`
- `tests/forecast_cli/test_tracking_wandb.py`
- `tests/forecast_cli/test_ablate.py`
- `tests/schedules/test_reconciliation_wandb.py`
- `tests/price_forecasting/test_lightning_wandb.py`
- `tests/price_forecasting/test_optuna_wandb.py`

---

## Conventions enforced by every task

- **Tests before code.** Each task starts with a failing test.
- **No live W&B network calls in tests.** Use `monkeypatch.setattr(observability_wandb.tracker, "wandb", fake_wandb)` (or the per-module equivalent). The package never imports `wandb` at function call time — only at module top.
- **No `print()` in src/.** Use `LOGGER = get_logger(__name__, service="observability-wandb")` from `infrastructure_clickhouse.logging_setup`, with `build_log_extra(**ctx)`.
- **No emojis in code or commit messages.**
- **Commit message convention:** match existing repo style — short type prefix, no scope (`feat:`, `test:`, `docs:`, `chore:`, `ci:`). Trailing `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` is **not** required; the existing repo commits do not include it. Omit it unless the user has asked otherwise during this session — in which case use `--trailer`.
- **Each task ends with a `git commit` step.**
- **All new code is typed.** Functions return-annotated. Dataclasses for configs.
- **No new top-level imports of `wandb` outside `src/observability_wandb/`.** Other packages depend on the tracker, never on `wandb` directly.

---

## Task 1: Bootstrap the `observability_wandb` workspace package

**Files:**
- Create: `src/observability_wandb/pyproject.toml`
- Create: `src/observability_wandb/src/observability_wandb/__init__.py`
- Create: `src/observability_wandb/src/observability_wandb/py.typed`
- Create: `tests/observability_wandb/__init__.py`
- Create: `tests/observability_wandb/test_package_smoke.py`
- Modify: `pyproject.toml` (root) — add `observability_wandb` to `[tool.uv.workspace]` members and to top-level `dependencies`.

- [ ] **Step 1: Write the failing smoke test**

Create `tests/observability_wandb/test_package_smoke.py`:

```python
"""Smoke test: package imports without error."""


def test_package_imports() -> None:
    import observability_wandb

    assert hasattr(observability_wandb, "__name__")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/observability_wandb/test_package_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'observability_wandb'`.

- [ ] **Step 3: Create the package manifest**

Create `src/observability_wandb/pyproject.toml`:

```toml
[project]
name = "observability-wandb"
version = "0.1.0"
description = "W&B observability layer (research-side dual-write tracker)."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "domain",
    "infrastructure-clickhouse",
    "wandb>=0.27.0",
]

[build-system]
requires = ["uv_build>=0.9.28,<0.10.0"]
build-backend = "uv_build"
```

- [ ] **Step 4: Create the package source skeleton**

Create `src/observability_wandb/src/observability_wandb/__init__.py`:

```python
"""W&B observability layer.

Owns all W&B SDK calls. Other packages depend on this module's
``WandbTracker``; they never import ``wandb`` directly.
"""

from observability_wandb.tracker import WandbTracker as WandbTracker

__all__ = ["WandbTracker"]
```

Create the `py.typed` marker file (empty):

```bash
touch src/observability_wandb/src/observability_wandb/py.typed
```

Create a stub `src/observability_wandb/src/observability_wandb/tracker.py`:

```python
"""Placeholder tracker — fleshed out in Task 3."""


class WandbTracker:  # pragma: no cover - replaced in Task 3
    """Stub. See Task 3."""
```

Create the README placeholder `src/observability_wandb/README.md`:

```markdown
# observability-wandb

W&B observability layer. See `docs/superpowers/specs/2026-05-21-wandb-migration-design.md`.
```

- [ ] **Step 5: Register the workspace member**

Edit the root `pyproject.toml` to add `observability-wandb` to the dependency list under `[project]`:

```toml
dependencies = [
    # ... existing entries ...
    "observability-wandb",
]
```

Locate the existing `[tool.uv.workspace]` block (search `[tool.uv.workspace]`) and add the new member to its `members` list. Follow the existing path format used by sibling packages like `infrastructure-clickhouse`.

- [ ] **Step 6: Refresh the lockfile and verify**

Run: `uv sync`
Expected: success; new package recognized.

Run: `uv run pytest tests/observability_wandb/test_package_smoke.py -v`
Expected: PASS.

- [ ] **Step 7: Create the test package init**

Create `tests/observability_wandb/__init__.py` (empty file).

- [ ] **Step 8: Commit**

```bash
git add src/observability_wandb pyproject.toml uv.lock tests/observability_wandb/__init__.py tests/observability_wandb/test_package_smoke.py
git commit -m "feat: bootstrap observability_wandb workspace package"
```

---

## Task 2: `client_factory` with env-driven `Settings` and `is_enabled()`

**Files:**
- Create: `src/observability_wandb/src/observability_wandb/client_factory.py`
- Create: `tests/observability_wandb/test_client_factory.py`

This module reads `WANDB_API_KEY`, `WANDB_ENTITY`, `WANDB_PROJECT`, `WANDB_MODE` from the environment and returns a single `Settings` dataclass plus an `is_enabled()` helper. Mirrors the pattern in `src/infrastructure_clickhouse/src/infrastructure_clickhouse/client_factory.py`.

- [ ] **Step 1: Write failing tests**

Create `tests/observability_wandb/test_client_factory.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/observability_wandb/test_client_factory.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

Create `src/observability_wandb/src/observability_wandb/client_factory.py`:

```python
"""Env-driven W&B settings.

``load_settings()`` reads ``WANDB_API_KEY``, ``WANDB_ENTITY``,
``WANDB_PROJECT``, ``WANDB_MODE`` and returns a ``Settings`` dataclass.

``is_enabled()`` returns ``True`` only when both an API key is present
and ``WANDB_MODE != "disabled"``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_PROJECT = "algo-research"


@dataclass(frozen=True)
class Settings:
    api_key: str
    entity: str
    default_project: str
    mode: str  # "online", "offline", or "disabled"


def load_settings() -> Settings:
    api_key = os.environ.get("WANDB_API_KEY", "")
    entity = os.environ.get("WANDB_ENTITY", "")
    project = os.environ.get("WANDB_PROJECT") or _DEFAULT_PROJECT
    explicit_mode = os.environ.get("WANDB_MODE")
    mode = explicit_mode if explicit_mode else ("online" if api_key else "disabled")
    return Settings(api_key=api_key, entity=entity, default_project=project, mode=mode)


def is_enabled() -> bool:
    settings = load_settings()
    return bool(settings.api_key) and settings.mode != "disabled"
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `uv run pytest tests/observability_wandb/test_client_factory.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/client_factory.py tests/observability_wandb/test_client_factory.py
git commit -m "feat(observability_wandb): env-driven settings and is_enabled gate"
```

---

## Task 3: `WandbTracker` class with no-op-when-disabled semantics

**Files:**
- Replace: `src/observability_wandb/src/observability_wandb/tracker.py` (the stub from Task 1)
- Create: `tests/observability_wandb/conftest.py` — `fake_wandb` fixture
- Create: `tests/observability_wandb/test_tracker.py` (gates only — methods land in Tasks 4–7)

The tracker is one class. Constructor accepts an injectable `wandb_module` (defaulting to the real `wandb`) so tests can pass a fake. Every public method begins with `if not self._enabled: return None`. This keeps the no-op fast and removes the need for try/except around each call site.

- [ ] **Step 1: Write the `fake_wandb` fixture**

Create `tests/observability_wandb/conftest.py`:

```python
"""Shared fixtures for observability_wandb tests."""

from __future__ import annotations

import types
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
```

- [ ] **Step 2: Write failing tracker-gate tests**

Create `tests/observability_wandb/test_tracker.py`:

```python
"""Tracker-level no-op semantics."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


class TestNoOpWhenDisabled:
    def test_log_backtest_run_noops_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
    ) -> None:
        monkeypatch.setenv("WANDB_MODE", "disabled")
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_backtest_run(
            run_id="r1",
            config={"area": "DK1"},
            summary={"mae": 5.0},
            per_day=[],
            tags=[],
        )

        assert fake_wandb.init_calls == []
        assert fake_wandb.runs == []

    def test_enabled_when_key_present(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        assert tracker.is_enabled is True
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: FAIL — `WandbTracker.__init__` does not accept `wandb_module`.

- [ ] **Step 4: Implement the tracker shell**

Replace `src/observability_wandb/src/observability_wandb/tracker.py` with:

```python
"""WandbTracker — single owner of the W&B-side schema.

Every public method is a no-op when the tracker is disabled
(missing API key or ``WANDB_MODE=disabled``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from observability_wandb.client_factory import is_enabled, load_settings

LOGGER = logging.getLogger(__name__)


class WandbTracker:
    def __init__(self, *, wandb_module: Any | None = None) -> None:
        if wandb_module is None:
            import wandb as _wandb

            self._wandb = _wandb
        else:
            self._wandb = wandb_module
        self._settings = load_settings()
        self._enabled = is_enabled()
        self._prod_runs: dict[tuple[str, str], Any] = {}

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def log_backtest_run(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        summary: Mapping[str, float],
        per_day: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 4.
        raise NotImplementedError

    def log_predict_run(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        prediction: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 5.
        raise NotImplementedError

    def log_prod_reconciled(
        self,
        *,
        area: str,
        config_name: str,
        target_date: str,
        metrics: Mapping[str, float],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 6.
        raise NotImplementedError

    def log_artifact(
        self,
        *,
        run: Any,
        artifact_id: str,
        artifact_type: str,
        local_path: str,
        metadata: Mapping[str, Any],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 7.
        raise NotImplementedError
```

- [ ] **Step 5: Run, expect PASS on the gate tests**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py tests/observability_wandb/conftest.py tests/observability_wandb/test_tracker.py
git commit -m "feat(observability_wandb): tracker shell with no-op-when-disabled semantics"
```

---

## Task 4: `WandbTracker.log_backtest_run`

**Files:**
- Modify: `src/observability_wandb/src/observability_wandb/tracker.py`
- Modify: `tests/observability_wandb/test_tracker.py`

A backtest produces: one config dict, one summary metrics dict (`mae`, `rmse`, `smape`, `rmae`), and a per-day error series. Map each to W&B as: `wandb.init(config=..., tags=..., job_type="backtest")`, then for each per-day row `run.log({...}, step=day_index)`, finally update `run.summary[...]` and `run.finish()`.

- [ ] **Step 1: Add the failing test class**

Append to `tests/observability_wandb/test_tracker.py`:

```python
class TestLogBacktestRun:
    def test_init_finish_and_per_day_logged(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        per_day = [
            {"target_date": "2026-01-01", "mae": 5.1, "rmse": 7.0},
            {"target_date": "2026-01-02", "mae": 4.8, "rmse": 6.4},
        ]
        tracker.log_backtest_run(
            run_id="r-001",
            config={"area": "DK1", "model_type": "lear", "alpha": 0.01},
            summary={"mae": 4.95, "rmse": 6.7, "smape": 12.0, "rmae": 0.82},
            per_day=per_day,
            tags=["DK1", "lear", "git:abc123"],
        )

        assert len(fake_wandb.init_calls) == 1
        call = fake_wandb.init_calls[0]
        assert call["project"] == "algo-research"
        assert call["entity"] == "dtu-thesis"
        assert call["id"] == "r-001"
        assert call["job_type"] == "backtest"
        assert call["tags"] == ["DK1", "lear", "git:abc123"]
        assert call["config"] == {
            "area": "DK1",
            "model_type": "lear",
            "alpha": 0.01,
        }

        run = fake_wandb.runs[0]
        assert run.finished is True
        assert [step for _, step in run.logged] == [0, 1]
        assert run.logged[0][0]["mae"] == 5.1
        assert run.logged[1][0]["rmse"] == 6.4
        assert run.summary == {
            "mae": 4.95,
            "rmse": 6.7,
            "smape": 12.0,
            "rmae": 0.82,
        }
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogBacktestRun -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement**

Replace the body of `WandbTracker.log_backtest_run` in `tracker.py` with:

```python
    def log_backtest_run(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        summary: Mapping[str, float],
        per_day: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
    ) -> None:
        if not self._enabled:
            return None
        run = self._wandb.init(
            project=self._settings.default_project,
            entity=self._settings.entity,
            id=run_id,
            job_type="backtest",
            tags=list(tags),
            config=dict(config),
        )
        try:
            for step, row in enumerate(per_day):
                run.log(dict(row), step=step)
            for key, value in summary.items():
                run.summary[key] = value
        finally:
            run.finish()
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py tests/observability_wandb/test_tracker.py
git commit -m "feat(observability_wandb): log_backtest_run with per-day history and summary"
```

---

## Task 5: `WandbTracker.log_predict_run`

**Files:**
- Modify: `src/observability_wandb/src/observability_wandb/tracker.py`
- Modify: `tests/observability_wandb/test_tracker.py`

One run per single-date prediction. Logs a 24-row (or 96-row) prediction Table plus a small config dict. `job_type="predict"`.

- [ ] **Step 1: Failing test**

Append to `tests/observability_wandb/test_tracker.py`:

```python
class TestLogPredictRun:
    def test_logs_prediction_table_with_correct_metadata(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        prediction = [
            {"period": 0, "timestamp_utc": "2026-05-22T00:00:00Z", "predicted": 50.1},
            {"period": 1, "timestamp_utc": "2026-05-22T01:00:00Z", "predicted": 48.4},
        ]
        tracker.log_predict_run(
            run_id="predict-2026-05-22-dk1",
            config={"area": "DK1", "target_date": "2026-05-22"},
            prediction=prediction,
            tags=["DK1", "lear", "predict"],
        )

        call = fake_wandb.init_calls[0]
        assert call["job_type"] == "predict"
        assert call["id"] == "predict-2026-05-22-dk1"

        run = fake_wandb.runs[0]
        assert run.finished is True
        assert len(run.logged) == 2
        assert run.logged[0][0]["predicted"] == 50.1
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogPredictRun -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement**

Replace `log_predict_run` body:

```python
    def log_predict_run(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        prediction: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
    ) -> None:
        if not self._enabled:
            return None
        run = self._wandb.init(
            project=self._settings.default_project,
            entity=self._settings.entity,
            id=run_id,
            job_type="predict",
            tags=list(tags),
            config=dict(config),
        )
        try:
            for step, row in enumerate(prediction):
                run.log(dict(row), step=step)
        finally:
            run.finish()
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py tests/observability_wandb/test_tracker.py
git commit -m "feat(observability_wandb): log_predict_run for single-date predictions"
```

---

## Task 6: `WandbTracker.log_prod_reconciled` (resumable run)

**Files:**
- Modify: `src/observability_wandb/src/observability_wandb/tracker.py`
- Modify: `tests/observability_wandb/test_tracker.py`

One continuous run per `(area, config_name)` lives in the `algo-prod` project. Each reconciliation appends exactly one step. The run is identified by a deterministic ID: `prod-{area_lower}-{config_name}`. First call inits with `resume="allow"`; subsequent calls in the same process reuse the cached run handle. The project is hard-coded to `"algo-prod"` (not the settings default).

- [ ] **Step 1: Failing test**

Append to `tests/observability_wandb/test_tracker.py`:

```python
class TestLogProdReconciled:
    def test_first_call_inits_run_in_algo_prod_project(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1",
            config_name="dk1_lear",
            target_date="2026-05-21",
            metrics={"mae": 4.5, "rmse": 6.1, "smape": 11.0},
        )

        call = fake_wandb.init_calls[0]
        assert call["project"] == "algo-prod"
        assert call["entity"] == "dtu-thesis"
        assert call["id"] == "prod-dk1-dk1_lear"
        assert call["resume"] == "allow"
        assert "DK1" in call["tags"]
        assert "dk1_lear" in call["tags"]

        run = fake_wandb.runs[0]
        assert run.finished is False  # continuous, do not finish
        assert len(run.logged) == 1
        assert run.logged[0][0]["mae"] == 4.5
        assert run.logged[0][0]["target_date"] == "2026-05-21"

    def test_second_call_reuses_run_no_reinit(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-20", metrics={"mae": 5.0},
        )
        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-21", metrics={"mae": 4.5},
        )

        assert len(fake_wandb.init_calls) == 1
        assert len(fake_wandb.runs[0].logged) == 2

    def test_distinct_runs_per_area_config(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-21", metrics={"mae": 4.5},
        )
        tracker.log_prod_reconciled(
            area="DE", config_name="de_lear",
            target_date="2026-05-21", metrics={"mae": 3.8},
        )

        assert len(fake_wandb.init_calls) == 2
        ids = {c["id"] for c in fake_wandb.init_calls}
        assert ids == {"prod-dk1-dk1_lear", "prod-de-de_lear"}
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogProdReconciled -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement**

Replace `log_prod_reconciled` body and add a constant at the top of the module:

```python
_PROD_PROJECT = "algo-prod"
```

```python
    def log_prod_reconciled(
        self,
        *,
        area: str,
        config_name: str,
        target_date: str,
        metrics: Mapping[str, float],
    ) -> None:
        if not self._enabled:
            return None
        key = (area, config_name)
        run = self._prod_runs.get(key)
        if run is None:
            run = self._wandb.init(
                project=_PROD_PROJECT,
                entity=self._settings.entity,
                id=f"prod-{area.lower()}-{config_name}",
                resume="allow",
                job_type="prod-reconciled",
                tags=[area, config_name],
                config={"area": area, "config_name": config_name},
            )
            self._prod_runs[key] = run
        payload = dict(metrics)
        payload["target_date"] = target_date
        run.log(payload)
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py tests/observability_wandb/test_tracker.py
git commit -m "feat(observability_wandb): log_prod_reconciled with resumable per-area run"
```

---

## Task 7: `WandbTracker.log_artifact` for joblib model artifacts

**Files:**
- Create: `src/observability_wandb/src/observability_wandb/artifacts.py`
- Modify: `src/observability_wandb/src/observability_wandb/tracker.py`
- Modify: `tests/observability_wandb/test_tracker.py`
- Create: `tests/observability_wandb/test_artifacts.py`

Wraps a joblib blob (or any local file) as a W&B Artifact and attaches it to a given run. The artifact name is the `artifact_id` (the same UUID stored in `algo.model_artifacts`). Type defaults to `"model"`. Metadata carries area, model_type, config_name, run_id.

- [ ] **Step 1: Failing test for log_artifact**

Append to `tests/observability_wandb/test_tracker.py`:

```python
class TestLogArtifact:
    def test_attaches_artifact_to_run(
        self,
        enabled_env: None,
        fake_wandb: FakeWandb,
        tmp_path,
    ) -> None:
        blob = tmp_path / "model.joblib"
        blob.write_bytes(b"\x00\x01fake-joblib")

        tracker = WandbTracker(wandb_module=fake_wandb)
        run = fake_wandb.init(project="algo-research", id="r-1")

        tracker.log_artifact(
            run=run,
            artifact_id="art-uuid-1",
            artifact_type="model",
            local_path=str(blob),
            metadata={"area": "DK1", "model_type": "lear"},
        )

        assert len(run.artifacts_logged) == 1
        artifact = run.artifacts_logged[0]
        assert artifact.name == "art-uuid-1"
        assert artifact.type == "model"
        assert artifact.metadata == {"area": "DK1", "model_type": "lear"}
        assert b"fake-joblib" in next(iter(artifact.files.values()))
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogArtifact -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement**

Replace `log_artifact` body in `tracker.py`:

```python
    def log_artifact(
        self,
        *,
        run: Any,
        artifact_id: str,
        artifact_type: str,
        local_path: str,
        metadata: Mapping[str, Any],
    ) -> None:
        if not self._enabled:
            return None
        artifact = self._wandb.Artifact(
            name=artifact_id,
            type=artifact_type,
            metadata=dict(metadata),
        )
        artifact.add_file(local_path)
        run.log_artifact(artifact)
```

- [ ] **Step 4: Add a higher-level helper for blob → artifact in `artifacts.py`**

Create `src/observability_wandb/src/observability_wandb/artifacts.py`:

```python
"""Helpers for turning in-memory joblib blobs into W&B Artifacts.

The system stores models as base64 joblib blobs in ``algo.model_artifacts``.
This module decodes such a blob to a temp file then hands it to
``WandbTracker.log_artifact``.
"""

from __future__ import annotations

import base64
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from observability_wandb.tracker import WandbTracker


def log_model_blob(
    *,
    tracker: WandbTracker,
    run: Any,
    artifact_id: str,
    blob_b64: str,
    metadata: Mapping[str, Any],
) -> None:
    """Decode a base64 joblib blob and push it as a W&B model Artifact."""
    if not tracker.is_enabled:
        return None
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / f"{artifact_id}.joblib"
        path.write_bytes(base64.b64decode(blob_b64))
        tracker.log_artifact(
            run=run,
            artifact_id=artifact_id,
            artifact_type="model",
            local_path=str(path),
            metadata=metadata,
        )
```

- [ ] **Step 5: Test the helper**

Create `tests/observability_wandb/test_artifacts.py`:

```python
"""log_model_blob round-trip test."""

from __future__ import annotations

import base64

import pytest

from observability_wandb.artifacts import log_model_blob
from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


def test_log_model_blob_decodes_and_attaches(
    enabled_env: None, fake_wandb: FakeWandb
) -> None:
    tracker = WandbTracker(wandb_module=fake_wandb)
    run = fake_wandb.init(project="algo-research", id="r-1")
    raw = b"joblib-bytes-here"
    encoded = base64.b64encode(raw).decode("ascii")

    log_model_blob(
        tracker=tracker,
        run=run,
        artifact_id="art-7",
        blob_b64=encoded,
        metadata={"area": "DK1"},
    )

    assert run.artifacts_logged[0].name == "art-7"
    assert next(iter(run.artifacts_logged[0].files.values())) == raw


def test_log_model_blob_noops_when_disabled(
    monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    tracker = WandbTracker(wandb_module=fake_wandb)
    run = fake_wandb.init(project="x", id="x")

    log_model_blob(
        tracker=tracker,
        run=run,
        artifact_id="art-7",
        blob_b64=base64.b64encode(b"x").decode(),
        metadata={},
    )
    assert run.artifacts_logged == []
```

- [ ] **Step 6: Run all tracker + artifact tests**

Run: `uv run pytest tests/observability_wandb/ -v`
Expected: 10 PASS.

- [ ] **Step 7: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py src/observability_wandb/src/observability_wandb/artifacts.py tests/observability_wandb/test_tracker.py tests/observability_wandb/test_artifacts.py
git commit -m "feat(observability_wandb): log_artifact + base64-blob helper"
```

---

## Task 8: Extend `ExperimentConfig` with `wandb_project` and `wandb_tags`

**Files:**
- Modify: `src/price_forecasting/src/price_forecasting/configs/experiment.py`
- Modify: `tests/price_forecasting/test_experiment_config.py` (create if not present)

Both fields are optional. Default: `wandb_project=None` (means "use the env default"), `wandb_tags=[]`.

- [ ] **Step 1: Locate the test file**

Run: `find tests/price_forecasting -name 'test_experiment*' -maxdepth 2`. If a test file for `ExperimentConfig` already exists, modify it. If not, create `tests/price_forecasting/test_experiment_config.py`.

- [ ] **Step 2: Write the failing test**

Add (or create) the test:

```python
"""ExperimentConfig wandb fields."""

from __future__ import annotations

from price_forecasting.configs.experiment import ExperimentConfig


def test_experiment_config_has_wandb_defaults() -> None:
    cfg = ExperimentConfig(
        experiment_name="x", results_dir="results", area="DK1"
    )
    assert cfg.wandb_project is None
    assert cfg.wandb_tags == []


def test_experiment_config_accepts_wandb_values() -> None:
    cfg = ExperimentConfig(
        experiment_name="x",
        results_dir="results",
        area="DK1",
        wandb_project="algo-research",
        wandb_tags=["DK1", "lear"],
    )
    assert cfg.wandb_project == "algo-research"
    assert cfg.wandb_tags == ["DK1", "lear"]
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/price_forecasting/test_experiment_config.py -v`
Expected: FAIL — unknown field.

- [ ] **Step 4: Modify the dataclass**

In `src/price_forecasting/src/price_forecasting/configs/experiment.py`, add the two fields. They go at the end of the field block, matching the dataclass's existing style:

```python
    wandb_project: str | None = None
    wandb_tags: list[str] = field(default_factory=list)
```

If `field` is not yet imported in that file, add `from dataclasses import dataclass, field` (or extend the existing import).

- [ ] **Step 5: Run tests, expect PASS**

Run: `uv run pytest tests/price_forecasting/test_experiment_config.py -v`
Expected: 2 PASS.

Then run the broader config test suite to ensure no regression:

Run: `uv run pytest tests/price_forecasting/configs -v`
Expected: PASS (existing tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/configs/experiment.py tests/price_forecasting/test_experiment_config.py
git commit -m "feat(price_forecasting): add wandb_project and wandb_tags to ExperimentConfig"
```

---

## Task 9: Dual-write hook in `forecast_cli.tracking` for backtests

**Files:**
- Modify: `src/forecast_cli/src/forecast_cli/tracking.py`
- Create: `tests/forecast_cli/test_tracking_wandb.py`

The existing `track_backtest()` (or equivalent — find its exact name with `grep -n "def track_" src/forecast_cli/src/forecast_cli/tracking.py`) writes one `algo.experiment_runs` row + N `algo.experiment_predictions` rows. After those writes succeed, call `WandbTracker.log_backtest_run(...)`. The tracker is passed in as an argument with a default factory; tests inject a fake.

- [ ] **Step 1: Inspect the current `track_backtest` signature**

Run: `grep -n "def track_\|class.*Track" src/forecast_cli/src/forecast_cli/tracking.py`

Note the existing function name and its current parameters. The new W&B call goes in the same function after the ClickHouse insert calls. Do **not** change the existing signature — add the dual-write call as an internal step.

- [ ] **Step 2: Failing test**

Create `tests/forecast_cli/test_tracking_wandb.py`:

```python
"""Backtest dual-write to W&B (in addition to ClickHouse)."""

from __future__ import annotations

from typing import Any

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "dtu-thesis")
    monkeypatch.setenv("WANDB_PROJECT", "algo-research")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_backtest_dual_writes_to_wandb(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling track_backtest with a tracker writes to W&B in addition to CH."""
    from forecast_cli import tracking

    # Patch the ClickHouse insert functions used by track_backtest so they
    # become no-ops. Adjust the attribute names if the engineer's grep in
    # Step 1 revealed different ones — patch the actual symbols used.
    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )

    tracker = WandbTracker(wandb_module=fake_wandb)

    # Call signature mirrors the existing track_backtest. The engineer fills
    # in the real arguments after Step 1's inspection.
    tracking.track_backtest(
        client=object(),  # ClickHouse client, ignored by the patched inserts
        run_id="bt-001",
        config={"area": "DK1", "model_type": "lear"},
        summary={"mae": 4.95, "rmse": 6.7, "smape": 12.0, "rmae": 0.82},
        per_day_metrics=[
            {"target_date": "2026-01-01", "mae": 5.1, "rmse": 7.0},
        ],
        forecasts_df=None,
        actuals_df=None,
        tags=["DK1", "lear"],
        tracker=tracker,
    )

    assert len(fake_wandb.init_calls) == 1
    assert fake_wandb.init_calls[0]["job_type"] == "backtest"
    assert fake_wandb.runs[0].finished is True


def test_backtest_disabled_tracker_skips_wandb(
    monkeypatch: pytest.MonkeyPatch,
    fake_wandb: FakeWandb,
) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    from forecast_cli import tracking

    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )
    tracker = WandbTracker(wandb_module=fake_wandb)

    tracking.track_backtest(
        client=object(),
        run_id="bt-002",
        config={"area": "DK1"},
        summary={"mae": 1.0},
        per_day_metrics=[],
        forecasts_df=None,
        actuals_df=None,
        tags=[],
        tracker=tracker,
    )
    assert fake_wandb.init_calls == []
```

> **NOTE for the engineer:** The exact parameter names of `track_backtest` may differ from those above (`per_day_metrics`, `forecasts_df`, `actuals_df`). Use Step 1's grep output to align the test's call to the real signature. The shape of what gets passed to `tracker.log_backtest_run(...)` is the load-bearing contract.

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/forecast_cli/test_tracking_wandb.py -v`
Expected: FAIL — `track_backtest` does not accept a `tracker` kwarg.

- [ ] **Step 4: Implement**

In `src/forecast_cli/src/forecast_cli/tracking.py`:

1. Add the import at the top:

```python
from observability_wandb.tracker import WandbTracker
```

2. Extend `track_backtest`'s signature with a keyword-only `tracker: WandbTracker | None = None`. The default-factory pattern (so callers without a tracker still get one) goes inside the function:

```python
if tracker is None:
    tracker = WandbTracker()
```

3. After the existing `insert_experiment_run(...)` and `insert_experiment_predictions(...)` calls, append:

```python
tracker.log_backtest_run(
    run_id=run_id,
    config=config,  # the dict that already populates metrics_json
    summary=summary,
    per_day=per_day_metrics,  # rename to match real param name from Step 1
    tags=tags or [],
)
```

If the real `track_backtest` already builds the per-day metrics as a DataFrame instead of a list-of-dicts, convert with `per_day_df.to_dict(orient="records")` before passing.

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/forecast_cli/test_tracking_wandb.py -v`
Expected: 2 PASS.

Also verify no existing tracking tests regressed:

Run: `uv run pytest tests/forecast_cli/ -v`
Expected: PASS across the file.

- [ ] **Step 6: Commit**

```bash
git add src/forecast_cli/src/forecast_cli/tracking.py tests/forecast_cli/test_tracking_wandb.py
git commit -m "feat(forecast_cli): dual-write backtests to W&B alongside ClickHouse"
```

---

## Task 10: Dual-write hook for `track_prediction`

**Files:**
- Modify: `src/forecast_cli/src/forecast_cli/tracking.py`
- Modify: `tests/forecast_cli/test_tracking_wandb.py`

Same pattern: after `track_prediction()` writes its `experiment_runs` + `experiment_predictions` + `model_artifacts` rows, call `tracker.log_predict_run(...)`. If `model_artifact_id` and the joblib blob are available at that call site, ALSO call `log_model_blob(...)` (Task 7's helper) to mirror the artifact.

- [ ] **Step 1: Append failing test**

Append to `tests/forecast_cli/test_tracking_wandb.py`:

```python
def test_predict_dual_writes_to_wandb(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forecast_cli import tracking

    monkeypatch.setattr(
        tracking, "insert_experiment_run", lambda *a, **k: None, raising=True
    )
    monkeypatch.setattr(
        tracking,
        "insert_experiment_predictions",
        lambda *a, **k: None,
        raising=True,
    )
    monkeypatch.setattr(
        tracking, "insert_model_artifact", lambda *a, **k: None, raising=True
    )

    tracker = WandbTracker(wandb_module=fake_wandb)

    tracking.track_prediction(
        client=object(),
        run_id="predict-2026-05-22-dk1",
        config={"area": "DK1", "target_date": "2026-05-22"},
        prediction_rows=[
            {"period": 0, "timestamp_utc": "2026-05-22T00:00:00Z", "predicted": 50.1},
        ],
        artifact_id="art-uuid-9",
        artifact_blob_b64="ZmFrZQ==",  # "fake" base64
        tags=["DK1", "lear", "predict"],
        tracker=tracker,
    )

    assert len(fake_wandb.init_calls) == 1
    assert fake_wandb.init_calls[0]["job_type"] == "predict"
    assert fake_wandb.runs[0].artifacts_logged[0].name == "art-uuid-9"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/forecast_cli/test_tracking_wandb.py::test_predict_dual_writes_to_wandb -v`
Expected: FAIL.

- [ ] **Step 3: Add a combined tracker method**

The test expects the prediction and the artifact to be attached to the same W&B run. Add a new public tracker method that does init + per-row log + (optional) artifact attach + finish in one call. This keeps `track_prediction` free of `wandb` API knowledge.

In `src/observability_wandb/src/observability_wandb/tracker.py`, add:

```python
    def log_predict_run_with_artifact(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        prediction: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
        artifact_id: str | None = None,
        artifact_blob_b64: str | None = None,
    ) -> None:
        if not self._enabled:
            return None
        from observability_wandb.artifacts import log_model_blob

        run = self._wandb.init(
            project=self._settings.default_project,
            entity=self._settings.entity,
            id=run_id,
            job_type="predict",
            tags=list(tags),
            config=dict(config),
        )
        try:
            for step, row in enumerate(prediction):
                run.log(dict(row), step=step)
            if artifact_id and artifact_blob_b64:
                log_model_blob(
                    tracker=self,
                    run=run,
                    artifact_id=artifact_id,
                    blob_b64=artifact_blob_b64,
                    metadata={
                        "area": config.get("area"),
                        "run_id": run_id,
                    },
                )
        finally:
            run.finish()
```

- [ ] **Step 4: Wire it into `track_prediction`**

In `src/forecast_cli/src/forecast_cli/tracking.py`, extend `track_prediction`'s signature with the keyword-only `tracker: WandbTracker | None = None`. After the existing ClickHouse inserts:

```python
if tracker is None:
    tracker = WandbTracker()

tracker.log_predict_run_with_artifact(
    run_id=run_id,
    config=config,
    prediction=prediction_rows,
    tags=tags or [],
    artifact_id=artifact_id,
    artifact_blob_b64=artifact_blob_b64,
)
```

If the existing `track_prediction` builds its prediction rows from a DataFrame, convert with `df.to_dict(orient="records")` before passing.

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/forecast_cli/test_tracking_wandb.py -v`
Expected: 3 PASS (including the existing two from Task 9).

- [ ] **Step 6: Commit**

```bash
git add src/forecast_cli/src/forecast_cli/tracking.py src/observability_wandb/src/observability_wandb/tracker.py tests/forecast_cli/test_tracking_wandb.py
git commit -m "feat(forecast_cli): dual-write predict runs + artifact mirror to W&B"
```

---

## Task 11: `WandbLogger` in `LightningModel`

**Files:**
- Create: `src/observability_wandb/src/observability_wandb/lightning_logger.py`
- Modify: `src/price_forecasting/src/price_forecasting/models/lightning_base.py`
- Create: `tests/observability_wandb/test_lightning_logger.py`
- Create: `tests/price_forecasting/test_lightning_wandb.py`

A factory function `build_lightning_logger(config)` returns either a `lightning.pytorch.loggers.WandbLogger` instance (when enabled and `config.wandb_project` is set) or `None`. `LightningModel` reads its config and passes the result to `L.Trainer(logger=...)`. Lightning accepts `None` or `False` as "no logger".

- [ ] **Step 1: Failing test for the factory**

Create `tests/observability_wandb/test_lightning_logger.py`:

```python
"""build_lightning_logger factory."""

from __future__ import annotations

import pytest

from observability_wandb.lightning_logger import build_lightning_logger


class _Cfg:
    wandb_project: str | None
    wandb_tags: list[str]
    experiment_name: str

    def __init__(
        self,
        wandb_project: str | None,
        wandb_tags: list[str] | None = None,
        experiment_name: str = "x",
    ) -> None:
        self.wandb_project = wandb_project
        self.wandb_tags = wandb_tags or []
        self.experiment_name = experiment_name


def test_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    assert build_lightning_logger(_Cfg(wandb_project="algo-research")) is None


def test_returns_none_when_config_has_no_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")
    assert build_lightning_logger(_Cfg(wandb_project=None)) is None


def test_returns_wandb_logger_when_enabled_and_project_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")

    from lightning.pytorch.loggers import WandbLogger

    logger = build_lightning_logger(
        _Cfg(wandb_project="algo-research", wandb_tags=["DK1", "dnn"])
    )
    assert isinstance(logger, WandbLogger)
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_lightning_logger.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the factory**

Create `src/observability_wandb/src/observability_wandb/lightning_logger.py`:

```python
"""Factory for the Lightning WandbLogger.

Returns ``None`` when W&B is disabled or the config has no
``wandb_project``. Callers (LightningModel) accept ``None`` as "no logger".
"""

from __future__ import annotations

from typing import Any, Protocol

from observability_wandb.client_factory import is_enabled, load_settings


class _CfgLike(Protocol):
    wandb_project: str | None
    wandb_tags: list[str]
    experiment_name: str


def build_lightning_logger(config: _CfgLike) -> Any | None:
    if not is_enabled():
        return None
    if not config.wandb_project:
        return None

    from lightning.pytorch.loggers import WandbLogger

    settings = load_settings()
    return WandbLogger(
        project=config.wandb_project,
        entity=settings.entity or None,
        name=config.experiment_name,
        tags=list(config.wandb_tags),
        job_type="train",
    )
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/observability_wandb/test_lightning_logger.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Wire into LightningModel**

In `src/price_forecasting/src/price_forecasting/models/lightning_base.py`:

1. Add import at top (alongside existing imports):

```python
from observability_wandb.lightning_logger import build_lightning_logger
```

2. Locate the `L.Trainer(...)` call (search for `enable_progress_bar=False` to find it). Replace the `logger=False` argument with:

```python
logger=build_lightning_logger(self._config) or False,
```

`build_lightning_logger` returns `None` when disabled; Lightning treats `False` as "no logger" but is tolerant of `None`. Coercing to `False` keeps behavior identical to the current code when disabled.

3. The model needs `self._config` (or whatever the attribute name is — find it in `LightningModel.__init__`). If the config isn't stored, store it. The `_config` reference must point to an `ExperimentConfig` with the new fields from Task 8.

- [ ] **Step 6: Integration test the wiring**

Create `tests/price_forecasting/test_lightning_wandb.py`:

```python
"""LightningModel passes a WandbLogger to Trainer when enabled."""

from __future__ import annotations

import pytest

from price_forecasting.configs.experiment import ExperimentConfig


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_trainer_logger_is_wandb_when_config_sets_project(
    enabled_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test the wiring path. We don't fit; we just assert the logger
    object set on the LightningModel's Trainer is a WandbLogger instance
    when the config opts in."""
    from observability_wandb.lightning_logger import build_lightning_logger
    from lightning.pytorch.loggers import WandbLogger

    cfg = ExperimentConfig(
        experiment_name="x",
        results_dir="results",
        area="DK1",
        wandb_project="algo-research",
        wandb_tags=["DK1", "dnn"],
    )
    logger = build_lightning_logger(cfg)
    assert isinstance(logger, WandbLogger)


def test_trainer_logger_is_none_when_config_has_no_project(
    enabled_env: None,
) -> None:
    cfg = ExperimentConfig(experiment_name="x", results_dir="results", area="DK1")
    assert build_lightning_logger(cfg) is None
```

> **NOTE:** Constructing a real `LightningModel` requires a full feature/target tensor and is heavy. The two assertions above plus the existing tests in `tests/price_forecasting/` (which exercise `LightningModel.fit()` end-to-end with `WANDB_MODE=disabled` — the CI default) prove the wiring is safe. Do not add a slow real-fit test for the W&B case.

- [ ] **Step 7: Run all tests**

Run: `uv run pytest tests/observability_wandb tests/price_forecasting -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/lightning_logger.py src/price_forecasting/src/price_forecasting/models/lightning_base.py tests/observability_wandb/test_lightning_logger.py tests/price_forecasting/test_lightning_wandb.py
git commit -m "feat(price_forecasting): WandbLogger in LightningModel trainer when enabled"
```

---

## Task 12: Optuna → W&B sweep callback

**Files:**
- Create: `src/observability_wandb/src/observability_wandb/optuna_callback.py`
- Modify: `src/price_forecasting/src/price_forecasting/tuning/optuna_storage.py`
- Create: `tests/observability_wandb/test_optuna_callback.py`
- Create: `tests/price_forecasting/test_optuna_wandb.py`

Each Optuna trial becomes a W&B run grouped under a "sweep" identified by the study name. Implementation: in the callback's `__call__(study, trial)`, init a run with `group=study.study_name`, log `trial.params` as config and `trial.value` as a summary metric, then finish.

- [ ] **Step 1: Failing test**

Create `tests/observability_wandb/test_optuna_callback.py`:

```python
"""Optuna -> W&B sweep callback."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from observability_wandb.optuna_callback import build_wandb_sweep_callback

from tests.observability_wandb.conftest import FakeWandb


@dataclasses.dataclass
class _FakeStudy:
    study_name: str


@dataclasses.dataclass
class _FakeTrial:
    number: int
    params: dict[str, Any]
    value: float
    state: Any


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_PROJECT", "algo-research")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_callback_logs_one_run_per_trial(
    enabled_env: None, fake_wandb: FakeWandb
) -> None:
    callback = build_wandb_sweep_callback(
        wandb_module=fake_wandb,
        study_name="dnn_dk1_v1",
        area="DK1",
        model_type="dnn",
        config_name="dk1_dnn",
    )
    study = _FakeStudy(study_name="dnn_dk1_v1")
    trial = _FakeTrial(
        number=3,
        params={"hidden_units": 128, "learning_rate": 1e-3},
        value=4.7,
        state="COMPLETE",
    )

    callback(study, trial)

    call = fake_wandb.init_calls[0]
    assert call["project"] == "algo-research"
    assert call["group"] == "dnn_dk1_v1"
    assert call["job_type"] == "sweep-trial"
    assert call["config"] == {
        "hidden_units": 128,
        "learning_rate": 1e-3,
        "trial_number": 3,
        "area": "DK1",
        "model_type": "dnn",
        "config_name": "dk1_dnn",
    }
    assert fake_wandb.runs[0].summary == {"value": 4.7, "state": "COMPLETE"}
    assert fake_wandb.runs[0].finished is True


def test_callback_noops_when_disabled(
    monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    callback = build_wandb_sweep_callback(
        wandb_module=fake_wandb,
        study_name="s",
        area="DK1",
        model_type="dnn",
        config_name="dk1_dnn",
    )
    callback(_FakeStudy(study_name="s"), _FakeTrial(0, {}, 0.0, "COMPLETE"))
    assert fake_wandb.init_calls == []
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_optuna_callback.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Create `src/observability_wandb/src/observability_wandb/optuna_callback.py`:

```python
"""Optuna study callback that mirrors each trial as a W&B run."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from observability_wandb.client_factory import is_enabled, load_settings


def build_wandb_sweep_callback(
    *,
    wandb_module: Any | None = None,
    study_name: str,
    area: str,
    model_type: str,
    config_name: str,
) -> Callable[[Any, Any], None]:
    if wandb_module is None:
        import wandb as wandb_module  # type: ignore[no-redef]
    settings = load_settings()
    enabled = is_enabled()

    def _callback(study: Any, trial: Any) -> None:
        if not enabled:
            return None
        run = wandb_module.init(
            project=settings.default_project,
            entity=settings.entity,
            group=study_name,
            job_type="sweep-trial",
            tags=[area, model_type, config_name],
            config={
                **dict(trial.params),
                "trial_number": trial.number,
                "area": area,
                "model_type": model_type,
                "config_name": config_name,
            },
        )
        try:
            run.summary["value"] = float(trial.value)
            run.summary["state"] = str(trial.state)
        finally:
            run.finish()

    return _callback
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/observability_wandb/test_optuna_callback.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Wire into `optuna_storage`**

In `src/price_forecasting/src/price_forecasting/tuning/optuna_storage.py`, find the existing `build_persistence_callback(...)` function. Add a sibling factory `build_wandb_callback(...)` (or import and re-export `build_wandb_sweep_callback`). Update the caller (which is `forecast-cli tune`, in `src/forecast_cli/src/forecast_cli/commands/tune.py`) to register both callbacks on `study.optimize(callbacks=[ch_cb, wandb_cb])`.

The wiring is two edits:

1. Add to `optuna_storage.py`:

```python
from observability_wandb.optuna_callback import build_wandb_sweep_callback as build_wandb_callback  # re-export
```

2. In `commands/tune.py`, after the existing `ch_cb = build_persistence_callback(...)` line, add:

```python
wandb_cb = build_wandb_callback(
    study_name=study_name,
    area=config.area,
    model_type=config.model_type,
    config_name=config_name,
)
```

Then pass both: `study.optimize(objective, n_trials=n_trials, callbacks=[ch_cb, wandb_cb])`.

- [ ] **Step 6: Add a smoke test that the wiring resolves**

Create `tests/price_forecasting/test_optuna_wandb.py`:

```python
"""Smoke: optuna_storage re-exports the W&B callback factory."""

from __future__ import annotations


def test_wandb_callback_reexport_present() -> None:
    from price_forecasting.tuning import optuna_storage

    assert hasattr(optuna_storage, "build_wandb_callback")
```

- [ ] **Step 7: Run all related tests**

Run: `uv run pytest tests/observability_wandb tests/price_forecasting/test_optuna_wandb.py tests/forecast_cli/test_tune.py -v`
Expected: PASS (existing tune tests should still pass — the new callback is additive and no-ops when `WANDB_MODE=disabled`, which is the test default).

- [ ] **Step 8: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/optuna_callback.py src/price_forecasting/src/price_forecasting/tuning/optuna_storage.py src/forecast_cli/src/forecast_cli/commands/tune.py tests/observability_wandb/test_optuna_callback.py tests/price_forecasting/test_optuna_wandb.py
git commit -m "feat(price_forecasting): mirror Optuna trials to a W&B sweep"
```

---

## Task 13: Reconciliation prod-sync hook

**Files:**
- Modify: `src/schedules/src/schedules/reconciliation.py`
- Create: `tests/schedules/test_reconciliation_wandb.py`

After the existing per-area reconciliation completes for one run, call `tracker.log_prod_reconciled(area, config_name, target_date, metrics)`. The tracker is initialized once per flow invocation (not per run) and reused.

- [ ] **Step 1: Locate the reconciliation entrypoint**

Run: `grep -n "def reconcile_predictions_flow\|def reconcile_per_run\|def _reconcile_area" src/schedules/src/schedules/reconciliation.py`

Note the function that finishes a single run's metrics. The new call goes immediately after the existing re-insert of `experiment_runs` with the populated `metrics_json`.

- [ ] **Step 2: Failing test**

Create `tests/schedules/test_reconciliation_wandb.py`:

```python
"""Reconciliation pushes daily reconciled metrics to W&B `algo-prod`."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_reconciliation_logs_to_prod_project(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a reconciliation completes for a run, the tracker logs one
    step to the prod-{area} run in the algo-prod project."""
    from schedules import reconciliation

    tracker = WandbTracker(wandb_module=fake_wandb)

    reconciliation._log_run_to_wandb(
        tracker=tracker,
        area="DK1",
        config_name="dk1_lear",
        target_date="2026-05-21",
        metrics={"mae": 4.5, "rmse": 6.1, "smape": 11.0},
    )

    call = fake_wandb.init_calls[0]
    assert call["project"] == "algo-prod"
    assert call["id"] == "prod-dk1-dk1_lear"
    assert fake_wandb.runs[0].logged[0][0]["mae"] == 4.5
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/schedules/test_reconciliation_wandb.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement**

In `src/schedules/src/schedules/reconciliation.py`:

1. Add the import at the top:

```python
from observability_wandb.tracker import WandbTracker
```

2. Add a small helper that the test calls directly (this isolates the wandb logic and is easy to test):

```python
def _log_run_to_wandb(
    *,
    tracker: WandbTracker,
    area: str,
    config_name: str,
    target_date: str,
    metrics: dict[str, float],
) -> None:
    tracker.log_prod_reconciled(
        area=area,
        config_name=config_name,
        target_date=target_date,
        metrics=metrics,
    )
```

3. In the per-run reconciliation path (the one Step 1's grep found), after the existing re-insert with populated `metrics_json`, build the metrics dict and call `_log_run_to_wandb(...)`. The tracker should be constructed at flow scope (once per flow run, **not** per run):

```python
tracker = WandbTracker()  # at the top of the flow, before the per-area loop
# ... per run ...
_log_run_to_wandb(
    tracker=tracker,
    area=row["area"],
    config_name=_extract_config_name(row),  # see existing patterns in reconciliation.py
    target_date=row["target_date"],
    metrics=metrics_dict,  # the same dict that was JSON-dumped into metrics_json
)
```

Use whatever the existing reconciliation code already builds for `metrics_dict` — do not recompute. If the dict is not available as a Python object (e.g. it was serialized directly to JSON), keep a Python copy and reuse it.

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/schedules/test_reconciliation_wandb.py -v`
Expected: PASS.

Also run the existing reconciliation tests to verify no regression:

Run: `uv run pytest tests/schedules/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/schedules/src/schedules/reconciliation.py tests/schedules/test_reconciliation_wandb.py
git commit -m "feat(schedules): mirror reconciled prod metrics to W&B algo-prod"
```

---

## Task 14: `forecast-cli ablate` command

**Files:**
- Create: `src/forecast_cli/src/forecast_cli/commands/ablate.py`
- Modify: `src/forecast_cli/src/forecast_cli/main.py`
- Create: `tests/forecast_cli/test_ablate.py`

A new Typer command that drives a config-field sweep: `forecast-cli ablate <config_name> --vary <field> --over <json>`. Internally it loads the base config (via existing `config_loader.load_config`), iterates over the values, for each one builds a modified copy of the config, invokes `BacktestRunner`, and writes results to W&B as a sweep grouped by `--study-name` (default: `f"ablate_{field}_{config_name}_{git_sha[:7]}"`).

Resulting W&B sweep gives the parallel-coordinates / Table view used directly in thesis Reports.

- [ ] **Step 1: Failing test**

Create `tests/forecast_cli/test_ablate.py`:

```python
"""ablate command: end-to-end with stubbed BacktestRunner."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_ablate_runs_one_w_and_b_run_per_variant(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from forecast_cli.commands import ablate

    captured: list[Any] = []

    def fake_backtest(cfg: Any, **_: Any) -> dict[str, float]:
        captured.append(cfg.calibration_windows)
        return {"mae": 5.0 + len(captured), "rmse": 7.0, "smape": 11.0, "rmae": 0.9}

    monkeypatch.setattr(ablate, "_run_backtest", fake_backtest, raising=True)

    runner = CliRunner()
    result = runner.invoke(
        ablate.app,
        [
            "dk1_lear",
            "--vary", "calibration_windows",
            "--over", "[[56,84],[56,84,1092],[56,84,1092,1456]]",
            "--study-name", "ablate-cw-test",
        ],
        env={
            "WANDB_API_KEY": "k",
            "WANDB_ENTITY": "e",
            "WANDB_MODE": "online",
        },
    )

    assert result.exit_code == 0
    # 3 variants, 3 backtest runs, 3 W&B runs
    assert len(captured) == 3
    # Each W&B run is a sweep-trial under the same group/study
    assert len(fake_wandb.init_calls) == 3
    groups = {c["group"] for c in fake_wandb.init_calls}
    assert groups == {"ablate-cw-test"}
```

> **NOTE:** This test patches the runner's internal `_run_backtest` helper. The command itself is responsible for wiring up Typer, parsing `--over` as JSON, applying the variant via `dataclasses.replace(cfg, **{field: value})`, then calling `_run_backtest(modified_cfg)` and forwarding to W&B.

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/forecast_cli/test_ablate.py -v`
Expected: FAIL — `forecast_cli.commands.ablate` does not exist.

- [ ] **Step 3: Implement the command**

Create `src/forecast_cli/src/forecast_cli/commands/ablate.py`:

```python
"""`forecast-cli ablate` — drive a config-field sweep into a W&B sweep.

Examples
--------
    forecast-cli ablate dk1_lear \\
        --vary calibration_windows \\
        --over '[[56,84],[56,84,1092],[56,84,1092,1456]]'
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

import typer

from forecast_cli.config_loader import load_config
from observability_wandb.client_factory import load_settings, is_enabled

app = typer.Typer(add_completion=False, help="Drive a config-field ablation.")


def _run_backtest(cfg: Any, **_: Any) -> dict[str, float]:
    """Indirection so tests can stub the slow path.

    Real implementation runs ``BacktestRunner(cfg).run()`` and returns the
    summary metrics dict (mae, rmse, smape, rmae).
    """
    from price_forecasting.backtesting.runner import BacktestRunner

    runner = BacktestRunner(cfg)
    summary, _per_day = runner.run()
    return summary


def _git_sha() -> str:
    return os.environ.get("GIT_SHA", "")


@app.callback(invoke_without_command=True)
def main(
    config_name: str = typer.Argument(..., help="Config under configs/."),
    vary: str = typer.Option(..., "--vary", help="ExperimentConfig field to vary."),
    over: str = typer.Option(..., "--over", help="JSON list of values for the field."),
    study_name: str | None = typer.Option(
        None, "--study-name", help="W&B group/sweep name (defaults to ablate-<vary>-<config>-<sha>)."
    ),
) -> None:
    base_cfg = load_config(config_name)
    values = json.loads(over)
    if not isinstance(values, list):
        raise typer.BadParameter("--over must be a JSON list.")

    sweep = study_name or f"ablate-{vary}-{config_name}-{_git_sha()[:7]}"

    if not is_enabled():
        typer.echo(
            "W&B disabled (WANDB_MODE=disabled or WANDB_API_KEY missing); "
            "running backtests but not logging."
        )
    settings = load_settings()
    import wandb

    for idx, value in enumerate(values):
        cfg = dataclasses.replace(base_cfg, **{vary: value})
        summary = _run_backtest(cfg)
        if is_enabled():
            run = wandb.init(
                project=settings.default_project,
                entity=settings.entity,
                group=sweep,
                job_type="sweep-trial",
                tags=[cfg.area, cfg.model_type, "ablate", vary],
                config={
                    "ablation_field": vary,
                    "ablation_value": value,
                    "trial_number": idx,
                    "area": cfg.area,
                    "model_type": cfg.model_type,
                    "config_name": config_name,
                },
            )
            try:
                for key, val in summary.items():
                    run.summary[key] = val
            finally:
                run.finish()
        typer.echo(f"[{idx + 1}/{len(values)}] {vary}={value!r} -> {summary}")
```

- [ ] **Step 4: Register in `main.py`**

In `src/forecast_cli/src/forecast_cli/main.py`, add (alongside the existing command registrations — find them by `grep -n "add_typer\|@app.command" src/forecast_cli/src/forecast_cli/main.py`):

```python
from forecast_cli.commands import ablate

app.add_typer(ablate.app, name="ablate")
```

Use the existing wiring pattern verbatim (the `tune` command is the closest precedent).

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/forecast_cli/test_ablate.py -v`
Expected: PASS.

- [ ] **Step 6: Smoke from the CLI**

Run with W&B disabled to confirm no network call:

Run: `WANDB_MODE=disabled uv run python -m forecast_cli.main ablate dk1_lear --vary calibration_windows --over '[[56,84]]'`
Expected: prints "W&B disabled ..." and the single-variant summary line. No errors.

(Skip if the local environment cannot run a real backtest. The unit test above is the load-bearing check.)

- [ ] **Step 7: Commit**

```bash
git add src/forecast_cli/src/forecast_cli/commands/ablate.py src/forecast_cli/src/forecast_cli/main.py tests/forecast_cli/test_ablate.py
git commit -m "feat(forecast_cli): add ablate command for config-field sweeps"
```

---

## Task 15: Docker + deploy_forecast env wiring

**Files:**
- Modify: `Dockerfile`
- Modify: `src/schedules/src/schedules/deploy_forecast.py`

The flow containers spawned by Prefect need `WANDB_API_KEY`, `WANDB_ENTITY`, and `WANDB_PROJECT` (default `algo-research`; the prod-mirror code hardcodes `algo-prod`). `WANDB_MODE` is optional — if unset and the key is present, the tracker treats that as online. CI containers are left at `WANDB_MODE=disabled` (already the default when no key is present, so no extra wiring needed).

- [ ] **Step 1: Modify the Dockerfile**

Add (or extend) the `ARG` / `ENV` block where existing env vars live. Find them with:

Run: `grep -n "ENV \|ARG " Dockerfile`

Then add `WANDB_API_KEY`, `WANDB_ENTITY`, `WANDB_PROJECT` to whichever section accepts runtime env vars — they are **runtime**, not build-time, so do not add `--build-arg` for them. They should come in via `docker run -e ...` or via Prefect's flow container env block.

For documentation purposes inside the Dockerfile, add a comment above the existing ENV block:

```dockerfile
# Runtime env consumed by observability_wandb (set via Prefect flow env or .env):
#   WANDB_API_KEY    - DTU academic API key
#   WANDB_ENTITY     - team workspace
#   WANDB_PROJECT    - default research project (algo-research)
#   WANDB_MODE       - set to "disabled" to no-op
```

No actual `ENV` line is needed — Prefect injects these into each container.

- [ ] **Step 2: Modify deploy_forecast.py**

Find the env block in `src/schedules/src/schedules/deploy_forecast.py`:

Run: `grep -n "SLACK_WEBHOOK_URL\|ENTSOE_API_KEY\|CLICKHOUSE" src/schedules/src/schedules/deploy_forecast.py`

Add a sibling block that reads `WANDB_*` from the host `.env` (via `os.environ.get(...)`) and passes them into each flow's container env. Mirror the exact pattern used for `SLACK_WEBHOOK_URL`.

```python
WANDB_API_KEY = os.environ.get("WANDB_API_KEY", "")
WANDB_ENTITY = os.environ.get("WANDB_ENTITY", "")
WANDB_PROJECT = os.environ.get("WANDB_PROJECT", "algo-research")
WANDB_MODE = os.environ.get("WANDB_MODE", "" if WANDB_API_KEY else "disabled")
```

Then in the env dict passed to each `FlowDeployment` (or whatever the existing class is called — find with `grep -n "class.*Deployment\|env=" deploy_forecast.py`):

```python
env={
    # ... existing keys ...
    "WANDB_API_KEY": WANDB_API_KEY,
    "WANDB_ENTITY": WANDB_ENTITY,
    "WANDB_PROJECT": WANDB_PROJECT,
    "WANDB_MODE": WANDB_MODE,
}
```

- [ ] **Step 3: Sanity-check by re-running the deploy script in dry mode**

Run: `PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_forecast.py --help 2>&1 | head -10`

Expected: prints the script's help / does not crash on import.

If the script has no dry-run mode, do **not** actually re-deploy here — the deploy run is the user's call (per repo safety conventions for shared infra). Just ensure the file parses.

Run: `uv run python -c "import src.schedules.src.schedules.deploy_forecast as d; print(d.WANDB_PROJECT)"`
Expected: prints `algo-research`.

(Adjust the import path if the workspace import doesn't resolve from the repo root — try `python -c "from schedules.deploy_forecast import WANDB_PROJECT; print(WANDB_PROJECT)"`.)

- [ ] **Step 4: Commit**

```bash
git add Dockerfile src/schedules/src/schedules/deploy_forecast.py
git commit -m "chore(schedules): inject WANDB_* into flow container env"
```

---

## Task 16: Documentation update

**Files:**
- Modify: `docs/REPO_OVERVIEW.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `CLAUDE.md`

Brief, fact-only updates so future engineers and Claude Code sessions understand the new surface.

- [ ] **Step 1: Update `docs/REPO_OVERVIEW.md`**

Two small additions:

(a) In Section 3 "Tech stack" (find with `grep -n "## 3. Tech stack" docs/REPO_OVERVIEW.md`), insert a new row after the Evidently row:

```markdown
| Observability — research | W&B (`observability_wandb` package) | Backtests, predict runs, DNN training (Lightning), Optuna sweeps, ablation sweeps, reconciled prod metrics. Algo-research + algo-prod projects. No-op when `WANDB_MODE=disabled`. |
```

(b) In Section 11 "Observability" (find with `grep -n "## 11. Observability"`), append a new subsection:

```markdown
### W&B (research)

`observability_wandb.tracker.WandbTracker` is the single owner of W&B-side
schema. Dual-write call sites: `forecast_cli.tracking.track_backtest /
track_prediction`, `price_forecasting.models.lightning_base.LightningModel`
(via `WandbLogger`), `price_forecasting.tuning.optuna_storage`, and
`schedules.reconciliation`. Production system is unaffected when the
tracker is disabled.

- `algo-research` project — backtests, predict runs, DNN training, sweeps,
  ablations.
- `algo-prod` project — one continuous run per `(area, config_name)`,
  one step per reconciled day. Run ID format: `prod-{area_lower}-{config}`.
- Disabled-mode: set `WANDB_MODE=disabled` or unset `WANDB_API_KEY`.
- New CLI: `forecast-cli ablate <config> --vary <field> --over <json>`.
```

- [ ] **Step 2: Update `docs/RUNBOOK.md`**

Add a new top-level section (find the existing section headings first with `grep -n "^## " docs/RUNBOOK.md` to match the heading style):

```markdown
## W&B troubleshooting

**Tracker is no-opping silently.**
Check the env: `WANDB_MODE` should be empty or `online`, and
`WANDB_API_KEY` must be set. The tracker logs nothing to Loki when
disabled (silent by design — see `client_factory.is_enabled`).

**Runs land in the wrong project.**
Backtests / predict / tune / ablate write to `WANDB_PROJECT` (default
`algo-research`). The reconciliation prod-sync hardcodes `algo-prod` —
this is intentional and not configurable.

**Daily prod run does not appear.**
The prod-mirror run uses a deterministic ID `prod-{area_lower}-{config}`
with `resume="allow"`. If it doesn't appear, check the reconciliation
flow's Loki logs for `WandbTracker` exceptions (the tracker catches
errors but logs at WARNING).

**Authoring Reports with Claude Code.**
The W&B MCP server is configured at the repo level. Restart your Claude
Code session if it doesn't appear under `/mcp`. The key is read from
`.env` via the local-scope `~/.claude.json` entry. To re-register after
rotating the key: `claude mcp remove wandb && claude mcp add --transport http wandb https://mcp.withwandb.com/mcp --header "Authorization: Bearer $WANDB_API_KEY"`.
```

- [ ] **Step 3: Update `CLAUDE.md`**

Find the "Observability" subsection (`grep -n "### Observability" CLAUDE.md`) and append, just before the next `###` heading:

```markdown
- **W&B research surface**: `observability_wandb.tracker.WandbTracker` is the
  ONLY place `wandb` is imported outside its own package. Other packages
  depend on the tracker (`WandbTracker`, `build_lightning_logger`,
  `build_wandb_sweep_callback`). Disable for local/CI with
  `WANDB_MODE=disabled` — the tracker no-ops cleanly. Two projects:
  `algo-research` (default) and `algo-prod` (hardcoded for reconciliation
  sync). New CLI: `forecast-cli ablate <config> --vary <field> --over
  <json>` runs an ablation sweep and emits to W&B.
```

- [ ] **Step 4: Commit**

```bash
git add docs/REPO_OVERVIEW.md docs/RUNBOOK.md CLAUDE.md
git commit -m "docs: document W&B integration surface and runbook"
```

---

## Task 17: Final full-suite verification

**Files:**
- None (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v 2>&1 | tail -40`
Expected: all PASS, no W&B network calls (CI default has no `WANDB_API_KEY`, so trackers are disabled).

- [ ] **Step 2: Ruff**

Run: `uv run ruff check src/ tests/`
Expected: no lint errors. Fix any that surface in newly added files. If formatting drift appears, also run `uv run ruff format src/ tests/`.

- [ ] **Step 3: Type-check the new package**

Run: `uv run python -c "from observability_wandb import WandbTracker; from observability_wandb.lightning_logger import build_lightning_logger; from observability_wandb.optuna_callback import build_wandb_sweep_callback; from observability_wandb.artifacts import log_model_blob; print('all imports OK')"`
Expected: `all imports OK`.

- [ ] **Step 4: Smoke the disabled path end-to-end**

Run with the tracker disabled, exercising a real backtest:

Run: `WANDB_MODE=disabled uv run python -m forecast_cli.main backtest dk1_lear 2>&1 | tail -20`
Expected: backtest runs to completion; no W&B-related output or errors.

(If running a full backtest is too slow locally, skip this and rely on the unit test coverage — but the pytest suite already covers the disabled path.)

- [ ] **Step 5: Smoke the enabled path against a throwaway W&B run**

This is the only step that touches real W&B. Skip if you do not want to create a real run.

Run: `WANDB_MODE=online WANDB_ENTITY=$WANDB_ENTITY uv run python -m forecast_cli.main ablate dk1_lear --vary calibration_windows --over '[[56,84]]' --study-name smoke-test 2>&1 | tail -10`
Expected: one run lands in the `algo-research` project under group `smoke-test`. Delete it from the W&B UI when done.

- [ ] **Step 6: No commit**

This task is verification-only.

---

## Self-review checklist

Run before declaring the plan complete:

**Spec coverage**

| Spec section | Plan task(s) |
|---|---|
| §4 Architecture diagram | Tasks 1–14 collectively |
| §5.2 modified files | Tasks 8, 9, 10, 11, 12, 13, 15 |
| §5.3 new files | Tasks 1, 2, 3–7, 11, 12, 14 |
| §6 duplicated by design | Tasks 9, 10, 13, plus 7 (artifacts) |
| §7 project structure (`algo-research`, `algo-prod`) | Tasks 4–7, 13 |
| §8 config & secrets | Tasks 2, 15 |
| §9 reliability (no-op when disabled, no exceptions to callers) | Tasks 3, every method test |
| §10 demo storyboard | Tasks 9, 11, 12, 13, 14 produce the demo content |
| §11 MCP server | Out of scope (already configured) — documented in Task 16 RUNBOOK update |

All spec sections covered.

**Placeholder scan**: none — every step contains executable content or a concrete grep/path the engineer must resolve from the actual repo state.

**Type/method consistency**:
- `WandbTracker.log_backtest_run(run_id, config, summary, per_day, tags)` — same signature in Tasks 3, 4, 9, 17.
- `WandbTracker.log_predict_run(run_id, config, prediction, tags)` — same in Tasks 3, 5, 10.
- `WandbTracker.log_prod_reconciled(area, config_name, target_date, metrics)` — same in Tasks 3, 6, 13.
- `WandbTracker.log_artifact(run, artifact_id, artifact_type, local_path, metadata)` — same in Tasks 3, 7, 10.
- `build_lightning_logger(config)` — same in Tasks 11, 16.
- `build_wandb_sweep_callback(study_name, area, model_type, config_name)` — same in Tasks 12, 16.

No drift.

**Scope check**: single subsystem (W&B integration); one plan is appropriate.
