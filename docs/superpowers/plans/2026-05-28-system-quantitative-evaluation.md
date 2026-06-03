# System Quantitative Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the over-claiming §5.2 "Quantitative evaluation" of the System Implementation chapter with a defensible, honestly-scoped system evaluation: ML Test Score, a reproducibility coverage number + a live re-run demonstration, DORA delivery *throughput only*, and a drift-as-monitoring discussion — backed by real measurements from code, git, and ClickHouse.

**Architecture:** Three artifacts feed the chapter. (1) `scripts/report/extract_metrics.py` is trimmed to drop the indefensible availability and change-failure-rate metrics and keep operational/reproducibility/DORA-throughput numbers. (2) A new `scripts/report/reproduce_run.py` re-runs a logged forecast and reports the max absolute difference from the stored prediction. (3) A new `Report/metrics/ml_test_score.md` worksheet records the 28-item self-audit. The chapter's §5.2 is rewritten to transcribe these, framed as a single-case study, and the availability + CFR tables are deleted.

**Tech Stack:** Python (clickhouse-connect, numpy, pandas), pytest, LaTeX (booktabs, tabularx), BibTeX, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-05-28-system-quantitative-evaluation-design.md`

**Scope notes:**
- Part 1 (forecasting-model accuracy) is a *separate* chapter and is **out of scope** here.
- No simulation/replay. Every number comes from code, git/CI, or a short experiment.
- `references.bib` already contains `google_mlops_maturity` and `zarour2025` — do not re-add them.

---

## Task 1: Add the six bibliography entries

**Files:**
- Modify: `Report/references.bib`

- [ ] **Step 1: Append the six entries at the end of the file**

Open `Report/references.bib` and append:

```bibtex
@article{runeson2009casestudy,
  author  = {Runeson, Per and H{\"o}st, Martin},
  title   = {Guidelines for conducting and reporting case study research in software engineering},
  journal = {Empirical Software Engineering},
  volume  = {14},
  number  = {2},
  pages   = {131--164},
  year    = {2009},
  doi     = {10.1007/s10664-008-9102-8}
}

@inproceedings{breck2017mltestscore,
  author    = {Breck, Eric and Cai, Shanqing and Nielsen, Eric and Salib, Michael and Sculley, D.},
  title     = {The {ML} Test Score: A Rubric for {ML} Production Readiness and Technical Debt Reduction},
  booktitle = {2017 IEEE International Conference on Big Data (Big Data)},
  pages     = {1123--1132},
  year      = {2017},
  doi       = {10.1109/BigData.2017.8258038}
}

@inproceedings{gundersen2018reproducibility,
  author    = {Gundersen, Odd Erik and Kjensmo, Sigbj{\o}rn},
  title     = {State of the Art: Reproducibility in Artificial Intelligence},
  booktitle = {Proceedings of the AAAI Conference on Artificial Intelligence},
  volume    = {32},
  number    = {1},
  year      = {2018},
  doi       = {10.1609/aaai.v32i1.11503}
}

@book{forsgren2018accelerate,
  author    = {Forsgren, Nicole and Humble, Jez and Kim, Gene},
  title     = {Accelerate: The Science of Lean Software and DevOps},
  publisher = {IT Revolution Press},
  year      = {2018}
}

@article{mahadevan2024costaware,
  author  = {Mahadevan, Ananth and Mathioudakis, Michael},
  title   = {Cost-aware retraining for machine learning},
  journal = {Knowledge-Based Systems},
  volume  = {293},
  pages   = {111610},
  year    = {2024},
  doi     = {10.1016/j.knosys.2024.111610}
}

@article{subramanya2022devops2mlops,
  author  = {Subramanya, Rakshith and Sierla, Seppo and Vyatkin, Valeriy},
  title   = {From {DevOps} to {MLOps}: Overview and Application to Electricity Market Forecasting},
  journal = {Applied Sciences},
  volume  = {12},
  number  = {19},
  pages   = {9851},
  year    = {2022},
  doi     = {10.3390/app12199851}
}
```

- [ ] **Step 2: Verify the bib file still parses**

Run from the repo root:

```bash
cd Report && pdflatex -interaction=batchmode system_implementation_standalone.tex >/dev/null 2>&1; bibtex system_implementation_standalone 2>&1 | tail -5; cd ..
```

Expected: bibtex reports no "I couldn't open" / "I was expecting" errors about the new entries. (Undefined-citation warnings are fine at this stage — the citations are added in Task 5.)

- [ ] **Step 3: Commit**

```bash
git add Report/references.bib
git commit -m "docs(report): add system-evaluation bibliography entries"
```

---

## Task 2: Trim extract_metrics.py — drop availability + change-failure-rate

**Files:**
- Modify: `scripts/report/extract_metrics.py`

This removes the two indefensible metric families (passive Prometheus availability; DORA change-failure-rate / failed-deploy counts) and keeps operational, reproducibility-coverage, DORA-throughput, and drift-count numbers.

- [ ] **Step 1: Remove the availability collector and its wiring**

Delete the entire `collect_availability` function (lines defining `def collect_availability(...)` through its `return {...}` block).

In the module docstring, delete the line:
```
  - Prometheus (availability / uptime)
```

Remove the now-unused imports at the top — delete these two lines:
```python
import os
```
```python
import httpx
```

In the `MetricsReport` dataclass, delete the field:
```python
    availability: dict[str, Any] = field(default_factory=dict)
```

In `main()`, delete the line:
```python
    report.availability = collect_availability(WINDOW_DAYS)
```

- [ ] **Step 2: Reduce `collect_dora` to throughput only**

Replace the entire body of `collect_dora` (everything after the docstring) with:

```python
    # Definition: a "deployment" is a successful cd_deploy.yml run on main.
    # DORA THROUGHPUT ONLY: deployment frequency + lead time. Change failure
    # rate and MTTR are intentionally NOT computed — they require an incident
    # corpus the study window does not provide (see spec / chapter prose).
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    raw = subprocess.run(
        [
            "gh", "run", "list",
            "--workflow", "cd_deploy.yml",
            "--branch", "main",
            "--limit", "200",
            "--created", f">={since}",
            "--json", "conclusion,startedAt,createdAt,headSha",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    runs = json.loads(raw.stdout)
    if len(runs) == 200:
        print(
            "WARNING: gh run list returned exactly 200 rows — the limit may "
            "have been hit. DORA numbers below may be truncated.",
            file=sys.stderr,
        )
    successes = [r for r in runs if r["conclusion"] == "success"]
    deploy_freq_per_week = round(7 * len(successes) / window_days, 2) if window_days else None

    lead_times_minutes: list[float] = []
    for r in successes:
        sha = r["headSha"]
        try:
            ts = subprocess.run(
                ["git", "show", "-s", "--format=%cI", sha],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            continue
        if not ts:
            continue
        commit_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        run_dt = datetime.fromisoformat(r["startedAt"].replace("Z", "+00:00"))
        lead_times_minutes.append((run_dt - commit_dt).total_seconds() / 60.0)
    lead_times_minutes.sort()

    def pct(xs: list[float], q: float) -> float | None:
        if not xs:
            return None
        idx = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
        return round(xs[idx], 1)

    return {
        "window_days": window_days,
        "deployments_success": len(successes),
        "deploy_frequency_per_week": deploy_freq_per_week,
        "lead_time_minutes_p50": pct(lead_times_minutes, 0.5),
        "lead_time_minutes_p95": pct(lead_times_minutes, 0.95),
    }
```

- [ ] **Step 3: Simplify `collect_feedback_loop` to drift counts only**

The drift-to-retrain latency is no longer reported (we argue drift is not a retrain trigger). Replace the entire body of `collect_feedback_loop` (after the docstring) with:

```python
    drift_row = client.query(
        """
        SELECT
            count() AS reports,
            countIf(drift_detected = 1) AS detections
        FROM algo.drift_reports FINAL
        WHERE created_utc >= now() - INTERVAL %(d)s DAY
        """,
        parameters={"d": window_days},
    ).result_rows[0]
    return {
        "drift_reports": int(drift_row[0]),
        "drift_detections": int(drift_row[1]),
    }
```

- [ ] **Step 4: Update `render_markdown`**

In `render_markdown`, replace the `## DORA metrics` section block with:

```python
    out.append("\n\n## DORA delivery throughput\n")
    d = report.dora
    out.append(f"\n- Successful deployments in window: **{d.get('deployments_success')}**")
    out.append(f"\n- Deploy frequency: **{d.get('deploy_frequency_per_week')}/week**")
    out.append(f"\n- Lead time PR-merge → cd_deploy start (p50): **{d.get('lead_time_minutes_p50')} min**")
    out.append(f"\n- Lead time (p95): **{d.get('lead_time_minutes_p95')} min**")
    out.append("\n- Change failure rate / MTTR: **not reported** (no incident corpus in window)")
```

Replace the `## Feedback loop` section block with:

```python
    out.append("\n\n## Drift monitoring\n")
    f = report.feedback_loop
    out.append(f"\n- Drift reports written: **{f.get('drift_reports')}**")
    out.append(f"\n- Drift detections (`drift_detected = 1`): **{f.get('drift_detections')}**")
```

Delete the entire `## System availability (Prometheus)` section block (the `out.append("\n\n## System availability...")` line through the `clickhouse_peak_memory_bytes` line).

- [ ] **Step 5: Run the script and confirm no availability/CFR output**

Run from the repo root:

```bash
uv run python -m scripts.report.extract_metrics && grep -iE "availability|change failure|prometheus" Report/metrics/quantitative_results.md && echo "LEFTOVER FOUND" || echo "CLEAN"
```

Expected: prints `Wrote .../quantitative_results.md`, then `CLEAN` (the only "change failure" hit is the explicit "not reported" line — if `grep` matches it, read the file and confirm it is only that line; that is acceptable). If ClickHouse is unreachable the script may error on `create_client()` — in that case run with the ClickHouse env loaded, or note the DB-dependent numbers will be filled at chapter-writing time.

- [ ] **Step 6: Commit**

```bash
git add scripts/report/extract_metrics.py Report/metrics/quantitative_results.md
git commit -m "feat(report): trim metrics to throughput-only DORA, drop availability"
```

---

## Task 3: Reproducibility re-run demonstration script

**Files:**
- Create: `scripts/report/reproduce_run.py`
- Test: `tests/scripts/test_reproduce_run.py`

This script re-runs a logged forecast from its committed config and target date, then compares to the prediction stored in `algo.experiment_predictions`, reporting the max absolute difference. Use a deterministic LEAR config first (`dk1_lear`).

- [ ] **Step 1: Write the failing test for the pure diff helper**

Create `tests/scripts/test_reproduce_run.py`:

```python
import numpy as np
import pytest

from scripts.report.reproduce_run import max_abs_diff


def test_max_abs_diff_identical():
    assert max_abs_diff([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_max_abs_diff_picks_largest_gap():
    assert max_abs_diff([1.0, 2.0, 3.0], [1.0, 2.0, 3.5]) == pytest.approx(0.5)


def test_max_abs_diff_shape_mismatch_raises():
    with pytest.raises(ValueError):
        max_abs_diff([1.0, 2.0], [1.0, 2.0, 3.0])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m pytest tests/scripts/test_reproduce_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.report.reproduce_run'`.

- [ ] **Step 3: Create the script**

Create `scripts/report/reproduce_run.py`:

```python
"""Reproducibility demonstration for the report.

Re-runs a logged forecast from its committed config + target date and compares
the re-run prediction against the prediction stored in
algo.experiment_predictions, reporting the max absolute difference.

Usage:
    uv run python -m scripts.report.reproduce_run --config dk1_lear --date 2026-03-20
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from forecast_cli.config_loader import load_config
from infrastructure_clickhouse.client_factory import create_client
from price_forecasting import LiveRunner


def max_abs_diff(a, b) -> float:
    """Max absolute elementwise difference between two equal-length sequences."""
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.shape != arr_b.shape:
        raise ValueError(f"shape mismatch: {arr_a.shape} vs {arr_b.shape}")
    return float(np.max(np.abs(arr_a - arr_b)))


def fetch_stored_prediction(client, config_name: str, area: str, target_date: str):
    """Return (run_id, [predicted...]) for the most recent run of this config
    that has predictions on target_date, or (None, None)."""
    runs = client.query(
        """
        SELECT run_id FROM algo.experiment_runs FINAL
        WHERE experiment_name = {cfg:String} AND area = {area:String}
        ORDER BY created_utc DESC
        LIMIT 50
        """,
        parameters={"cfg": config_name, "area": area},
    ).result_rows
    for (run_id,) in runs:
        rows = client.query(
            """
            SELECT timestamp_utc, predicted FROM algo.experiment_predictions FINAL
            WHERE run_id = {rid:String} AND toDate(timestamp_utc) = {d:Date}
            ORDER BY timestamp_utc
            """,
            parameters={"rid": run_id, "d": target_date},
        ).result_rows
        if rows:
            return run_id, [float(r[1]) for r in rows]
    return None, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="config name, e.g. dk1_lear")
    parser.add_argument("--date", required=True, help="target date YYYY-MM-DD")
    args = parser.parse_args()

    config = load_config(args.config)
    client = create_client()
    try:
        run_id, stored = fetch_stored_prediction(
            client, config.experiment_name, config.area, args.date
        )
    finally:
        client.close()

    if stored is None:
        print(
            f"No stored prediction found for config={args.config} area={config.area} "
            f"date={args.date}. Pick a date that has a logged run.",
            file=sys.stderr,
        )
        return 2

    result = LiveRunner(config).run_live_with_metadata(args.date)
    rerun = list(result.prediction.values)

    diff = max_abs_diff(rerun, stored)
    print(f"config={args.config} area={config.area} date={args.date}")
    print(f"matched run_id={run_id}")
    print(f"periods={len(stored)}  max_abs_diff={diff:.6f}")
    print("REPRODUCED (max abs diff < 1e-6)" if diff < 1e-6 else f"DIFF {diff:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m pytest tests/scripts/test_reproduce_run.py -v`
Expected: PASS (3 passed). If it fails with `ModuleNotFoundError: No module named 'scripts'`, create an empty `scripts/__init__.py` (`touch scripts/__init__.py`) and re-run; the existing `python -m scripts.report.extract_metrics` invocation continues to work.

- [ ] **Step 5: Run the demo end-to-end against the live DB**

Pick a date inside a deployed config's history. Run:

```bash
uv run python -m scripts.report.reproduce_run --config dk1_lear --date 2026-03-20
```

Expected: prints a matched `run_id`, a period count (24 or 96), and a `max_abs_diff`. For LEAR this should be at or near 0. If "No stored prediction found", query for a valid date first:

```bash
uv run python -c "
from infrastructure_clickhouse.client_factory import create_client
c = create_client()
print(c.query('''SELECT min(toDate(timestamp_utc)), max(toDate(timestamp_utc)) FROM algo.experiment_predictions FINAL''').result_rows)
c.close()"
```

Record the resulting `max_abs_diff` and date — they are transcribed into the chapter in Task 5.

- [ ] **Step 6: Commit**

```bash
git add scripts/report/reproduce_run.py tests/scripts/test_reproduce_run.py
[ -f scripts/__init__.py ] && git add scripts/__init__.py
git commit -m "feat(report): reproducibility re-run demonstration script"
```

---

## Task 4: ML Test Score worksheet

**Files:**
- Create: `Report/metrics/ml_test_score.md`

The ML Test Score (Breck et al. 2017) has 28 items in four sections. Score each **0** (not done), **0.5** (done manually), or **1** (automated/tested). Final score = **min of the four section sums**. Fill the Evidence column from the codebase; leave a score in every row.

- [ ] **Step 1: Create the worksheet with all 28 items**

Create `Report/metrics/ml_test_score.md`:

```markdown
# ML Test Score worksheet (Breck et al. 2017)

Score each item 0 (not done) / 0.5 (manual) / 1 (automated). Final score = min of the
four section sums. Evidence = one-line pointer into algo-repo.

## Section 1 — Data tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Feature expectations captured in a schema | | enforce_schema() in domain/curves.py |
| 2 | All features are beneficial | | |
| 3 | No feature costs too much | | |
| 4 | Features adhere to meta-level requirements | | |
| 5 | Data pipeline has appropriate privacy controls | | |
| 6 | New features can be added quickly | | FeatureTransformer pipeline, data/transformers.py |
| 7 | All input feature code is tested | | tests/price_forecasting/ |

## Section 2 — Model development tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Model specs are reviewed and submitted | | configs/ in git, PR review |
| 2 | Offline and online metrics correlate | | |
| 3 | All hyperparameters have been tuned | | Optuna tune CLI, hyperparam_trials |
| 4 | The impact of model staleness is known | | daily refit at 06:00 UTC |
| 5 | A simpler model is not better | | LEAR baseline vs DNN/Transformer |
| 6 | Model quality is sufficient on slices | | per-area (DK1, DE) backtests |
| 7 | The model is tested for inclusion (fairness) | | n/a domain |

## Section 3 — ML infrastructure tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Training is reproducible | | reproduce_run.py demo |
| 2 | Model specs are unit tested | | tests/price_forecasting/models/ |
| 3 | The full ML pipeline is integration tested | | LEAR smoke test, tests/.../test_smoke.py |
| 4 | Model quality validated before serving | | |
| 5 | The model allows debugging by observing steps | | Loki structured logging |
| 6 | Models are tested via a canary process | | cd_deploy triggers a forecast post-deploy |
| 7 | Models can be quickly and safely rolled back | | model_artifacts blobs, re-insert pattern |

## Section 4 — Monitoring tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Dependency changes result in notification | | |
| 2 | Data invariants hold in training and serving | | schema enforcement both paths |
| 3 | Training and serving features compute same values | | shared DataPreprocessor |
| 4 | Models are not too stale | | daily refit; staleness < 24h |
| 5 | The model is numerically stable | | |
| 6 | Compute performance has not regressed | | training_duration_seconds tracked |
| 7 | Prediction quality has not regressed | | reconciliation + accuracy-degradation alert |

## Scores
- Section 1 (Data) sum: ___ / 7
- Section 2 (Model) sum: ___ / 7
- Section 3 (Infra) sum: ___ / 7
- Section 4 (Monitoring) sum: ___ / 7
- **ML Test Score = min(section sums) = ___**
```

- [ ] **Step 2: Score every row from the codebase**

Walk each item and fill in 0 / 0.5 / 1 plus evidence. Use the existing chapter §P1–P9 and the codebase as the source of truth. Compute the four section sums and the min. Do not leave any Score cell blank.

- [ ] **Step 3: Commit**

```bash
git add Report/metrics/ml_test_score.md
git commit -m "docs(report): ML Test Score self-audit worksheet"
```

---

## Task 5: Rewrite §5.2 Quantitative evaluation in the chapter

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (the `\subsection{Quantitative evaluation}` block, currently lines ~703–868, ending immediately before `\subsection{Known gaps}`)

Replace the entire current subsection (from the line `\subsection{Quantitative evaluation}` up to but **not including** `\subsection{Known gaps}`) with the content below. Transcribe the bracketed `<...>` values from `Report/metrics/quantitative_results.md`, `Report/metrics/ml_test_score.md`, and the Task 3 demo output. If a number is missing, write `n/a` and add a one-clause note rather than inventing a value.

- [ ] **Step 1: Replace the subsection**

```latex
\subsection{Quantitative evaluation}

The qualitative maturity table above records whether a practice is realised, not
by how much. This section adds quantitative evidence. Following the single-case
study guidelines of Runeson and H\"ost~\cite{runeson2009casestudy}, the system is
evaluated from its source code, version-control and CI history, and short targeted
experiments; the reported figures are indicative of the system over the study
window rather than claims about long-run production operation. This framing is the
same one adopted by comparable MLOps evaluations in the electricity-forecasting
domain~\cite{subramanya2022devops2mlops}.

\subsubsection{ML Test Score}

We self-administer the ML Test Score rubric of Breck et
al.~\cite{breck2017mltestscore}, which scores 28 tests across four sections
(data, model development, ML infrastructure, monitoring) on a $\{0, 0.5, 1\}$
scale; the final score is the \emph{minimum} of the four section sums, so the
weakest area bounds the result. Table~\ref{tab:ml-test-score} reports the
per-section sums and the final score.

\begin{table}[h]
  \centering
  \caption{ML Test Score self-assessment (min-of-sections rule).}
  \label{tab:ml-test-score}
  \begin{tabularx}{\linewidth}{@{}X r@{}}
    \toprule
    \textbf{Section (max 7)} & \textbf{Sum} \\
    \midrule
    Data tests                & <data_sum> \\
    Model development tests    & <model_sum> \\
    ML infrastructure tests    & <infra_sum> \\
    Monitoring tests           & <monitoring_sum> \\
    \midrule
    \textbf{ML Test Score (min)} & \textbf{<ml_test_score>} \\
    \bottomrule
  \end{tabularx}
\end{table}

The binding section is <weakest_section>, which we read as the system's primary
remaining investment area and revisit under \S5.3.

\subsubsection{Reproducibility}

Reproducibility is measured two ways. First, as provenance coverage: of the
<total_runs> live runs in the window, <with_full_triple_pct>\,\% carry the
complete provenance triple (\texttt{git\_sha}, the data window
(\texttt{data\_start\_utc}, \texttt{data\_end\_utc}), and
\texttt{model\_artifact\_id}). Second, as a worked re-run: using only a logged
run's committed configuration and target date, we regenerated the forecast with
\texttt{scripts/report/reproduce\_run.py} and compared it to the prediction stored
in \texttt{algo.experiment\_predictions}. For the deterministic LEAR
configuration on <repro_date>, the maximum absolute difference across all
<repro_periods> delivery periods was <repro_max_abs_diff>. Under the ACM Artifact
Review and Badging terminology, the artefact is Available, Functional, and
Reusable by self-review; we do not claim the independent ``Reproduced'' badge,
which requires an external reviewer~\cite{gundersen2018reproducibility}.

\subsubsection{Delivery throughput}

Treating each successful run of \texttt{cd\_deploy.yml} on \texttt{main} as one
deployment, we report the two DORA \emph{throughput} metrics~\cite{forsgren2018accelerate}:
over the window there were <deployments_success> successful deployments
(<deploy_frequency_per_week} per week), with a PR-merge-to-deploy-start lead time
of <lead_p50>\,min (p50) and <lead_p95>\,min (p95). We deliberately do
\emph{not} report change failure rate or mean time to restore: both require an
incident corpus that a study window of this length does not provide, and we do
not assign a DORA performance tier, whose thresholds are re-derived annually.

\subsubsection{Drift detection as monitoring, not a retraining trigger}

The system refits every model from scratch daily on a rolling window at a cost of
seconds (\S P6), so the model is never stale between scheduled refits. In this
regime, drift-\emph{triggered} retraining adds no freshness benefit over the
scheduled refit: the cost--benefit analysis of Mahadevan and
Mathioudakis~\cite{mahadevan2024costaware} shows that triggered retraining earns
its keep only when retraining is expensive, and that distribution-drift triggers
otherwise incur unnecessary retrains from false positives. We therefore retain
drift detection as a \emph{monitoring and alerting} signal rather than a
retraining trigger, which is why \texttt{retrain\_on\_drift} defaults to false.
This conclusion is conditional: it holds while retraining stays cheap and the
rolling window short, and would be revisited for expensive multi-year transformer
retraining. We also note a calibration limitation: over the window the detector
flagged drift on <drift_detections> of <drift_reports> reports, a detection rate
that is uninformatively high and is listed as future work in \S5.3.

\subsubsection{Summary}

Taken together, these measurements turn the chapter's qualitative ``Realised''
labels into numbers: a single ML Test Score with a per-section breakdown, a
provenance-coverage percentage backed by a live re-run, and delivery-throughput
figures. Each is recomputable by re-running
\texttt{scripts/report/extract\_metrics.py} and
\texttt{scripts/report/reproduce\_run.py} against the live system.
```

- [ ] **Step 2: Fix the deliberate brace typo introduced above**

The block above contains one LaTeX typo to catch during transcription: `<deploy_frequency_per_week}` must become `<deploy_frequency_per_week>` (closing angle bracket, not brace) before you substitute the number. Confirm there are no stray `{`/`}` or `<`/`>` mismatches after substituting all values.

- [ ] **Step 3: Substitute every bracketed value**

Replace each `<...>` token with the measured value from the metrics files and the Task 3 demo. There must be **zero** `<` or `>` placeholder tokens left in the file. Verify:

```bash
grep -nE "<[a-z_]+>" Report/chapters/system_implementation.tex && echo "PLACEHOLDERS REMAIN" || echo "ALL SUBSTITUTED"
```

Expected: `ALL SUBSTITUTED`.

- [ ] **Step 4: Confirm the availability + CFR tables are gone**

```bash
grep -niE "availability|quant-availability|change failure rate|grafana uptime" Report/chapters/system_implementation.tex && echo "LEFTOVER" || echo "CLEAN"
```

Expected: `CLEAN`. (If a hit appears in an unrelated section such as P8 monitoring prose, confirm it is not the deleted §5.2 tables.)

- [ ] **Step 5: Build the chapter and resolve citations**

```bash
cd Report && pdflatex -interaction=batchmode system_implementation_standalone.tex >/dev/null 2>&1; bibtex system_implementation_standalone >/dev/null 2>&1; pdflatex -interaction=batchmode system_implementation_standalone.tex >/dev/null 2>&1; pdflatex -interaction=batchmode system_implementation_standalone.tex 2>&1 | tail -3; cd ..
```

Then check for unresolved references:

```bash
grep -iE "undefined (citation|reference)|Citation .* undefined" Report/system_implementation_standalone.log && echo "UNRESOLVED" || echo "REFS OK"
```

Expected: `REFS OK`. If a citation is undefined, confirm the key matches Task 1 exactly.

- [ ] **Step 6: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): rewrite quantitative evaluation (ML Test Score, reproducibility, DORA throughput)"
```

---

## Task 6: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run python -m pytest tests/ -q`
Expected: all pass, including the new `tests/scripts/test_reproduce_run.py` (3 new tests).

- [ ] **Step 2: Confirm no overclaiming language remains in the chapter**

```bash
grep -niE "ninety days of operation|90 days of operation|last ninety days" Report/chapters/system_implementation.tex && echo "OVERCLAIM REMAINS" || echo "CLEAN"
```

Expected: `CLEAN`.

- [ ] **Step 3: Confirm the PDF built**

```bash
ls -la Report/system_implementation_standalone.pdf
```

Expected: a recently-modified PDF exists.

- [ ] **Step 4: Final commit if anything is uncommitted**

```bash
git status --short
```

If clean, the work is complete. If not, review and commit remaining changes.

---

## Self-review notes (for the implementer)

- **Reproducibility determinism:** LEAR (LassoCV) is deterministic given fixed data, so `dk1_lear` should reproduce at `max_abs_diff ≈ 0`. DNN/Transformer have seed/ensemble stochasticity — if you demo those too, report the diff honestly rather than expecting zero. Lead with LEAR.
- **DB availability:** Tasks 2, 3, and 5 read live ClickHouse. If the DB is empty/unreachable, the script still runs but emits zeros/None; in that case fill the chapter values when the DB is reachable rather than transcribing zeros.
- **The brace typo in Task 5 Step 1 is intentional** and called out in Step 2 — do not "fix" it silently elsewhere.
