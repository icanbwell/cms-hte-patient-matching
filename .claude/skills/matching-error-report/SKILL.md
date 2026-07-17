---
name: matching-error-report
description: >-
  Produce the standardized member/patient match-error volume-and-trend report from the Sigma
  "Connection Matching Error Research" dashboard. Use this whenever someone asks how match errors
  are trending, wants a weekly/status number on matching failures, asks "are errors going up or
  holding?", needs the 30-day volume or error-to-registration ratio, or wants the blurb for a
  status update. Trigger for phrasings like "how's matching looking this week," "give me the
  match-error trend," or "are we still holding the improvement?" — not just literal "report"
  requests. Produces volume, ratio, step-change, a stability read (slope/CV), and a ready-to-paste
  status summary.
---

# Matching error report

This standardizes the "how are match errors trending?" answer so week-to-week updates are
comparable and don't get re-derived (or misread) each time. It reads the **live run-level**
data, distinct from the person-level failure logs used by `analyze-matching-mismatches`.

## Source (get this right)

- Sigma workbook **"Connection Matching Error Research"** (`workbookId` `839139a7-35b8-4d6b-ac99-9933f5884cb9`).
- Backing warehouse table: **`bronze.proa.metrics`** (Databricks connection). `matched` (bool) is
  the pass/fail flag; the client is a derived field (WellSense records aren't identified by
  `slug` — slug is the EHR connection and varies — so filter on the client id column, auto-detect
  which raw column carries `wellsense`).
- ⚠️ Ignore the workbook's **"PROA Metrics" success-rate** element — it's stale (stopped updating
  Oct 2025). Use "Matching Errors by Day" (element `S2V14RkfL9`) for the live series.
- Counts are **run-level** (retries counted), so totals exceed unique-person counts — never
  present them as contradicting the person-level failure logs.

## Steps

1. **Pull the daily series** (last ~60 days) — errors per day = runs where `matched = false` for
   the WellSense client. Use the Sigma "Matching Errors by Day" element, or query
   `bronze.proa.metrics` directly: `SELECT DATE(run_date_time) day, COUNT(*) FROM bronze.proa.metrics
   WHERE matched = false AND <client filter> AND run_date_time >= DATEADD(day,-60,CURRENT_DATE()) GROUP BY 1`.
2. **Compute:**
   - **Last-30-day volume** (total + mean/day) and vs. the prior 30 days (% change).
   - **Step-change** vs. the prior peak/plateau (the mid-June ~80% drop is the reference baseline).
   - **Stability of the current regime:** split it in half and compare means, and report the
     linear slope (≈0/week = flat = holding) and the coefficient of variation. "Flat at a low
     level" is the success state, not a stall — say so explicitly.
   - **Ratio** vs. registrations if a denominator is available (~errors/day ÷ registrations/day),
     labeled as approximate.
3. **Draft the status blurb** — 2–3 sentences: current /day, trend vs. prior period, whether it's
   holding, and the one-line framing ("residual is upstream data quality, not the algorithm" when
   the mismatch analysis supports it).

## Output — always this shape

- A small table: last-30d total & mean/day, prior-30d, % change, step-change vs. peak.
- Stability read: half-vs-half means + slope + CV → holding / rising / falling.
- Ratio (if available), clearly marked approximate.
- A paste-ready status sentence for the update.

Keep the interpretation honest: after a large one-time improvement you settle onto a floor set by
upstream data quality — you don't keep declining linearly, and flat-at-low is good. For the
per-field "why" behind the errors, hand off to the `analyze-matching-mismatches` skill.
