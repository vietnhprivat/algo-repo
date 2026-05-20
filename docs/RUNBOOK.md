# Runbook

## Alerts

### `Drift detected on <area>`

1. Open Grafana → Model Performance dashboard, filter to the area.
2. Inspect Price Drift Score (30d) panel — is this a slow trend or a spike?
3. Check `algo.drift_reports`: `SELECT * FROM algo.drift_reports FINAL ORDER BY created_utc DESC LIMIT 10`.
4. If `retrain_on_drift=True` on the config, retrain has already been queued — check `algo.retrain_events`.
5. If the alert recurs daily, raise `REFERENCE_DAYS` in `drift.py` or open an investigation.

### `Accuracy degradation on <area> (<config>)`

1. Check `algo.experiment_runs` for the latest run's MAE vs the 30-day median.
2. Compare today's input data to the recent baseline (holiday, extreme weather, ENTSO-E correction).
3. If sustained 3+ days, trigger a manual retrain:

```bash
python -c "from schedules.retrain import triggered_retrain_flow; triggered_retrain_flow(config_name='<cfg>', triggered_by='manual', area='<area>')"
```

### `Curve freshness > 12h`

1. Check ENTSO-E transparency platform status: <https://transparency.entsoe.eu/>
2. Check `algo.timeseries`:

```sql
SELECT curve_name, max(timestamp_utc) FROM algo.timeseries FINAL GROUP BY curve_name
```

3. Inspect ingestion flow logs in Grafana → Operational dashboard.
4. If ENTSO-E is up, retrigger ingestion for the area:

```bash
python -c "from schedules.ingestion import entsoe_backfill_flow; entsoe_backfill_flow(area='<XX>')"
```

### `No reconciliation in 36h`

1. Likely cause: reconciliation flow failed or got skipped.
2. Inspect Prefect → Deployments → `reconcile-predictions` → most recent runs.
3. Manually re-run:

```bash
python -c "from schedules.reconciliation import reconcile_predictions_flow; reconcile_predictions_flow()"
```

## Manual operations

### Backfill data

```bash
uv run python -m data_cli.main entsoe backfill price-document -a DK1 -s 2024-01-01 -e 2026-05-19
```

### Re-tune a DNN config

```bash
uv run python -m forecast_cli.main tune dk1_dnn --n-trials 100
```

Paste the best params into `configs/dk1_dnn.py` `model_params` and commit.

### Force ClickHouse dedup

```sql
OPTIMIZE TABLE algo.timeseries FINAL;
OPTIMIZE TABLE algo.forecasts FINAL;
```

## Common pitfalls

- Editing an existing migration: don't. Add a new one.
- Editing Grafana dashboards through the UI: changes are lost on restart. Edit the JSON in `grafana/dashboards/`.
- Asinh transform breaks if `AsinhScaler` isn't fit before inverse — make sure `fit_transform` runs on the training targets.
- DNN HPs returned by Optuna search may include keys the model class doesn't accept (`use_price_d_*`, `preprocessing`, `init_method`); the objective filters these. When pasting tuned params into a config, keep only the architecture HPs that `DNNModel.__init__` and `LightningModel.__init__` actually consume.
