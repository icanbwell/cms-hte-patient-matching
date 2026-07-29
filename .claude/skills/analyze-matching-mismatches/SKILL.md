---
name: analyze-matching-mismatches
description: >-
  Standardized analysis of member/patient matching FAILURES and mismatch patterns. Use this
  whenever someone asks why records didn't match, wants to "look at the actual data" behind
  match errors, needs a breakdown of DOB/gender/name/ZIP failures, asks whether a spike in
  match failures is the algorithm or upstream data, or wants a repeatable read on member-match
  failures for a client and time window (e.g. WellSense). Trigger even if they don't say
  "mismatch" — phrases like "these members can't connect," "account-creation match errors,"
  "why is DOB failing," or "is this our bug or their data?" all apply. Produces a consistent
  field-outcome breakdown, score-vs-threshold distribution, sole-blocker analysis, and an
  upstream-data-vs-algorithm verdict.
---

# Analyze matching mismatches

The recurring question is some version of *"records aren't matching — is it our algorithm or
their data, and what's the pattern?"* This skill answers it the same way every time so the
conclusion is defensible and comparable across runs. The heart of it: **be explicit about
which of three data layers you're looking at, because they are different datasets and people
constantly conflate them.**

## The three data layers (state which one you're using)

| Layer | Source | Grain | Has raw values? | Answers |
|---|---|---|---|---|
| **A — failure logs** | `enterprise-person-service` logs (`msg="Matching Failure insight"`) exported to JSON | 1 row / unique failed person | No — outcomes only | "how far below the bar, which field blocked it?" |
| **B — error dashboard** | Sigma *Connection Matching Error Research* → `bronze.proa.metrics` | 1 row / pipeline run (retries counted) | No — counts | "how many/day, trending?" (use the `matching-error-report` skill) |
| **C — raw reconciliation** | Sigma Custom SQL over `bronze.proa.metrics` (`dob_bwell` vs `dob_ehr`, gender, names) + WellSense source `bronze.wellsense.ws_eligibility_all` | 1 row / match run | **Yes** | "is the difference a typo, a format issue, or genuinely different people?" |

Never present a Layer-A person count and a Layer-B run count as if they conflict — the gap is
retries. If someone says the numbers don't add up, that's usually why.

## Method

The reference implementation is `notebooks/wellsense_member_matching_analysis.py` (a Databricks
notebook). Reuse it; only rebuild pieces if the data source differs. Steps:

1. **Scope it.** Confirm client and time window. Load the Layer-A failure export (or query the
   log source). Record N (unique failed persons), the window, and the match threshold in the data.
2. **Field-outcome table.** Count matched / partial / not-matched / **missing** per field
   (firstName, lastName, gender, dateOfBirth, postalCode). The `missing` column is what settles
   the recurring "is gender/DOB *mismatching* or just *missing*?" debate — read it directly.
3. **Score distribution vs the 0.955 threshold.** Report median/mean and the share ≥0.20 below
   the bar. If most failures sit far below, they are not near-misses and tuning won't recover
   them — say so.
4. **Sole-blocker analysis.** For records failing on exactly one field, which field? DOB is
   usually dominant; gender is usually never the lone blocker — quantify it, don't assert it.
5. **The "perfect-except-DOB ceiling."** Find records perfect on the other four fields, failing
   only on DOB. They cap around **~0.80** (a wrong DOB scores 0.0 and drags the rule average:
   `4/5 × 0.992 ≈ 0.79`). This is the single most convincing number for "why not just lower the
   bar?" — recovering them means dropping 0.955→0.80 and auto-linking different people.
6. **Reconcile raw values (Layer C) when available.** Pull `dob_bwell` vs `dob_ehr` (and
   gender/ZIP) side by side and classify each difference: **format/parse artifact** (same date,
   different representation → our fix), **small typo** (already partly handled), **genuinely
   different** (upstream/different person), or **missing** (blank on one side). This is the
   analysis stakeholders mean by "look at the real data" (tracked as Jira **RA-4428**).

## Output — always this shape

- **Headline verdict:** upstream data quality vs. algorithm, with the numbers behind it.
- **Field table** + **score distribution** + **sole-blocker counts** + **perfect-except-DOB count/ceiling**.
- **Raw-value buckets** (if Layer C available): counts of format-fix / typo / genuinely-different / missing.
- **What's recoverable by us vs. what's upstream**, and the one high-value next check.

## Facts to get right (verified against the current scorer)

- Threshold **0.955** (`helix.personmatching` `matcher.py`); the service re-filters at 0.9555.
- DOB is `exact_only`: exact→1.0; day ±2→0.95; month ±1→0.90; single-digit year typo within
  2yr→0.85; else **0.0**. It has no standalone weight — it's averaged within each rule, so a
  wrong DOB near-vetoes the match. A **missing** DOB is dropped from the average when ≥3 fields
  are present (not penalized).
- Gender only lowercases — there is **no `M/F ↔ male/female` normalization**, so an encoding
  mismatch can read as a false no-match; check for that in Layer C before calling it a real conflict.
- **We do not change DOB/gender weighting in the current algorithm** — genuine value conflicts
  *should* block a match; that work is handled correctly by the CMS v3.3 rework, not by loosening
  the current rules.

For the full data-source map, ownership, and context see the DS handoff doc
(`Handoff_Docs/DS_Handoff_Combined.md` in the working area, or the team's shared copy).
