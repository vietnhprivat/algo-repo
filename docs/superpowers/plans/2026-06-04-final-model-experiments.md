# Final Model Experiments & Modelling-Side Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the paper-faithful LEAR/DNN/Transformer benchmark on DK1 + DE over the shared test window 2025-10-24 → 2026-05-31 with paper-exact exogenous features, and produce the modelling-side report chapters comparing results against Lago et al. (2021) and Llorente & Portela (2025).

**Architecture:** A small config+loader extension (`exogenous_aggregates`) sums raw ENTSOE wind/solar curves into the papers' aggregate series at load time; all six experiment configs align on one test window; a new report script turns the six runs' outputs into the comparison tables; two new LaTeX chapter scaffolds consume them.

**Tech Stack:** Python (pandas/numpy/sklearn/PyTorch via existing models), ClickHouse, Typer CLIs (`data_cli`, `forecast_cli`), pytest with MagicMock fake clients, LaTeX (latexmk).

**Spec:** `docs/superpowers/specs/2026-06-04-final-model-experiments-and-report-design.md`

**Branch:** `final-model-experiments` (already created, contains the spec commit).

**Scheduling note:** Tasks 1, 6, 7, 8, 9 are long-running compute (backfill ≈ 1–2 h; each tune and each DNN backtest = overnight; transformers = several hours each). Code/writing tasks interleave: Task 2–3 can run while Task 1's backfill is in flight; Tasks 10–12 can be written while Tasks 6–9 compute. Only Task 13's pinned numbers and Task 10's *execution* require all six runs to be finished.

---

## Task 1: Backfill wind/solar history for DK1 and DE

**Files:** none (data-only task)

The papers' exogenous features need wind (DK1) and wind+solar (DE) day-ahead forecasts back to the start of price history (2022-03-10). The DB currently has these curves only from 2026-04-29.

- [ ] **Step 1: Launch the DK1 backfill in the background**

```bash
cd /home/vietnh/Projects/algo-repo
nohup uv run python -m data_cli.main entsoe backfill wind-solar -a DK1 -s 2022-03-10 -e 2026-06-04 > /tmp/backfill_dk1_wind.log 2>&1 &
```

Expected: process starts; log shows chunked ENTSOE fetches. The client is rate-limited (400 calls/60 s) — expect up to 1–2 h.

- [ ] **Step 2: Launch the DE backfill in the background**

```bash
nohup uv run python -m data_cli.main entsoe backfill wind-solar -a DE -s 2022-03-10 -e 2026-06-04 > /tmp/backfill_de_wind.log 2>&1 &
```

(Safe to run concurrently — the rate limiter is per-client; if ENTSOE 429s appear in the logs, rerun sequentially. Re-ingestion is always safe: `ReplacingMergeTree` dedups.)

- [ ] **Step 3: While waiting — proceed to Task 2.** Return here when both logs end with a `BackfillResult` summary line.

- [ ] **Step 4: Verify coverage per curve**

```bash
docker exec clickhouse-server clickhouse-client --query "
SELECT splitByChar(' ', curve_name)[2] AS area,
       splitByChar(' ', curve_name)[3] AS curve_type,
       min(timestamp_utc) AS earliest,
       max(timestamp_utc) AS latest,
       uniqExact(toDate(timestamp_utc)) AS days
FROM algo.forecasts
WHERE splitByChar(' ', curve_name)[2] IN ('DK1','DE')
  AND splitByChar(' ', curve_name)[3] IN ('WindOnshore','WindOffshore','Solar')
GROUP BY area, curve_type ORDER BY area, curve_type"
```

Expected: all six (area, curve) rows show `earliest` ≈ 2022-03-10 and `days` ≥ 1500.

**STOP CONDITION:** If any curve's `earliest` is materially later than 2022-03-10 (e.g. DK1 WindOffshore only from 2023), STOP and surface to the owner — the aggregate's inner join would truncate the whole Wind series to the latest member's start (spec §8 names the fallback: drop that member per-market and document).

- [ ] **Step 5: Check for gap days inside the range**

```bash
docker exec clickhouse-server clickhouse-client --query "
SELECT curve_name, count() AS suspicious_days FROM (
  SELECT curve_name, toDate(timestamp_utc) AS d, count(DISTINCT timestamp_utc) AS c
  FROM algo.forecasts
  WHERE splitByChar(' ', curve_name)[2] IN ('DK1','DE')
    AND splitByChar(' ', curve_name)[3] IN ('WindOnshore','WindOffshore','Solar')
  GROUP BY curve_name, d HAVING c < 20
) GROUP BY curve_name"
```

Expected: zero rows, or a handful of DST-transition days only (those days are already dropped by the preprocessor's NaN mask — fine).

- [ ] **Step 6: Force dedup**

```bash
docker exec clickhouse-server clickhouse-client --query "OPTIMIZE TABLE algo.forecasts FINAL"
```

---

## Task 2: `exogenous_aggregates` field + `exogenous_columns` property on ExperimentConfig

**Files:**
- Modify: `src/price_forecasting/src/price_forecasting/configs/experiment.py`
- Test: `tests/price_forecasting/test_experiment_config.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/price_forecasting/test_experiment_config.py`:

```python
class TestExogenousAggregates:
    def test_defaults_empty(self):
        config = ExperimentConfig(
            experiment_name="x", results_dir="r", area="DK1"
        )
        assert config.exogenous_aggregates == {}
        assert config.exogenous_columns == []

    def test_exogenous_columns_combines_types_and_aggregate_names(self):
        config = ExperimentConfig(
            experiment_name="x",
            results_dir="r",
            area="DK1",
            exogenous_curve_types=["TotalLoad"],
            exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
        )
        assert config.exogenous_columns == ["TotalLoad", "Wind"]
```

(If the file imports `ExperimentConfig` already, reuse the import; otherwise add `from price_forecasting.configs import ExperimentConfig` at the top, matching the file's existing import style.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/price_forecasting/test_experiment_config.py -v -k Aggregates`
Expected: FAIL — `AttributeError` / `TypeError: unexpected keyword argument 'exogenous_aggregates'`

- [ ] **Step 3: Implement** — in `configs/experiment.py`, directly below the `exogenous_curve_types` field (line 41):

```python
    # Aggregate exogenous series summed from raw curves at load time, e.g.
    # {"Wind": ["WindOnshore", "WindOffshore"]} produces one "Wind" column.
    # Keeps the papers' exactly-two-exogenous spec (Lago 2021 §3) while the
    # DB stores only raw ENTSOE curves.
    exogenous_aggregates: Dict[str, List[str]] = field(default_factory=dict)
```

and a property at the end of the class:

```python
    @property
    def exogenous_columns(self) -> List[str]:
        """All exogenous column names after loading: raw curve types followed
        by aggregate names. This is what the feature pipeline sees."""
        return list(self.exogenous_curve_types) + list(self.exogenous_aggregates)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/price_forecasting/test_experiment_config.py -v`
Expected: ALL PASS (new + existing)

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/configs/experiment.py tests/price_forecasting/test_experiment_config.py
git commit -m "feat(config): exogenous_aggregates field + exogenous_columns property"
```

---

## Task 3: Loader-level aggregation + preprocessor wiring

**Files:**
- Modify: `src/price_forecasting/src/price_forecasting/data/clickhouse_loader.py`
- Modify: `src/price_forecasting/src/price_forecasting/data/preprocessor.py:50`
- Modify: `CLAUDE.md` (one line, Feature Engineering section)
- Test: `tests/price_forecasting/test_clickhouse_loader.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/price_forecasting/test_clickhouse_loader.py` (reuses the existing `_make_mock_query_result` helper and imports):

```python
class TestLoadExogenousAggregates:
    def _two_member_client(self):
        t0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        t1 = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        onshore = [(t0, 100.0), (t1, 110.0)]
        offshore = [(t0, 40.0), (t1, 44.0)]
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        return client

    def test_aggregate_column_is_sum_of_members(self):
        client = self._two_member_client()
        df = load_exogenous_series(
            client, "DK1", [], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert list(df.columns) == ["Wind"]
        assert df["Wind"].tolist() == [140.0, 154.0]

    def test_aggregate_queries_each_member_curve(self):
        client = self._two_member_client()
        load_exogenous_series(
            client, "DK1", [], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        calls = client.query.call_args_list
        curve_names = [
            c.kwargs.get("parameters", c[1].get("parameters", {})).get("curve_name")
            for c in calls
        ]
        assert "ENTSOE DK1 WindOnshore Dayahead" in curve_names
        assert "ENTSOE DK1 WindOffshore Dayahead" in curve_names

    def test_aggregate_drops_timestamps_missing_in_any_member(self):
        t0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        t1 = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        onshore = [(t0, 100.0), (t1, 110.0)]
        offshore = [(t0, 40.0)]  # t1 missing
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        df = load_exogenous_series(
            client, "DK1", [], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert len(df) == 1
        assert df["Wind"].tolist() == [140.0]

    def test_plain_and_aggregate_columns_combine(self):
        t0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        load_rows = [(t0, 45000.0)]
        onshore = [(t0, 100.0)]
        offshore = [(t0, 40.0)]
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(load_rows, ["timestamp_utc", "value"]),
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        df = load_exogenous_series(
            client, "DK1", ["TotalLoad"], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert list(df.columns) == ["TotalLoad", "Wind"]
        assert df["Wind"].tolist() == [140.0]
        assert df["TotalLoad"].tolist() == [45000.0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/price_forecasting/test_clickhouse_loader.py -v -k Aggregates`
Expected: FAIL — `TypeError: load_exogenous_series() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: Implement the loader change** — in `clickhouse_loader.py`, replace the body of `load_exogenous_series` with a `_fetch_curve` helper + aggregation:

```python
def _fetch_curve(client: Client, area: str, curve_type: str) -> pd.DataFrame:
    """Fetch one forecast curve as a single-column DataFrame indexed by timestamp."""
    curve_name = f"ENTSOE {area} {curve_type} Dayahead"
    result = client.query(
        "SELECT timestamp_utc, value "
        "FROM algo.forecasts "
        "WHERE curve_name = {curve_name:String} "
        "ORDER BY timestamp_utc",
        parameters={"curve_name": curve_name},
    )

    df = pd.DataFrame(result.result_rows, columns=["timestamp_utc", curve_type])
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.drop_duplicates(subset=["timestamp_utc"], keep="last")
    df = df.set_index("timestamp_utc").sort_index()
    return df


def load_exogenous_series(
    client: Client,
    area: str,
    curve_types: list[str],
    aggregates: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Query algo.forecasts for each curve type and each aggregate.

    Returns DataFrame with DatetimeIndex, one column per curve type, plus one
    column per aggregate (the sum of its member curves, inner-joined on
    timestamps so partial sums never occur).
    Curve names follow: "ENTSOE {area} {curve_type} Dayahead"
    """
    frames = [_fetch_curve(client, area, curve_type) for curve_type in curve_types]

    for aggregate_name, members in (aggregates or {}).items():
        member_frames = [_fetch_curve(client, area, member) for member in members]
        joined = member_frames[0]
        for member_frame in member_frames[1:]:
            joined = joined.join(member_frame, how="inner")
        frames.append(joined.sum(axis=1).to_frame(name=aggregate_name))

    if not frames:
        return pd.DataFrame()

    exogenous = frames[0]
    for df in frames[1:]:
        exogenous = exogenous.join(df, how="outer")

    return exogenous
```

and in `load_dataset`, change the exogenous branch to:

```python
        if config.exogenous_curve_types or config.exogenous_aggregates:
            exogenous = load_exogenous_series(
                client,
                config.area,
                config.exogenous_curve_types,
                config.exogenous_aggregates,
            )
            dataset = prices.join(exogenous, how="inner")
```

- [ ] **Step 4: Wire the preprocessor** — in `preprocessor.py` line 50, change:

```python
            self.transformers = default_transformers_for_model(experiment_config.exogenous_curve_types)
```

to:

```python
            self.transformers = default_transformers_for_model(experiment_config.exogenous_columns)
```

(Backward compatible: with no aggregates, `exogenous_columns == exogenous_curve_types`.)

- [ ] **Step 5: Run the full price_forecasting test module**

Run: `uv run python -m pytest tests/price_forecasting/ -v`
Expected: ALL PASS (new aggregate tests + all existing loader/preprocessor/engine tests)

- [ ] **Step 6: Document the convention** — in `CLAUDE.md`, section "Feature Engineering (price_forecasting/data/)", add one bullet after the feature-explosion bullet:

```markdown
- **Exogenous aggregates**: `ExperimentConfig.exogenous_aggregates` (e.g. `{"Wind": ["WindOnshore", "WindOffshore"]}`) sums raw curves into one series at load time — used to match the papers' exactly-two-exogenous spec (Lago NP: load+wind; EPEX-DE: load+wind+solar). Members are inner-joined on timestamps before summing so partial sums never occur. The feature pipeline sees `config.exogenous_columns` (curve types + aggregate names).
```

- [ ] **Step 7: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/data/clickhouse_loader.py src/price_forecasting/src/price_forecasting/data/preprocessor.py tests/price_forecasting/test_clickhouse_loader.py CLAUDE.md
git commit -m "feat(data): config-driven exogenous aggregation in ClickHouse loader"
```

---

## Task 4: Align all six experiment configs

**Files:**
- Modify: `configs/dk1_lear.py`, `configs/de_lear.py`, `configs/dk1_dnn.py`, `configs/de_dnn.py`, `configs/dk1_transformer.py`, `configs/de_transformer.py`

**Requires Task 1 complete** (the verification snippets read Wind/Renewables data).

- [ ] **Step 1: Rewrite `configs/dk1_lear.py`** (full new content):

```python
from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_lear",
    area="DK1",
    model_type="lear",
    results_dir="results",
    # Shared final-benchmark test window (all six configs identical) — the
    # longest window keeping DNN tuning ex-ante (val ends 2025-10-23).
    # Lago et al. 2021 recommend >= 1 year; 31 weeks is the documented,
    # data-constrained deviation (spec 2026-06-04).
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    # Validation window: 42 weeks immediately preceding test (Lago §4.3.2).
    # Used by `forecast-cli tune` only; backtests train on all pre-test data.
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    # Paper-correct ensemble windows (Lago Table 2); 1456d removed (dips into 2022).
    calibration_windows=[56, 84, 1092],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.1, Nord Pool): load + wind generation.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
    target_scaler="asinh",
    model_params={"alpha": "auto"},
)
```

- [ ] **Step 2: Rewrite `configs/de_lear.py`** (full new content):

```python
from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="de_lear",
    area="DE",
    model_type="lear",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    calibration_windows=[56, 84, 1092],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.6, EPEX-DE): zonal load + aggregated
    # wind & solar generation forecasts.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={
        "Renewables": ["WindOnshore", "WindOffshore", "Solar"]
    },
    target_scaler="asinh",
    model_params={"alpha": "auto"},
)
```

- [ ] **Step 3: Update `configs/dk1_dnn.py`** — change only the dates, exogenous block, and the calibration-window comment; **keep the existing `model_params` and `n_dnn_ensemble` untouched** (Task 6 replaces the params after re-tuning):

```python
from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_dnn",
    area="DK1",
    model_type="dnn",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    # 42-week validation window for Optuna tuning (ex-ante: ends the day
    # before the test window starts).
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    # DNN: single long window (Lago §4.3 uses 4 years; 730d kept as the
    # documented data/compute-constrained deviation). Ensemble of 4 (Lago §4.4).
    calibration_windows=[730],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.1, Nord Pool): load + wind generation.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
    target_scaler="asinh",
    # INTERIM — re-tune pending (Task 6): these params were tuned on
    # TotalLoad-only features (study dk1_dnn_tune_v3) and are replaced by the
    # paper-exog re-tune before the final backtest.
    model_params={
        "hidden_units": 198,
        "activation": "tanh",
        "dropout": 0.02680613227742755,
        "learning_rate": 0.000627980254004135,
        "batch_norm": False,
        "l1_reg": 0.0006727849421606088,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
```

- [ ] **Step 4: Update `configs/de_dnn.py`** — same pattern (full new content; existing params kept INTERIM until Task 7):

```python
from price_forecasting import ExperimentConfig

config = ExperimentConfig(
    experiment_name="de_dnn",
    area="DE",
    model_type="dnn",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    val_start_date="2025-01-01",
    val_end_date="2025-10-23",
    calibration_windows=[730],
    refit_interval_days=1,
    # Paper-exact exogenous (Lago §3.6, EPEX-DE): load + wind & solar.
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={
        "Renewables": ["WindOnshore", "WindOffshore", "Solar"]
    },
    target_scaler="asinh",
    # INTERIM — re-tune pending (Task 7): tuned on TotalLoad-only features
    # (study de_dnn_tune_v4); replaced by the paper-exog re-tune.
    model_params={
        "hidden_units": 58,
        "activation": "elu",
        "dropout": 0.13216185974066028,
        "learning_rate": 0.004855834388063902,
        "batch_norm": False,
        "l1_reg": 0.0005710947096868873,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
    n_dnn_ensemble=4,
)
```

- [ ] **Step 5: Update `configs/dk1_transformer.py`** (full new content — exog swap Generation → Wind aggregate, window extension):

```python
"""DK1 day-ahead forecasting config — pure-Transformer model
(Llorente & Portela, 2025).

Production deployment defined in src/schedules/src/schedules/deploy_forecast.py:FORECAST_CONFIGS.
Defaults below follow the paper's Nord Pool / EPEX search ranges.
"""

from price_forecasting import ExperimentConfig
from price_forecasting.data import default_transformers_for_transformer

# Paper-exact exogenous (the paper benchmarks on the Lago open-access
# datasets; Nord Pool = load + wind): TotalLoad + Wind aggregate.
_EXOG = ["TotalLoad", "Wind"]
_SEQ = 14  # m days of past prices (paper search: m in {14, 28})

config = ExperimentConfig(
    experiment_name="dk1_transformer",
    area="DK1",
    model_type="transformer",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    calibration_windows=[1092],
    refit_interval_days=7,
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
    target_scaler="asinh",
    feature_transformers=default_transformers_for_transformer(
        exogenous_columns=_EXOG,
        sequence_length_days=_SEQ,
    ),
    model_params={
        "seq_length_days": _SEQ,
        "n_exog": len(_EXOG),
        "embedding_dim": 128,
        "n_heads": 8,
        "n_encoder_layers": 6,
        "ff_dim": 1024,
        "dropout": 0.2,
        "mlp_hidden": 128,
        "gradient_clip_val": None,
        "lr_scheduler_step": 70,
        "lr_scheduler_gamma": 0.1,
        "epochs": 200,
        "batch_size": 32,
        "learning_rate": 1e-4,
        "validation_fraction": 0.16,
        "early_stopping_patience": 25,
        "random_seed": 42,
    },
)
```

- [ ] **Step 6: Update `configs/de_transformer.py`** (full new content — window provisionally 1092, finalized in Step 7):

```python
"""DE day-ahead forecasting config — pure-Transformer model
(Llorente & Portela, 2025).

Mirror of dk1_transformer.py with area='DE'. Production deployment
defined in src/schedules/src/schedules/deploy_forecast.py:FORECAST_CONFIGS.
"""

from price_forecasting import ExperimentConfig
from price_forecasting.data import default_transformers_for_transformer

# Paper-exact exogenous (Lago EPEX-DE: load + aggregated wind & solar).
_EXOG = ["TotalLoad", "Renewables"]
_SEQ = 14  # m days of past prices (paper search: m in {14, 28})

config = ExperimentConfig(
    experiment_name="de_transformer",
    area="DE",
    model_type="transformer",
    results_dir="results",
    # Shared final-benchmark test window — see configs/dk1_lear.py.
    test_start_date="2025-10-24",
    test_end_date="2026-05-31",
    # Window verified against usable sequence rows before test start
    # (Task 4 step 7 of the 2026-06-04 plan); with wind/solar backfilled to
    # 2022-03 the previous 365d data-sparsity cap no longer binds. If the
    # verification snippet reports < 1092 usable rows, set this to
    # (reported - 10) and update this comment with the measured number.
    calibration_windows=[1092],
    refit_interval_days=7,
    exogenous_curve_types=["TotalLoad"],
    exogenous_aggregates={
        "Renewables": ["WindOnshore", "WindOffshore", "Solar"]
    },
    target_scaler="asinh",
    feature_transformers=default_transformers_for_transformer(
        exogenous_columns=_EXOG,
        sequence_length_days=_SEQ,
    ),
    model_params={
        "seq_length_days": _SEQ,
        "n_exog": len(_EXOG),
        "embedding_dim": 128,
        "n_heads": 8,
        "n_encoder_layers": 6,
        "ff_dim": 1024,
        "dropout": 0.2,
        "mlp_hidden": 128,
        "gradient_clip_val": None,
        "lr_scheduler_step": 70,
        "lr_scheduler_gamma": 0.1,
        "epochs": 200,
        "batch_size": 32,
        "learning_rate": 1e-4,
        "validation_fraction": 0.16,
        "early_stopping_patience": 25,
        "random_seed": 42,
    },
)
```

- [ ] **Step 7: Verify usable rows for both transformer configs** (this decides the DE window):

```bash
uv run python - <<'EOF'
import importlib.util
import pandas as pd
from price_forecasting.data.preprocessor import DataPreprocessor

for name in ("dk1_transformer", "de_transformer"):
    spec = importlib.util.spec_from_file_location("cfg", f"configs/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    config = mod.config
    pre = DataPreprocessor(config)
    features, targets = pre.build_dataset()
    n_before = int((features.index < pd.Timestamp(config.test_start_date)).sum())
    print(f"{name}: usable rows before test start = {n_before} "
          f"(window {config.calibration_windows[0]})")
EOF
```

Expected: `dk1_transformer` ≥ 1092. For `de_transformer`: if ≥ 1092, keep `[1092]`; otherwise edit `configs/de_transformer.py` to `calibration_windows=[<reported - 10>]` and record the measured number in the comment.

- [ ] **Step 8: Commit**

```bash
git add configs/
git commit -m "feat(configs): shared 2025-10-24..2026-05-31 test window + paper-exact exogenous for all six experiments"
```

---

## Task 5: Feature-count sanity check + LEAR backtests (both markets)

**Files:** none (run + verify task)

- [ ] **Step 1: Verify paper-exact feature counts** (Lago Eq. 3: `4·n + 2·3·n + 7`):

```bash
uv run python - <<'EOF'
import importlib.util
from price_forecasting.data.preprocessor import DataPreprocessor

for name in ("dk1_lear", "de_lear"):
    spec = importlib.util.spec_from_file_location("cfg", f"configs/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pre = DataPreprocessor(mod.config)
    features, targets = pre.build_dataset()
    n = targets.shape[1]
    expected = 4 * n + 2 * 3 * n + 7
    status = "OK" if features.shape[1] == expected else "MISMATCH"
    print(f"{name}: n_periods={n} features={features.shape[1]} expected={expected} {status}")
EOF
```

Expected output: `dk1_lear: n_periods=24 features=247 expected=247 OK` and `de_lear: n_periods=96 features=967 expected=967 OK`. If MISMATCH, stop and debug the aggregate wiring before burning compute.

- [ ] **Step 2: Run the DK1 LEAR backtest**

```bash
uv run python -m forecast_cli.main backtest dk1_lear --track 2>&1 | tee /tmp/bt_dk1_lear.log
```

Expected: completes (tens of minutes — 220 test days × 3 windows, daily refit); prints `Metrics Summary` with `rMAE` and `Tracked run <id> in ClickHouse.`

- [ ] **Step 3: Run the DE LEAR backtest**

```bash
uv run python -m forecast_cli.main backtest de_lear --track 2>&1 | tee /tmp/bt_de_lear.log
```

Expected: same shape of output (slower — 96 periods → 96 Lasso fits per window-day).

- [ ] **Step 4: Verify outputs**

```bash
uv run python - <<'EOF'
import json
import pandas as pd

for name in ("dk1_lear", "de_lear"):
    fc = pd.read_csv(f"results/{name}_forecasts.csv", index_col=0)
    metrics = json.loads(open(f"results/{name}_metrics.json").read())
    assert not fc.isna().any().any(), f"{name}: NaNs in forecasts"
    print(name, "days:", len(fc), "metrics:", metrics)
EOF
```

Expected: `days: 220` for both; `rmae` present and plausibly `< 1.0` (beating weekly-naive); MAE in single-to-low-double-digit EUR/MWh. Sanity-question anything wildly off (e.g. rMAE > 1.5) before proceeding.

---

## Task 6: Re-tune dk1_dnn on paper-exact features (overnight)

**Files:**
- Modify: `configs/dk1_dnn.py` (model_params block only)

- [ ] **Step 1: Launch the study** (overnight; ~50 trials × one 730d training per trial):

```bash
nohup uv run python -m forecast_cli.main tune dk1_dnn -n 50 --study-name dk1_dnn_tune_v5_paperexog > /tmp/tune_dk1_dnn.log 2>&1 &
```

- [ ] **Step 2: After completion, extract the best trial**

```bash
tail -5 /tmp/tune_dk1_dnn.log
docker exec clickhouse-server clickhouse-client --query "
SELECT trial_number, value, params_json
FROM algo.hyperparam_trials FINAL
WHERE study_name = 'dk1_dnn_tune_v5_paperexog' AND state = 'COMPLETE'
ORDER BY value ASC LIMIT 1 FORMAT Vertical"
```

Expected: one row; `value` = best val MAE; `params_json` holds the 6 architecture HPs (`n_neurons`, `activation`, `dropout`, `learning_rate`, `batch_norm`, `l1_reg`).

(If the `state`/`params_json` column names differ, inspect with `DESCRIBE algo.hyperparam_trials` and adapt — the table came from migration `008`.)

- [ ] **Step 3: Paste params into `configs/dk1_dnn.py`** — replace the INTERIM comment + `model_params` with (values from Step 2; `n_neurons` maps to `hidden_units`):

```python
    # Tuned via `forecast-cli tune dk1_dnn -n 50 --study-name
    # dk1_dnn_tune_v5_paperexog` on paper-exact exogenous (TotalLoad + Wind),
    # val MAE <VALUE> on trial <N>. See algo.hyperparam_trials.
    model_params={
        "hidden_units": <n_neurons>,
        "activation": "<activation>",
        "dropout": <dropout>,
        "learning_rate": <learning_rate>,
        "batch_norm": <batch_norm>,
        "l1_reg": <l1_reg>,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
```

(`<...>` are the literal best-trial values — fill every one; `epochs`/`early_stopping_patience` stay fixed, they are not tuned.)

- [ ] **Step 4: Commit**

```bash
git add configs/dk1_dnn.py
git commit -m "feat(dnn): dk1_dnn re-tuned on paper-exact exogenous (dk1_dnn_tune_v5_paperexog)"
```

---

## Task 7: Re-tune de_dnn on paper-exact features (overnight)

**Files:**
- Modify: `configs/de_dnn.py` (model_params block only)

Identical procedure to Task 6 with the DE study:

- [ ] **Step 1: Launch**

```bash
nohup uv run python -m forecast_cli.main tune de_dnn -n 50 --study-name de_dnn_tune_v5_paperexog > /tmp/tune_de_dnn.log 2>&1 &
```

- [ ] **Step 2: Extract best trial** — same query as Task 6 Step 2 with `study_name = 'de_dnn_tune_v5_paperexog'`.

- [ ] **Step 3: Paste params into `configs/de_dnn.py`** — same template as Task 6 Step 3, comment citing `de_dnn_tune_v5_paperexog`, exogenous "(TotalLoad + Renewables)".

- [ ] **Step 4: Commit**

```bash
git add configs/de_dnn.py
git commit -m "feat(dnn): de_dnn re-tuned on paper-exact exogenous (de_dnn_tune_v5_paperexog)"
```

---

## Task 8: DNN final backtests (overnight, sequential)

**Files:** none (run + verify task)

- [ ] **Step 1: Launch both sequentially** (220 days × daily refit × 4-net ensemble each — run overnight):

```bash
nohup bash -c "uv run python -m forecast_cli.main backtest dk1_dnn --track && uv run python -m forecast_cli.main backtest de_dnn --track" > /tmp/bt_dnn.log 2>&1 &
```

- [ ] **Step 2: Verify both runs** (same check as Task 5 Step 4 with `("dk1_dnn", "de_dnn")`):

```bash
uv run python - <<'EOF'
import json
import pandas as pd

for name in ("dk1_dnn", "de_dnn"):
    fc = pd.read_csv(f"results/{name}_forecasts.csv", index_col=0)
    metrics = json.loads(open(f"results/{name}_metrics.json").read())
    assert not fc.isna().any().any(), f"{name}: NaNs in forecasts"
    print(name, "days:", len(fc), "metrics:", metrics)
EOF
```

Expected: 220 days each; `Tracked run` lines in `/tmp/bt_dnn.log`.

---

## Task 9: Transformer final backtests

**Files:** none (run + verify task)

- [ ] **Step 1: Launch both sequentially** (~32 weekly refits each; several hours):

```bash
nohup bash -c "uv run python -m forecast_cli.main backtest dk1_transformer --track && uv run python -m forecast_cli.main backtest de_transformer --track" > /tmp/bt_transformer.log 2>&1 &
```

- [ ] **Step 2: Verify** — same check with `("dk1_transformer", "de_transformer")`. Expected: 220 days each, no NaNs, tracked-run lines present.

---

## Task 10: Model-comparison report script

**Files:**
- Create: `scripts/report/extract_model_comparison.py`
- Test: `tests/scripts/test_extract_model_comparison.py`
- Output (committed): `Report/metrics/model_comparison.md`

**Code can be written before Tasks 6–9 finish; execution (Step 6) needs all six runs.**

- [ ] **Step 1: Write the failing tests** — create `tests/scripts/test_extract_model_comparison.py`:

```python
"""Tests for the pure table-building helpers of extract_model_comparison."""

import numpy as np
import pandas as pd

from scripts.report.extract_model_comparison import (
    errors_matrix,
    build_headline_table,
    build_gw_table,
    to_latex_booktabs,
)


def _wide(values, start="2026-01-01"):
    """Build a (n_days x n_periods) wide frame like the runner CSVs."""
    arr = np.asarray(values, dtype=float)
    index = pd.date_range(start, periods=arr.shape[0], freq="D")
    return pd.DataFrame(arr, index=index,
                        columns=[f"price_p{i}" for i in range(arr.shape[1])])


class TestErrorsMatrix:
    def test_errors_are_actuals_minus_forecasts_aligned(self):
        actuals = _wide([[10.0, 20.0], [30.0, 40.0]])
        forecasts = _wide([[9.0, 22.0], [33.0, 39.0]])
        errors = errors_matrix(forecasts, actuals)
        assert errors.shape == (2, 2)
        np.testing.assert_allclose(errors, [[1.0, -2.0], [-3.0, 1.0]])

    def test_alignment_drops_unmatched_days(self):
        actuals = _wide([[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]])
        forecasts = _wide([[9.0, 22.0], [33.0, 39.0]])  # one day fewer
        errors = errors_matrix(forecasts, actuals)
        assert errors.shape == (2, 2)


class TestBuildHeadlineTable:
    def test_one_row_per_model_plus_naive_with_metric_columns(self):
        actuals = _wide(np.full((14, 2), 50.0))
        runs = {
            "LEAR": _wide(np.full((14, 2), 49.0)),
            "DNN": _wide(np.full((14, 2), 48.0)),
        }
        table = build_headline_table(runs, actuals)
        assert list(table.index) == ["LEAR", "DNN", "Naive (weekly)"]
        for col in ("MAE", "RMSE", "sMAPE", "rMAE"):
            assert col in table.columns
        # constant 1.0 absolute error for LEAR
        assert abs(table.loc["LEAR", "MAE"] - 1.0) < 1e-9


class TestBuildGwTable:
    def test_square_matrix_with_nan_diagonal(self):
        rng = np.random.default_rng(0)
        errors = {
            "LEAR": rng.normal(size=(30, 24)),
            "DNN": rng.normal(size=(30, 24)),
        }
        table = build_gw_table(errors)
        assert table.shape == (2, 2)
        assert np.isnan(table.loc["LEAR", "LEAR"])
        assert 0.0 <= table.loc["LEAR", "DNN"] <= 1.0


class TestToLatexBooktabs:
    def test_contains_booktabs_rules_and_label(self):
        df = pd.DataFrame({"MAE": [1.0]}, index=["LEAR"])
        out = to_latex_booktabs(df, caption="Cap", label="tab:x")
        assert "\\toprule" in out
        assert "\\label{tab:x}" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/scripts/test_extract_model_comparison.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.report.extract_model_comparison'`

- [ ] **Step 3: Implement** — create `scripts/report/extract_model_comparison.py`:

```python
"""Build the modelling-side comparison tables for the report.

Reads the six final runs' outputs from results/ (forecast + actual CSVs),
recomputes metrics and GW p-value matrices, pulls training durations from
algo.experiment_runs, and writes Report/metrics/model_comparison.md with
markdown tables plus LaTeX-ready versions.

Usage:
    uv run python -m scripts.report.extract_model_comparison
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from infrastructure_clickhouse.client_factory import create_client
from price_forecasting.evaluation.summary import (
    build_dm_matrix,
    build_weekly_naive,
    compute_metrics_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
OUTPUT_PATH = REPO_ROOT / "Report" / "metrics" / "model_comparison.md"

MARKETS: dict[str, dict[str, str]] = {
    "DK1": {
        "LEAR": "dk1_lear",
        "DNN": "dk1_dnn",
        "Transformer": "dk1_transformer",
    },
    "DE": {
        "LEAR": "de_lear",
        "DNN": "de_dnn",
        "Transformer": "de_transformer",
    },
}

# Published ensemble rMAE, Lago et al. 2021 Table 3 (Nord Pool / EPEX-DE rows).
# Different test periods (2016-2018) — rankings + rMAE compared, never MAE.
PAPER_RMAE = {
    "DK1": {"LEAR": 0.420, "DNN": 0.407},  # Nord Pool
    "DE": {"LEAR": 0.433, "DNN": 0.374},   # EPEX-DE
}
# Llorente & Portela 2025 Table 5 MAE (ranking evidence only): Transformer
# beats DNN on NP (2.33 vs 3.40) and EPEX-DE (4.03 vs 4.34).


def load_run(experiment_name: str, results_dir: Path = RESULTS_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (forecasts, actuals) wide frames with parsed DatetimeIndex."""
    forecasts = pd.read_csv(
        results_dir / f"{experiment_name}_forecasts.csv", index_col=0, parse_dates=True
    )
    actuals = pd.read_csv(
        results_dir / f"{experiment_name}_actuals.csv", index_col=0, parse_dates=True
    )
    return forecasts, actuals


def errors_matrix(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> np.ndarray:
    """(n_days, n_periods) error array actuals - forecasts on the common index."""
    aligned_actuals, aligned_forecasts = actuals.align(forecasts, join="inner", axis=0)
    return aligned_actuals.to_numpy(dtype=float) - aligned_forecasts.to_numpy(dtype=float)


def build_headline_table(
    forecasts_by_model: dict[str, pd.DataFrame], actuals: pd.DataFrame
) -> pd.DataFrame:
    """MAE / RMSE / sMAPE / rMAE per model, plus the weekly-naive row."""
    naive = build_weekly_naive(actuals)
    rows: dict[str, dict[str, float]] = {}
    for model_name, forecasts in forecasts_by_model.items():
        metrics = compute_metrics_summary(forecasts, actuals, naive)
        rows[model_name] = {
            "MAE": metrics["mae"],
            "RMSE": metrics["rmse"],
            "sMAPE": metrics["smape"],
            "rMAE": metrics["rmae"],
        }
    naive_metrics = compute_metrics_summary(naive, actuals, naive)
    rows["Naive (weekly)"] = {
        "MAE": naive_metrics["mae"],
        "RMSE": naive_metrics["rmse"],
        "sMAPE": naive_metrics["smape"],
        "rMAE": naive_metrics["rmae"],
    }
    return pd.DataFrame(rows).T[["MAE", "RMSE", "sMAPE", "rMAE"]]


def build_gw_table(errors_by_model: dict[str, np.ndarray]) -> pd.DataFrame:
    """Pairwise GW p-value matrix (column model better than row model)."""
    return build_dm_matrix(errors_by_model, norm=1)


def fetch_training_durations(experiment_names: list[str]) -> dict[str, float]:
    """Latest tracked training_duration_seconds per experiment from ClickHouse."""
    client = create_client()
    try:
        result = client.query(
            "SELECT experiment_name, argMax(training_duration_seconds, created_utc) "
            "FROM algo.experiment_runs FINAL "
            "WHERE experiment_name IN {names:Array(String)} "
            "GROUP BY experiment_name",
            parameters={"names": experiment_names},
        )
        return {row[0]: float(row[1]) for row in result.result_rows}
    finally:
        client.close()


def to_latex_booktabs(table: pd.DataFrame, caption: str, label: str) -> str:
    body = table.to_latex(float_format="%.3f", na_rep="--")
    return (
        "\\begin{table}[h]\n  \\centering\n"
        f"  \\caption{{{caption}}}\n  \\label{{{label}}}\n"
        f"{body}"
        "\\end{table}\n"
    )


def main() -> None:
    sections: list[str] = ["# Model comparison — final benchmark\n"]
    sections.append(
        "Generated by `scripts/report/extract_model_comparison.py`. "
        "Test window 2025-10-24 → 2026-05-31, all six runs paired.\n"
    )
    all_experiments = [
        exp for market in MARKETS.values() for exp in market.values()
    ]
    durations = fetch_training_durations(all_experiments)

    for market, experiments in MARKETS.items():
        forecasts_by_model: dict[str, pd.DataFrame] = {}
        errors_by_model: dict[str, np.ndarray] = {}
        actuals_ref: pd.DataFrame | None = None
        for model_name, experiment_name in experiments.items():
            forecasts, actuals = load_run(experiment_name)
            forecasts_by_model[model_name] = forecasts
            errors_by_model[model_name] = errors_matrix(forecasts, actuals)
            actuals_ref = actuals

        naive = build_weekly_naive(actuals_ref)
        errors_by_model["Naive (weekly)"] = errors_matrix(naive, actuals_ref)

        headline = build_headline_table(forecasts_by_model, actuals_ref)
        gw = build_gw_table(errors_by_model)

        n_days = len(errors_by_model["LEAR"])
        duration_rows = {
            model_name: durations.get(experiment_name, float("nan")) / n_days
            for model_name, experiment_name in experiments.items()
        }
        cost = pd.DataFrame.from_dict(
            duration_rows, orient="index", columns=["seconds/recalibration-day"]
        )

        paper = pd.DataFrame.from_dict(
            PAPER_RMAE[market], orient="index", columns=["paper rMAE (Lago T3)"]
        )
        paper["ours rMAE"] = headline["rMAE"]

        sections.append(f"\n## {market}\n")
        sections.append("### Headline metrics\n")
        sections.append(headline.round(3).to_markdown() + "\n")
        sections.append("### GW p-values (column better than row)\n")
        sections.append(gw.round(4).to_markdown() + "\n")
        sections.append("### Computation cost\n")
        sections.append(cost.round(1).to_markdown() + "\n")
        sections.append("### vs published benchmarks (rMAE; periods differ — rankings only)\n")
        sections.append(paper.round(3).to_markdown() + "\n")

        sections.append("### LaTeX\n```latex\n")
        sections.append(
            to_latex_booktabs(
                headline.round(3),
                caption=f"{market}: final benchmark metrics (test 2025-10-24--2026-05-31).",
                label=f"tab:results-{market.lower()}-headline",
            )
        )
        sections.append(
            to_latex_booktabs(
                gw.round(4),
                caption=f"{market}: GW multivariate p-values (column better than row).",
                label=f"tab:results-{market.lower()}-gw",
            )
        )
        sections.append("```\n")

    OUTPUT_PATH.write_text("\n".join(sections))
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/scripts/test_extract_model_comparison.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit code**

```bash
git add scripts/report/extract_model_comparison.py tests/scripts/test_extract_model_comparison.py
git commit -m "feat(report): model-comparison table extraction script"
```

- [ ] **Step 6 (after Tasks 5, 8, 9 complete): Generate and commit the artifact**

```bash
uv run python -m scripts.report.extract_model_comparison
git add Report/metrics/model_comparison.md
git commit -m "docs(report): pin final model-comparison tables"
```

Expected: `Report/metrics/model_comparison.md` has both market sections, 4×4 headline tables, 4×4 GW matrices, cost and paper-comparison tables. Eyeball: rMAE < 1 for at least LEAR; GW diagonal NaN.

---

## Task 11: Bibliography entries

**Files:**
- Modify: `Report/references.bib`

- [ ] **Step 1: Append the four missing entries**

```bibtex
@article{llorente2025transformer,
  author  = {Llorente, Jes{\'u}s and Portela, Jos{\'e}},
  title   = {A Transformer Approach for Electricity Price Forecasting},
  journal = {arXiv preprint arXiv:2403.16108},
  year    = {2025},
}

@article{uniejewski2018vst,
  author  = {Uniejewski, Bartosz and Weron, Rafa{\l} and Ziel, Florian},
  title   = {Variance Stabilizing Transformations for Electricity Spot Price Forecasting},
  journal = {IEEE Transactions on Power Systems},
  volume  = {33},
  number  = {2},
  pages   = {2219--2229},
  year    = {2018},
  doi     = {10.1109/TPWRS.2017.2734563},
}

@article{diebold1995dm,
  author  = {Diebold, Francis X. and Mariano, Roberto S.},
  title   = {Comparing Predictive Accuracy},
  journal = {Journal of Business \& Economic Statistics},
  volume  = {13},
  number  = {3},
  pages   = {253--263},
  year    = {1995},
}

@article{giacomini2006gw,
  author  = {Giacomini, Raffaella and White, Halbert},
  title   = {Tests of Conditional Predictive Ability},
  journal = {Econometrica},
  volume  = {74},
  number  = {6},
  pages   = {1545--1578},
  year    = {2006},
}
```

- [ ] **Step 2: Commit**

```bash
git add Report/references.bib
git commit -m "docs(report): add Llorente, Uniejewski VST, DM and GW citations"
```

---

## Task 12: Methods chapter scaffold (`ch:methods-models`)

**Files:**
- Create: `Report/chapters/methods_models_draft.tex`
- Create: `Report/methods_models_draft_standalone.tex`

The existing scaffolds (`evaluation_framework_draft.tex`) already `\ref{ch:methods-models}` — this task creates the label they point to. Follow the repo's structure-first draft convention (tables + bullets, not prose).

- [ ] **Step 1: Create `Report/chapters/methods_models_draft.tex`**

```latex
% =============================================================================
% DRAFT SCAFFOLD — Methods: Forecasting Models & Evaluation (modelling part)
% Structure-first. Tables + bullets; expand bullets into prose later.
% Source of pinned setup values: configs/*.py on this branch +
% docs/superpowers/specs/2026-06-04-final-model-experiments-and-report-design.md
% =============================================================================

\chapter{Methods --- Forecasting Models and Evaluation}
\label{ch:methods-models}

% -----------------------------------------------------------------------------
\section{Replication framing}
\label{sec:mm-framing}

\begin{itemize}
  \item One paragraph: methodology replicated from \cite{lago2021} (LEAR, DNN)
        and \cite{llorente2025transformer} (Transformer) on current market data;
        absolute errors are not comparable across periods, so comparison uses
        rMAE and model rankings (\cite{lago2021} \S5.4).
  \item State the three models and two markets; all six runs share one test
        window so DM/GW tests are paired.
\end{itemize}

% -----------------------------------------------------------------------------
\section{Data and features}
\label{sec:mm-data}

\begin{table}[h]
  \centering
  \caption{Datasets. Both markets span 2022-03-10 to 2026-05-31 (ENTSO-E).}
  \label{tab:mm-datasets}
  \begin{tabularx}{\linewidth}{@{}l l l X@{}}
    \toprule
    \textbf{Market} & \textbf{Resolution} & \textbf{Exogenous (paper-exact)} & \textbf{Paper analogue} \\
    \midrule
    DK1 & hourly (24)   & TotalLoad + Wind (on+offshore)        & Nord Pool: load + wind~\cite{lago2021} \\
    DE  & 15-min (96)   & TotalLoad + Renewables (wind+solar)   & EPEX-DE: load + wind\&solar~\cite{lago2021} \\
    \bottomrule
  \end{tabularx}
\end{table}

\begin{itemize}
  \item Feature set per \cite{lago2021} Eq.~3: price lags $d{-}1,d{-}2,d{-}3,d{-}7$;
        exogenous at $d0,d{-}1,d{-}7$; 7 day-of-week dummies
        ($4n + 2\cdot3n + 7$; $n{=}24 \Rightarrow 247$, $n{=}96 \Rightarrow 967$).
  \item Aggregation: raw ENTSO-E wind/solar curves summed at load time
        (\texttt{exogenous\_aggregates}); inner-join on member timestamps.
  \item Variance stabilisation: asinh transform~\cite{uniejewski2018vst}.
  \item Resolution note: DK1 day-ahead moved to 15-min on 2025-10-01; the
        pipeline anchors on the hourly load forecast grid, so DK1 prices are
        the hourly samples of the 15-min curve --- internally consistent for
        all models and the naive baseline.
\end{itemize}

% -----------------------------------------------------------------------------
\section{Models}
\label{sec:mm-models}

\begin{table}[h]
  \centering
  \caption{Model setups (one row per model; identical across both markets unless noted).}
  \label{tab:mm-models}
  \begin{tabularx}{\linewidth}{@{}l X X l@{}}
    \toprule
    \textbf{Model} & \textbf{Spec} & \textbf{Calibration} & \textbf{Refit} \\
    \midrule
    LEAR        & One Lasso per delivery period; $\lambda$ by \texttt{LassoCV} (time-series CV) & ensemble over 56/84/1092\,d & daily \\
    DNN         & MLP, 4-seed ensemble; architecture HPs by Optuna TPE (50 trials, ex-ante val) & 730\,d & daily \\
    Transformer & Encoder stack per \cite{llorente2025transformer}; paper NP hyperparameters & 1092\,d (DE: see note) & weekly \\
    \bottomrule
  \end{tabularx}
\end{table}

\begin{itemize}
  \item Tuning protocol: validation window 2025-01-01 to 2025-10-23 (42 weeks,
        immediately preceding the test window; \cite{lago2021} \S4.3.2);
        trials persisted to \texttt{algo.hyperparam\_trials}.
  \item DE Transformer calibration window: state the measured usable-row count
        and final window from the config comment.
\end{itemize}

% -----------------------------------------------------------------------------
\section{Evaluation protocol}
\label{sec:mm-eval}

\begin{itemize}
  \item Test window 2025-10-24 to 2026-05-31 (220 days), identical for all six
        runs; training data = everything before test start (\cite{lago2021} \S5.7).
  \item Metrics: MAE, RMSE, sMAPE, rMAE with weekly-naive
        (\cite{lago2021} \S5.4); rMAE is the headline metric.
  \item Statistical testing: multivariate GW on daily $L^1$ loss differentials
        with Newey--West HAC errors~\cite{giacomini2006gw,lago2021}; pairwise
        DM~\cite{diebold1995dm} as univariate complement.
  \item Computation cost: training seconds per recalibration day, from
        \texttt{algo.experiment\_runs} (analogue of \cite{lago2021} Table~4).
\end{itemize}

% -----------------------------------------------------------------------------
\section{Deviations from the source papers}
\label{sec:mm-deviations}

\begin{table}[h]
  \centering
  \caption{Documented deviations from \cite{lago2021} and \cite{llorente2025transformer}.}
  \label{tab:mm-deviations}
  \begin{tabularx}{\linewidth}{@{}l X X@{}}
    \toprule
    \textbf{Aspect} & \textbf{Paper} & \textbf{This work (reason)} \\
    \midrule
    Test length            & $\geq$ 1--2 years            & 31 weeks (price history starts 2022-03; val + calibration consume the rest) \\
    DNN tuning budget      & 1500 TPE iterations          & 50 trials (compute; optimum stable early in prior studies) \\
    DNN search space       & architecture + feature selectors & architecture only (feature set fixed to paper spec) \\
    LEAR windows           & 56/84/1092/1456\,d           & 56/84/1092\,d (1456 predates data) \\
    DNN window             & 4 years                      & 730\,d (data/compute constraint) \\
    $\lambda$ selection    & LARS + AIC                   & \texttt{LassoCV} time-series CV (standard, equivalent accuracy) \\
    DK1 resolution         & hourly market                & hourly samples of 15-min curve after 2025-10-01 \\
    Transformer pipeline   & train-once + renormalise     & calibration window + weekly refit (pipeline consistency) \\
    Transformer HPs        & tuned per dataset            & paper NP optimum reused (future work) \\
    \bottomrule
  \end{tabularx}
\end{table}

% =============================================================================
% END DRAFT
% =============================================================================
```

- [ ] **Step 2: Create `Report/methods_models_draft_standalone.tex`** (mirrors `results_system_draft_standalone.tex`):

```latex
% Standalone wrapper to render `chapters/methods_models_draft.tex` as a PDF.
% Mirrors `results_system_draft_standalone.tex`. Cross-chapter refs appear
% as `??` in the standalone proof; that is expected.
\documentclass[11pt,a4paper]{report}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=2.5cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{array}
\usepackage{tabularx}
\usepackage{hyperref}
\usepackage{microtype}

\setlength{\emergencystretch}{3em}
\hyphenpenalty=1000
\tolerance=1000

\begin{document}

\tableofcontents
\clearpage

\input{chapters/methods_models_draft}

\bibliographystyle{plain}
\bibliography{references}

\end{document}
```

- [ ] **Step 3: Compile check**

```bash
cd Report && latexmk -pdf -interaction=nonstopmode methods_models_draft_standalone.tex && cd ..
```

Expected: `methods_models_draft_standalone.pdf` produced; warnings about `??` cross-refs to other chapters are fine; zero LaTeX errors.

- [ ] **Step 4: Commit**

```bash
git add Report/chapters/methods_models_draft.tex Report/methods_models_draft_standalone.tex
git commit -m "docs(report): scaffold methods chapter for forecasting models"
```

---

## Task 13: Results chapter scaffold (`ch:results-models`) + cross-ref check

**Files:**
- Create: `Report/chapters/results_models_draft.tex`
- Create: `Report/results_models_draft_standalone.tex`

**Requires Task 10 Step 6** (numbers pinned from `Report/metrics/model_comparison.md`).

- [ ] **Step 1: Create `Report/chapters/results_models_draft.tex`** — same scaffold conventions; pin the real numbers from `Report/metrics/model_comparison.md` into the tables (the generated file contains ready LaTeX blocks for the headline and GW tables — paste them in):

```latex
% =============================================================================
% DRAFT SCAFFOLD — Results: Forecasting Models (modelling part)
% Numbers pinned from Report/metrics/model_comparison.md (generated by
% scripts/report/extract_model_comparison.py) — paste its LaTeX blocks in.
% =============================================================================

\chapter{Results --- Forecasting Models}
\label{ch:results-models}

% -----------------------------------------------------------------------------
\section{Headline accuracy}
\label{sec:rm-headline}

\begin{itemize}
  \item Two tables (one per market) — paste \texttt{tab:results-dk1-headline}
        and \texttt{tab:results-de-headline} LaTeX blocks from
        \texttt{model\_comparison.md}.
  \item Bullets: which model wins on rMAE per market; do ensembles beat naive
        (rMAE $<$ 1) everywhere?
\end{itemize}

% PASTE: tab:results-dk1-headline
% PASTE: tab:results-de-headline

% -----------------------------------------------------------------------------
\section{Statistical significance}
\label{sec:rm-significance}

\begin{itemize}
  \item Two GW matrices — paste \texttt{tab:results-dk1-gw} and
        \texttt{tab:results-de-gw}; read as: cell $(r,c)$ = p-value that
        column model beats row model (\cite{lago2021} Fig.~5 convention).
  \item Bullets: which differences are significant at 0.05; which are not —
        echo \cite{lago2021}'s finding that better MAE is not always significant.
\end{itemize}

% PASTE: tab:results-dk1-gw
% PASTE: tab:results-de-gw

% -----------------------------------------------------------------------------
\section{Computation cost}
\label{sec:rm-cost}

\begin{itemize}
  \item Table: seconds per recalibration day per model per market (from
        \texttt{model\_comparison.md}); compare against \cite{lago2021}
        Table~4 (LEAR seconds vs DNN minutes).
\end{itemize}

% -----------------------------------------------------------------------------
\section{Comparison with published benchmarks}
\label{sec:rm-papers}

\begin{itemize}
  \item Caveat first: different test periods and price regimes (2016--2018 vs
        2025--2026); rMAE and rankings are the valid comparison
        (\cite{lago2021} \S5.4).
  \item Table: ours-vs-paper rMAE (from \texttt{model\_comparison.md});
        bullets on whether the papers' ranking (DNN $>$ LEAR in
        \cite{lago2021}; Transformer $>$ DNN in
        \cite{llorente2025transformer}) reproduces on current data.
\end{itemize}

% -----------------------------------------------------------------------------
\section{Threats to validity (modelling side)}
\label{sec:rm-validity}

\begin{itemize}
  \item 31-week test window (vs the papers' 1--2 years); single run per
        DNN/Transformer config (seed variance partially mitigated by the
        4-seed DNN ensemble); 2025--2026 regime includes negative-price and
        high-renewables days unseen in the papers' data.
  \item Cross-reference the deviations table (Ch.~\ref{ch:methods-models},
        Table~\ref{tab:mm-deviations}).
\end{itemize}

% -----------------------------------------------------------------------------
\section{Future work (modelling side)}
\label{sec:rm-future}

\begin{itemize}
  \item 1456\,d window once data depth allows; LARS+AIC; Transformer
        per-market tuning; probabilistic extension (pinball/CRPS); per-hour
        DM profiles.
\end{itemize}

% =============================================================================
% END DRAFT
% =============================================================================
```

- [ ] **Step 2: Create `Report/results_models_draft_standalone.tex`** — identical to Task 12 Step 2's wrapper with `\input{chapters/results_models_draft}`.

- [ ] **Step 3: Verify cross-references resolve across the report**

```bash
grep -rn "ch:methods-models\|ch:results-models" Report/chapters/*.tex
```

Expected: `\label{ch:methods-models}` (methods draft) and `\label{ch:results-models}` (results draft) exist; every `\ref` to them in `evaluation_framework_draft.tex` / `results_system_draft.tex` now has a target.

- [ ] **Step 4: Compile check**

```bash
cd Report && latexmk -pdf -interaction=nonstopmode results_models_draft_standalone.tex && cd ..
```

Expected: PDF builds, zero LaTeX errors.

- [ ] **Step 5: Commit**

```bash
git add Report/chapters/results_models_draft.tex Report/results_models_draft_standalone.tex
git commit -m "docs(report): scaffold results chapter for forecasting models"
```

---

## Task 14: Scorecard refresh, full verification, PR

**Files:**
- Modify: `researh_material/reading_guides/lago_epf_benchmark_reading_guide.md`

- [ ] **Step 1: Refresh the Lago checklist scorecard** — in the reading guide: checklist row #2 changes from **PARTIAL** to **PASS** with details "LEAR vs DNN vs Transformer benchmarked head-to-head on DK1+DE with GW tests (see Report/metrics/model_comparison.md)"; update the score line to `13 PASS, 0 PARTIAL, 0 FAIL`; update the "Last refreshed" date line; rewrite the "What's Missing / Gap Analysis" row for the DNN benchmark as closed.

- [ ] **Step 2: Run the full test suite and linter**

```bash
uv run python -m pytest tests/ -v 2>&1 | tail -5
uv run ruff check .
```

Expected: all tests pass; ruff clean.

- [ ] **Step 3: Commit and push**

```bash
git add researh_material/reading_guides/lago_epf_benchmark_reading_guide.md
git commit -m "docs: Lago checklist #2 PARTIAL -> PASS (head-to-head benchmark published)"
git push -u origin final-model-experiments
```

- [ ] **Step 4: Open the PR**

```bash
gh pr create --title "Final model benchmark: paper-exact features, aligned test window, modelling-side report chapters" --body "$(cat <<'EOF'
## Summary
- Wind/solar history backfilled to 2022-03; config-driven exogenous aggregation (paper-exact features: DK1 load+wind, DE load+renewables)
- All six configs aligned on test window 2025-10-24 → 2026-05-31; DNNs re-tuned on the new features
- Six tracked backtests (LEAR/DNN/Transformer × DK1/DE); comparison tables in Report/metrics/model_comparison.md
- New report chapters: methods (ch:methods-models) + results (ch:results-models)

## Production note
Merging changes the deployed daily-forecast configs: exogenous features become the paper-exact aggregates (intended).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed; CI (pytest + ruff + smoke) green.

---

## Self-review checklist (done at plan-writing time)

- **Spec coverage:** Phase 1 → Task 1; Phase 2 → Tasks 2–4; Phase 3 → Task 5; Phase 4 → Tasks 6–7; Phase 5 → Tasks 8–9; Phase 6 → Task 10; Phase 7 → Tasks 11–13; Phase 8 → Task 14. Spec §8 risks: backfill stop-condition in Task 1 Step 4; DE-window fallback in Task 4 Step 7; runtime staging in the scheduling note; production note in Task 14 Step 4.
- **Placeholders:** Task 6/7 Step 3 `<...>` markers are deliberate run-time values from the tuning study, with explicit fill instructions — not plan gaps.
- **Type consistency:** `exogenous_aggregates: Dict[str, List[str]]` (Task 2) matches loader param `aggregates: dict[str, list[str]] | None` (Task 3) and config usage (Task 4); `exogenous_columns` property name consistent between Tasks 2, 3 (preprocessor), and 4 (transformer `_EXOG` lists match aggregate names "Wind"/"Renewables").
