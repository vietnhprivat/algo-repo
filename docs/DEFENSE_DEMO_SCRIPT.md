# Live Demo — step by step (~7.5 min)

**Premise (say once at the start):** *"I'm a contributor. A stakeholder wants the DK2
bidding zone added. Watch the platform take that from a merged change to a live, monitored
forecast — through CI/CD, Prefect, Grafana and W&B."*

The change (adding `dk2_lear`) was driven through the pipeline **before** the talk, so
nothing here waits on CI or a merge. Everything below is live navigation of real surfaces.

Order: **CI/CD → Prefect → Grafana → W&B** (ship it → run it → it's healthy → it's scored).

---

## Before you click anything (setup, 30 s, done off-stage)

Pre-open these tabs/windows, logged in, in this left-to-right order so you just move across:

1. Browser tab — GitHub PR for the DK2 change (`github.com/vietnhprivat/algo-repo` → Pull requests → the merged DK2 PR).
2. Browser tab — GitHub **Actions** → the `cd_deploy` run for that merge.
3. Browser tab — **Prefect** `http://localhost:4200` → Deployments.
4. Browser tab — **Grafana** `http://localhost:3000` → Dashboards.
5. Browser tab — **W&B** `wandb.ai` → the `algo-prod` project.
6. A terminal (fallback only).

Have the backup screen-recording one click away. Target date to type later: **2026-06-12**.

---

## Granular timeline (teleprompter, ~10–15 s steps)

Clock is cumulative from the moment you switch off the LIVE DEMO slide. **⏱ checkpoints**
are pacing guardrails — if you're past one, move on, don't finish the sentence. The only
natural dead time is the Prefect run, so **trigger it the instant you open Prefect and talk
over it**. *(do)* = what your hands do; **Say** = words, roughly verbatim.

### Switch in + premise · 0:00–0:18
- **0:00** *(do)* Alt-tab off the red LIVE DEMO slide → GitHub **PR** tab.
- **0:05** **Say:** "I'm a contributor. A stakeholder wants the DK2 bidding zone added — watch
  the platform take that from a merged change to a live, monitored forecast."

### CI/CD · 0:18–2:00 · GitHub *(internet; screenshots if flaky)*
- **0:18** *(do)* Point at the **three green checks** on the PR.
  **Say:** "Nothing reaches `main` without these three — tests, lint, and an end-to-end smoke."
- **0:38** *(do)* Click **Files changed**.
  **Say:** "The whole change is one new config and one line in the deployment list..."
- **0:55** *(do)* Hover the `dk2_lear.py` diff.
  **Say:** "...area DK2, short calibration windows because it's a new market with little
  history. Adding a market is a few lines, by design."
- **1:15** *(do)* Click the **`pr_smoke`** check → **Details** → scroll the log.
  **Say:** "The smoke test stands up the whole stack and runs a forecast and reconciliation on
  synthetic data, so a broken pipeline can't merge."
- **1:40** *(do)* **Actions** tab → open the **`cd_deploy`** run for the merge; scroll steps.
  **Say:** "On merge, CD reaches the host over Tailscale, applies migrations, rebuilds the
  image with the commit SHA baked in, redeploys the flows, and runs a smoke forecast."
- **⏱ 2:00 — leave GitHub.** **Say:** "...and that registers DK2 as a deployment — let's see it."

### Prefect · 2:00–4:15 · localhost:4200 *(offline-safe)*
- **2:00** *(do)* Alt-tab to **Prefect → Deployments**.
- **2:08** *(do)* Point at **`daily-forecast-dk2_lear`**.
  **Say:** "Here it is, just registered, on the same 6 a.m. schedule as the others."
- **2:22** *(do)* Open it → **Run ▸ Custom run**.
- **2:32** *(do)* Set **`target_date = 2026-06-12`** → click **Run**.
  **Say:** "I'll run it for a recent day — that fires the flow now."
- **2:45** *(do)* Go to **Flow Runs** → click the run that just started → show the **task graph**.
  **Say:** "One task per stage. The worker spawns an ephemeral container..."
- **3:05** *(do)* Point at the **streaming logs**.
  **Say:** "...it loads the window from ClickHouse, refits the model from scratch, and forecasts."
- **3:25** *(run still going — fill the time)* **Say:** "A new zone has only a few weeks of
  history, so it uses short windows — the same data trade-off the thesis discusses for DE."
- **3:45** *(do)* State flips to **Completed** → scroll logs to the prediction.
- **3:55** *(do)* Point at the **24 hourly prices**.
  **Say:** "A brand-new market, forecast end to end — overnight low, the midday solar dip, the
  evening peak."
- **⏱ 4:15 — leave Prefect.** *(If not finished by ~3:50, open the run you pre-ran this
  morning — identical view, no waiting.)* **Say:** "Every step of that was logged and stored —
  which brings us to monitoring."

### Grafana · 4:15–5:40 · localhost:3000 *(offline-safe)*
- **4:15** *(do)* Alt-tab to **Grafana → Data Quality**.
- **4:25** *(do)* Point at **Freshness By Curve**.
  **Say:** "Data health per curve — DK2's price and exogenous feeds are fresh..."
- **4:40** *(do)* Point at **Missing Energy Price Hours**.
  **Say:** "...and no missing hours."
- **4:55** *(do)* Switch to **System Health** → point at **Scrape target status**.
  **Say:** "The platform's own vitals — every service up and scraped by Prometheus."
- **5:12** *(do)* Glance at **ClickHouse query rate / merge backlog**.
- **5:22** *(do)* Switch to **Operational → Live Log Stream**.
  **Say:** "And the structured logs from the DK2 run I just triggered, streaming in via Loki."
- **⏱ 5:40 — leave Grafana.** **Say:** "So it runs and it's healthy. Last question — how good is it?"

### W&B · 5:40–7:00 · wandb.ai `algo-prod` *(internet; screenshots if flaky)*
- **5:40** *(do)* Alt-tab to **W&B → `algo-prod`** → runs table.
- **5:52** *(do)* Point at the `prod-dk1-*` / `prod-de-*` runs.
  **Say:** "Every production forecast is reconciled against realised prices the next day..."
- **6:10** *(do)* Open a run (or a comparison panel) → the **MAE / RMSE / sMAPE** chart.
  **Say:** "...and its error is tracked here — the model-quality surface."
- **6:35** **Say:** "Offline backtest and live forecasts use the exact same metrics. DK2 joins
  this view after its first reconciliation tomorrow."
- **⏱ 7:00 — wrap.**

### Close · 7:00–7:20
- **7:00** *(do)* Alt-tab back to slides (the **workload** slide is up).
- **7:05** **Say:** "So in a few minutes, as a contributor, I added a market and shipped it
  through a gated pipeline — and the platform registered it, ran it, stayed healthy, and is
  scoring it."
- **7:15** **Say:** "That's seven of the nine MLOps practices, live. Now, how well do the
  models actually forecast?" → into Part 3.

---

The four sections below repeat this flow grouped by surface, with the full click-detail.

---

## 1. CI/CD — the change shipped (~2 min) · *GitHub, needs internet*

1. **PR tab.** Point at the title ("Add DK2 market") and the **three green checks**:
   `pr_test`, `pr_ruff-lint`, `pr_smoke`.
   - *Say:* "Every change goes through a PR; nothing reaches `main` without these three passing."
2. Open the **Files changed** tab. Show it's basically `configs/dk2_lear.py` plus one line
   in `FORECAST_CONFIGS`.
   - *Say:* "Adding a whole market is a few lines — the flows are parameterised by area."
3. Click into **`pr_smoke`** check → its log.
   - *Say:* "The smoke test stands up the stack and runs an end-to-end forecast and
     reconciliation on synthetic data, so a broken pipeline can't merge."
4. **Actions tab** → the `cd_deploy` run. Scroll the steps.
   - *Say:* "On merge, CD reaches the host over Tailscale, applies migrations, rebuilds the
     image with the commit SHA baked in, redeploys the Prefect flows, and runs a smoke
     forecast. The DK2 deployment is now registered."

*Fallback if no internet: the same four views as pre-captured screenshots.*

---

## 2. Prefect — the platform runs the new market (~2.5 min) · *localhost, offline-safe*

1. **Deployments page.** Scroll/filter to **`daily-forecast-dk2_lear`** — it's there, with a
   `0 6 * * *` schedule, alongside the dk1/de ones.
   - *Say:* "CD just registered this. The new market is now a first-class scheduled job."
2. Open it → **Run → Custom run**. Leave `config_name = dk2_lear`; set
   **`target_date = 2026-06-12`**. Submit.
   - *Say:* "I'll run it for a recent day. (A new zone only has a few weeks of history, so it
     uses short calibration windows — the same data-history trade-off the thesis discusses.)"
3. **Flow Runs** → open the running run. Show the **task graph** and the **streaming logs**.
   - *Say:* "One task per stage; the worker spawns an ephemeral container, refits from
     scratch, forecasts, and stores the result."
4. When it completes (~30–60 s), scroll the logs to the **24 hourly DK2 prices** (overnight
   plateau, midday solar dip, evening peak).
   - *Say:* "A brand-new market, forecast end to end."

*Fallback if the run is slow/flaky: in the terminal run
`uv run python -m forecast_cli.main predict dk2_lear -d 2026-06-12` (proven to work), or
open the DK2 run you pre-ran this morning.*

---

## 3. Grafana — is it healthy? (~1.5 min) · *localhost, offline-safe*

1. **Dashboards → "Data Quality".** Point at **Freshness By Curve** and **Missing Energy
   Price Hours** — DK2's curves are fresh, no gaps.
   - *Say:* "Data health per curve — staleness and missing hours surface here automatically."
2. **Dashboards → "System Health".** Point at **Scrape target status** (all up) and
   **ClickHouse query rate / merge backlog**.
   - *Say:* "Prometheus scrapes the services; this is the platform's own vitals."
3. **Dashboards → "Operational".** Point at the **Live Log Stream** and **Logs By Service**
   — the structured logs from the DK2 run you just triggered, flowing in via Loki.
   - *Say:* "Every flow pushes structured logs to Loki; I can filter to the run that just ran."

*All three are file-provisioned from the repo — no clicking-to-build dashboards.*

---

## 4. W&B — how good is it? (~1.5 min) · *wandb.ai, needs internet*

1. **`algo-prod` project**, runs table. Show the per-`(area, config)` runs
   (`prod-dk1-dk1_lear`, `prod-de-de_dnn`, …).
   - *Say:* "Every production forecast is reconciled against realised prices the next day,
     and its MAE / RMSE / sMAPE is tracked here — this is the model-quality surface."
2. Open one run (or a comparison panel) → show **MAE / RMSE / sMAPE** over reconciled days.
   - *Say:* "So offline backtest accuracy and live accuracy use the same metrics; DK2 joins
     this view after its first reconciliation tomorrow."

*Fallback if no internet: a screenshot of the `algo-prod` runs table and a metric panel.*

---

## Close (~20 s)
*"In a few minutes, as a contributor, I added a market and shipped it through a gated
pipeline; the platform registered it, ran it, stayed healthy, and is scoring it — CI/CD,
orchestration, monitoring and tracking, live. That's seven of the nine MLOps practices."*

---

## What must be true before the talk (pre-stage once)
- `configs/dk2_lear.py` added to `FORECAST_CONFIGS` and the **PR merged** (so CI is green and
  `daily-forecast-dk2_lear` is registered in Prefect).
- One **DK2 run already tracked** so the provenance/logs exist if the live trigger fails.
- Browsers **logged in** to GitHub and W&B; the stack up (`docker ps` shows six services).
- The sklearn `FutureWarning` lines silenced for a clean terminal fallback
  (`export PYTHONWARNINGS="ignore::FutureWarning"`).
- A full **backup recording** of this exact sequence.
