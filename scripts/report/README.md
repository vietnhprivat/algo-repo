# Report figure & metric policy

The thesis chapter `Report/chapters/system_implementation.tex` pulls numbers
and figures from two sources. This document records the policy so future
edits stay consistent.

## Where each figure comes from

| Figure / number | Source | Why |
|---|---|---|
| Training loss / val-loss curves | W&B export (`algo-research`) | The W&B run already stores per-epoch series; re-deriving in matplotlib duplicates effort. |
| Hyperparameter-sweep parallel-coordinate plots | W&B export (`algo-research`) | W&B's HP plot is the canonical view of a sweep. |
| Ablation comparison charts (`forecast-cli ablate`) | W&B export (`algo-research`) | Each ablation variant is a sibling run; W&B group-by handles it natively. |
| Reconciled production accuracy time-series | W&B export (`algo-prod`, run `prod-{area}-{config}`) | The continuous run is the source of truth post-spec. |
| Architecture diagrams (`f1-arch`, `f2-flows`, `f3-cicd`) | Hand-built (Excalidraw / TikZ) | Static, not derived from a run. |
| Headline number tables (§5 Quantitative Evaluation) | `scripts/report/extract_metrics.py` → `Report/metrics/quantitative_results.md` | Reproducible from ClickHouse + Prometheus on demand. |
| DM / GW p-value matrix | Hand-built matplotlib in `scripts/report/` (or future module) | Cross-model comparison, derived from `algo.experiment_predictions`. |
| System availability table (§5.2) | `scripts/report/extract_metrics.py:collect_availability` (Prometheus) | Reproducible. |

## Rule of thumb

- If a figure compares **two or more runs** (sweeps, ablations, model A vs model B), it comes from W&B.
- If a figure is a **single static artifact** (architecture diagram, headline number table, p-value matrix), it comes from a matplotlib script under `scripts/report/` (or is hand-built).

## Disabled W&B

When `WANDB_MODE=disabled` (local development), W&B-sourced figures are not
regenerated. The PDF in `main` always ships with the last committed
W&B exports; CI does not re-render them. If a W&B export is updated, commit
the new PNG / PDF alongside the chapter edit that references it.

## Related

- `Report/chapters/system_implementation.tex` — the chapter consuming these figures.
- `docs/REPO_OVERVIEW.md` §11 — the framework these figures support.
- `docs/superpowers/specs/2026-05-25-observability-split-design.md` — the spec that established this policy.
