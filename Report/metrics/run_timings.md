# Run timings — final benchmark

Hardware: NVIDIA RTX 3060 GPU, 16 CPU cores. Backtest wall-clock is the full rolling-window run (all refits), read from `algo.experiment_runs.training_duration_seconds` (persisted by `forecast-cli backtest --track`). Tuning timings are from `results/run_timings.log`.

## Backtests

| Experiment | Model | Resolution | Refit | Window(s) | Ensemble | Wall-clock | Seconds |
|---|---|---|---|---|---|---|---|
| dk1_lear | lear | hourly (24) | daily | 56/84/1092 | 1 | 2:36:43 | 9403 |
| de_lear | lear | hourly (24, from 15-min) | daily | 56/84/1092 | 1 | 2:01:01 | 7261 |
| dk1_dnn | dnn | hourly (24) | daily | 730 | 4 | 2:54 | 174 |
| de_dnn | dnn | hourly (24, from 15-min) | daily | 730 | 4 | 4:43 | 283 |
| dk1_transformer | transformer | hourly (24) | weekly | 1092 | 1 | 5:04 | 304 |
| de_transformer | transformer | hourly (24, from 15-min) | weekly | 1092 | 1 | 5:35 | 335 |


## Tuning and other timed steps

| Label | Start | End | Wall-clock |
|---|---|---|---|
| backtest:dk1_lear | 2026-06-04T13:32:50+02:00 | 2026-06-04T16:09:46+02:00 | 2:36:56 |
| backtest:de_lear | 2026-06-04T16:09:46+02:00 | 2026-06-04T18:10:53+02:00 | 2:01:07 |
| tune:dk1_dnn(30,contended) | 2026-06-04T13:33:00+02:00 | 2026-06-04T19:24:00+02:00 | 5:51:00 |
| tune:de_dnn(30) | 2026-06-04T19:27:29+02:00 | 2026-06-05T01:00:03+02:00 | 5:32:34 |
| backtest:dk1_dnn | 2026-06-05T01:00:50+02:00 | 2026-06-05T01:03:48+02:00 | 2:58 |
| backtest:de_dnn | 2026-06-05T01:03:48+02:00 | 2026-06-05T01:08:34+02:00 | 4:46 |
| backtest:dk1_transformer | 2026-06-05T01:08:34+02:00 | 2026-06-05T01:13:41+02:00 | 5:07 |
| backtest:de_transformer | 2026-06-05T01:13:41+02:00 | 2026-06-05T01:19:19+02:00 | 5:38 |


## Notes

- All runs are modelled at hourly resolution (24 periods); the 15-min DE and post-2025-10 DK1 prices are downsampled to an hourly mean, so both markets fit the same number of per-period Lasso models.

- DNN and Transformer are MIMO (one GPU network for all periods); the Transformer refits weekly, so its run is dominated by ~32 trainings.

- Single-refit GPU probe (2026-06-04): dk1_dnn 4-net ensemble ~10s; dk1_transformer ~17s.
