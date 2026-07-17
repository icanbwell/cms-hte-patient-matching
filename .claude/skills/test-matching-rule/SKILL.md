---
name: test-matching-rule
description: >-
  Measure the before/after impact of a proposed patient-matching change BEFORE it ships, using
  the standardized evaluation harness. Use this whenever someone proposes a new blocking rule,
  scoring rule, nickname/normalization tweak, or a threshold change and asks "will this help?",
  "does it increase false positives?", "should we ship it?", "what does it do to recall/precision?",
  or wants to justify adding a rule to catch a mismatch pattern. Trigger even when they don't say
  "test" — "can we add a rule for X," "what if we lower the threshold to 0.94," or "prove this is
  safe" all apply. Produces a before/after report (TPR/FPR/FNR/precision/F1 with credible
  intervals), a paired true-positive/false-positive churn view, and a ship / reject /
  needs-more-data verdict, safety-first (a false positive = wrong-patient match is the critical error).
---

# Test a matching rule

Adding rules on intuition is how you overfit and quietly raise false positives. This skill runs
any candidate change through the same statistical harness so the decision is evidence-based and
comparable across proposals. The harness lives at **`evaluation/rule_eval.py`**; the full spec,
data protocol, and decision rules are in **`evaluation/DESIGN.md`**; a runnable example is
**`notebooks/rule_eval_demo.ipynb`**.

## What counts as a "rule"

Anything expressible as `features -> bool` (predicted match): a blocking rule, a scoring rule, or
a threshold change. That's the whole point — they all plug in identically. A threshold change is
just `lambda f: f["score"] >= 0.94`.

## Steps

1. **Get a labeled gold set** of match / non-match pairs (`LabeledPair(features, is_true_match,
   strata)`). For CMS work this is the **ONC patient-matching test dataset** (ground truth →
   real precision/recall/FPR). WellSense *prod* logs are **unlabeled** — use them for behavior /
   shadow only, never to claim precision/recall.
2. **Split.** `dev, holdout = stratified_split(pairs, holdout_frac=0.70, strata_keys=[...])`.
   The **holdout (70%) is protected** — never tune on it. Stratify on the gold label (preserves
   base rate) and on demographic strata; **always include a `dob_present:"no"` stratum** so a
   DOB-reliant rule's degradation on CMS-sourced (missing-DOB) records is visible.
3. **Compare on the holdout only:**
   ```python
   import sys; sys.path.insert(0, "evaluation")   # or install: pip install numpy scipy pandas matplotlib
   import rule_eval as re
   report = re.compare(baseline, candidate, holdout,
                       candidate_name="my-rule",
                       primary_metric="TPR (recall/sensitivity)")  # set to what the change targets
   print(re.format_report(report))                # verdict + per-metric credible intervals + churn
   ```
4. **Read the verdict** (see interpretation below). If it's `NEEDS MORE DATA`, use
   `re.min_sample_size(p0, delta)` to say how many labels would resolve the effect you care about,
   rather than guessing.

## Interpreting the report

- **Per metric:** `improved` = P(better) ≥ 0.95, `regressed` ≤ 0.05, else `inconclusive`
  (credible intervals still overlap → not enough evidence).
- **Paired view (the churn):** check `lost` and `churn`, not just net recall. Any `lost > 0`
  means the rule drops matches the old one caught — acceptable only if the trade is deliberate.
- **Overall verdict (safety-first):**
  - **REJECT** — FPR or Precision decisively regresses. A wrong-patient release risk is
    disqualifying regardless of recall gains.
  - **SHIP** — no safety regression AND the primary metric decisively improves.
  - **NEEDS MORE DATA** — otherwise; get more labels or lean on the paired test.

## Why it's built this way

A false positive here is a **wrong-patient record link** — the critical, hard-to-detect error —
so the harness protects precision/FPR by design and forces recall gains to prove they don't come
at precision's expense. Verdicts are computed on an untouched holdout because deterministic rules
have no training set; the dev split is the design/tuning analog. Re-run after *any* change to
matching logic, normalization, or thresholds — same discipline the CMS proposal requires (§VI:
validate before go-live and after every change).

> The harness needs `numpy` (and `scipy`/`pandas`/`matplotlib` for stats/rendering), which are
> present on Databricks clusters. It is intentionally not a dependency of the shippable
> `patient_matching` package.
