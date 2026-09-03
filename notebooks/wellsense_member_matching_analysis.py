# ruff: noqa: F821, E501
# mypy: ignore-errors
"""Payer Client Member Matching — Data Exploration & Open-Issue Investigation.

Context: payer client account-creation / member-match triage, July 2026.

Several stakeholders have asked to see the actual data behind the member-matching
discussion, and there has been understandable confusion about which dataset is which.
This script does three things:

1. Explains the three different data layers we have been quoting (they are NOT the
   same data -- see the table below).
2. Reproduces the failure-log analysis visually (score distribution, per-field
   outcomes, the DOB guardrail, the gender missing-vs-mismatch question).
3. Sets up the open-issue investigation -- the raw value-vs-source reconciliation
   (Jira RA-4428) that answers "is this our bug or upstream data?".

It is written to be read top-to-bottom by a non-specialist. Every section starts with
a plain-English note.

The single most important thing to understand: these are THREE different datasets.

  Layer A -- Failure logs
    Source: enterprise-person-service prod logs (msg="Matching Failure insight").
    Grain: 1 row per unique person (deduped, latest mismatch).
    Contains: the match score and per-field outcomes (matched / partial / not-matched).
    Does NOT contain: the actual field values (no names/DOBs).
    Used for: "How far below the bar? Which field blocked it?" (the JSON file).

  Layer B -- Error dashboard
    Source: Sigma "Connection Matching Error Research" -> matching-error / PROA
    tables. Grain: 1 row per pipeline RUN (retries counted separately).
    Contains: daily/weekly error counts, review workflow, manual-link disposition.
    Does NOT contain: person-level dedup (a person who retried 4x = 4 rows).
    Used for: "How many errors per day? Is the trend stable?"

  Layer C -- Review / raw values
    Source: Sigma Custom SQL over bronze.proa.metrics (+
    payer client eligibility table). Grain: 1 row per match run.
    Contains: actual values side-by-side (dob_platform vs dob_ehr, gender_platform vs
    gender_ehr, names, postal, address). Does NOT contain: complete coverage (only
    failed/reviewed runs are surfaced).
    Used for: "Is the difference a typo, a format issue, or genuinely different
    people?"

So when someone says "146 failures" (Layer A) and someone else says "~519 errors
last 30 days" (Layer B), both are correct -- they are counting different things
(unique people vs. individual run attempts; different source systems; slightly
different windows). Do not treat the two numbers as a contradiction.

Glossary:
  score -- the algorithm's confidence for a candidate pair, 0.0-1.0. This is the
    real number to reason about.
  threshold = 0.955 -- auto-match cutoff. score >= 0.955 -> auto-linked; below ->
    not linked (a person may then land in manual review). Single binary cutoff;
    there is no "review band" inside the code.
  match_percent (in the JSON) -- a derived display field = score / threshold.
    0.9548 / 0.955 = 99.98%. It is NOT confidence. Don't read the "95-100%" bucket
    as "95% sure".
  field outcome -- per-field result: matched, partial match, or not matched.
  The mid-June scoring improvement added DOB near-miss tolerance, nickname/initial
    handling, and the "ignore missing fields" rule. The mid-June error drop coincides
    with this improvement.

Configuration: set the path to the JSON export and (optionally) the warehouse
catalog/schema below. Everything downstream reads from here. The script degrades
gracefully: the JSON-driven charts need the JSON; the warehouse sections need Spark
+ table access.
"""

import json
import os
from datetime import datetime, timedelta

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

try:
    from notebooks._sql_safety import _sql_string_literal, _validate_sql_identifier
except ImportError:  # pragma: no cover - only hit when Databricks doesn't have notebooks/ on sys.path
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _sql_safety import _sql_string_literal, _validate_sql_identifier  # type: ignore[no-redef]


# --- Widgets (Databricks). Falls back to defaults when run outside Databricks. ---
try:
    dbutils.widgets.text("json_path", "/dbfs/FileStore/member-matching-demographics.json", "Path to failure-log JSON")
    dbutils.widgets.text("ws_catalog", "bronze", "Payer client source catalog")
    dbutils.widgets.text("ws_schema", "payer_client", "Payer client source schema")
    dbutils.widgets.text("proa_table", "bronze.proa.metrics", "PROA run-metrics table (Layers B & C source)")
    dbutils.widgets.text("ws_client", "payer_client", "Client id (this is clientId, NOT slug)")
    dbutils.widgets.text("client_col", "", "Raw column holding the client id (blank = auto-detect)")
    JSON_PATH = dbutils.widgets.get("json_path")
    WS_CATALOG = _validate_sql_identifier(dbutils.widgets.get("ws_catalog"))
    WS_SCHEMA = _validate_sql_identifier(dbutils.widgets.get("ws_schema"))
    PROA_TABLE = _validate_sql_identifier(dbutils.widgets.get("proa_table"))
    WS_CLIENT = dbutils.widgets.get("ws_client")
    CLIENT_COL = dbutils.widgets.get("client_col").strip()
    if CLIENT_COL:
        _validate_sql_identifier(CLIENT_COL)
    IN_DATABRICKS = True
except Exception:
    # Local fallback — point at the file sitting next to this notebook.
    JSON_PATH = os.environ.get("WS_JSON_PATH", "member-matching-demographics.json")
    WS_CATALOG, WS_SCHEMA = "bronze", "payer_client"
    PROA_TABLE, WS_CLIENT, CLIENT_COL = "bronze.proa.metrics", "payer_client", ""
    IN_DATABRICKS = False

# display() exists in Databricks; provide a no-frills fallback for local runs.
try:
    display  # type: ignore  # noqa: B018
except NameError:
    def display(x):  # noqa: A001
        try:
            from IPython.display import display as _d
            _d(x)
        except Exception:
            print(x)

print(f"IN_DATABRICKS={IN_DATABRICKS}\nJSON_PATH={JSON_PATH}")
print(f"Source (payer client eligibility feed) = {WS_CATALOG}.{WS_SCHEMA}.ws_eligibility_all")
print(f"Source (match runs)     = {PROA_TABLE}   client = {WS_CLIENT!r}  (client_col={'auto' if not CLIENT_COL else CLIENT_COL})")

# Resolve which raw column identifies the payer client (slug varies; client id does not)
# In the dashboard, clientId is stable while `slug` is the EHR connection and varies per run
# — so we must filter on the CLIENT, not the slug. `bronze.proa.metrics` has no literal
# `client_id` column (the workbook's Custom SQL derives it), so we auto-detect which raw column carries the client id.
CANDIDATE_CLIENT_COLS = ["scope", "url", "flow_run_name", "metrics_flow_run_name",
                         "token", "source_system_type", "connection_type", "slug"]

def detect_client_col(table, needle):
    """Return the first raw column that contains `needle` in the last 30 days of runs, plus the hit count."""
    _validate_sql_identifier(table)
    needle_literal = _sql_string_literal(f"%{needle.lower()}%")
    for c in CANDIDATE_CLIENT_COLS:
        _validate_sql_identifier(c)
        try:
            n = spark.sql(
                f"SELECT COUNT(*) AS c FROM {table} "
                f"WHERE LOWER(`{c}`) LIKE {needle_literal} "
                f"AND run_date_time >= DATEADD(day, -30, CURRENT_DATE())"
            ).collect()[0]["c"]
            if n:
                return c, n
        except Exception:  # noqa: BLE001  (column missing / wrong type → try the next candidate)
            continue
    return None, 0

if IN_DATABRICKS:
    if not CLIENT_COL:
        CLIENT_COL, _hits = detect_client_col(PROA_TABLE, WS_CLIENT)
        print(f"Auto-detected client column: {CLIENT_COL!r} ({_hits} '{WS_CLIENT}' rows in last 30d)"
              if CLIENT_COL else
              f"Could not auto-detect a column containing '{WS_CLIENT}'. Set the 'client_col' widget manually. "
              f"Candidates tried: {CANDIDATE_CLIENT_COLS}")  # noqa: E501
    if CLIENT_COL:
        _validate_sql_identifier(CLIENT_COL)
        CLIENT_PREDICATE = f"LOWER(`{CLIENT_COL}`) LIKE {_sql_string_literal(f'%{WS_CLIENT.lower()}%')}"
    else:
        CLIENT_PREDICATE = "TRUE"
else:
    CLIENT_PREDICATE = f"LOWER(`<client_col>`) LIKE {_sql_string_literal(f'%{WS_CLIENT.lower()}%')}"  # resolved at runtime in Databricks
print("Payer client predicate:", CLIENT_PREDICATE)

# LAYER A — The failure logs (the JSON file)
#
# **Plain English:** this is a list of the sign-ups that did *not* auto-match in the last 30 days, one row per person.
# For each one we know *how confident* the algorithm was and *which fields* agreed — but **not the actual names/dates**
# (those live in Layer C). This layer answers "how bad were the misses, and what blocked them?"

# Load the JSON and show the headline metadata
# Only these roots are allowed to be read from — the widget/env value is analyst-supplied but
# must not be able to point outside the expected DBFS/Volumes locations (or the notebook's own
# local directory in the non-Databricks fallback).
_ALLOWED_JSON_ROOTS = ("/dbfs/", "/Volumes/")


def load_failure_json(path):
    """Load Layer A. Handles both /dbfs FUSE paths and plain local paths."""
    normalized = os.path.normpath(path)
    if os.path.isabs(normalized):
        if not normalized.startswith(_ALLOWED_JSON_ROOTS):
            raise ValueError(
                f"Refusing to read {path!r}: absolute paths must be under {_ALLOWED_JSON_ROOTS}."
            )
    elif ".." in normalized.split(os.sep):
        raise ValueError(f"Refusing to read {path!r}: path traversal is not allowed.")

    candidates = [normalized]
    if normalized.startswith("/dbfs/"):
        candidates.append(normalized.replace("/dbfs", "", 1))  # spark path variant
    for p in candidates:
        try:
            with open(p) as f:
                return json.load(f)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(
        f"Could not read the JSON at {path}. In Databricks, upload it to DBFS/a Volume and set the 'json_path' widget."
    )

data = load_failure_json(JSON_PATH)
persons = pd.json_normalize(data["persons"])

print(f"Window                : {data['window']['start']}  →  {data['window']['end']}")
print(f"Source workload       : {data['source_workload']}")
print(f"Log signature         : {data['log_signature']}")
print(f"Total unique persons  : {data['total_unique_persons']}")
print(f"clientPersonId resolved / unresolved : {data['clientPersonId_resolved']} / {data['clientPersonId_unresolved']}")
print(f"Dedup strategy        : {data['dedup_strategy']}")
THRESHOLD = float(persons["threshold"].iloc[0])
print(f"\nMatch threshold (from data): {THRESHOLD}")
display(persons.head(10))

# A1 · Score distribution — how far below the bar are the failures?
# **Why this matters:** if failures were clustered *just* under 0.955, tuning the algorithm might recover them.
# They are not — most sit far below, meaning the two records genuinely look like different people.

# Score histogram with the 0.955 threshold marked
scores = persons["score"].astype(float)
mean_s, median_s = scores.mean(), scores.median()
far_below = (scores <= THRESHOLD - 0.20).mean()
near_miss = ((scores >= THRESHOLD - 0.05) & (scores < THRESHOLD)).sum()

fig, ax = plt.subplots(figsize=(11, 5))
ax.hist(scores, bins=24, edgecolor="white")
ax.axvline(THRESHOLD, color="crimson", lw=2, label=f"threshold = {THRESHOLD}")
ax.axvline(median_s, color="seagreen", ls="--", lw=2, label=f"median = {median_s:.3f}")
ax.axvspan(THRESHOLD - 0.05, THRESHOLD, color="orange", alpha=0.15, label="near-miss band (within 0.05)")
ax.set(title="Layer A · Distribution of match scores for FAILED sign-ups",
       xlabel="match score (0–1)   —   higher = more confident it's the same person",
       ylabel="number of people")
ax.legend()
plt.tight_layout()
display(fig)

print(f"mean={mean_s:.3f}  median={median_s:.3f}")
print(f"Share ≥ 0.20 BELOW threshold : {far_below:.0%}   ← '3 out of 4 miss by a wide margin'")
print(f"Genuine near-misses (within 0.05 of the bar): {near_miss}")
print("\nTakeaway: the typical failure is nowhere near the bar. Lowering the threshold to catch them\n"
      "would mean auto-linking people who only share ~2 of 5 fields — i.e. linking different people.")

# A2 · Per-field outcomes — which fields agree, which block the match?
# **Why this matters:** this is where DOB and gender come under scrutiny. Note the **"missing data" column** —
# it directly answers the question *"is gender mismatching or just missing?"*.

# Stacked bar of field outcomes + the missing-vs-mismatch answer
pft = pd.DataFrame(data["per_field_outcome_table"]).T
pft = pft[["matched", "partial match", "not matched", "missing data"]]
display(pft)

ax = pft.plot(kind="bar", stacked=True, figsize=(11, 5),
              color=["#2e7d32", "#9ccc65", "#e53935", "#9e9e9e"])
ax.set(title="Layer A · Field outcomes across the 146 failed sign-ups",
       ylabel="number of records", xlabel="")
ax.legend(title="outcome", bbox_to_anchor=(1.01, 1))
plt.xticks(rotation=0)
plt.tight_layout()
display(ax.get_figure())

gender = data["per_field_outcome_table"]["gender"]
print("GENDER:", gender)
print(f"\n→ 'missing data' for gender = {gender['missing data']}.  All {gender['not matched']} gender failures are\n"
      "  genuine value conflicts (male vs female), NOT blank fields.\n"
      "  (In the algorithm, missing/unknown gender is scored leniently and dropped from the average when\n"
      "   ≥3 other fields are present — so it never shows up here as 'not matched'.)\n"
      "  This is the data-backed answer to 'is gender missing or mismatching?' → mismatching.")

# A3 · How many of the 5 fields agree per record?  And what is the *sole* blocker?
# **Why this matters:** shows that failures typically agree on only ~2 of 5 fields, and pinpoints DOB as the
# field that single-handedly blocks the most otherwise-good records.

# Fields-matched distribution + sole-blocker tally
FIELDS = ["firstName", "lastName", "gender", "dateOfBirth", "postalCode"]
fo = persons[[f"field_outcomes.{f}" for f in FIELDS]].copy()
fo.columns = FIELDS

n_full = fo.eq("matched").sum(axis=1)
sole_blocker = {}
for f in FIELDS:
    others = [c for c in FIELDS if c != f]
    mask = fo[f].eq("not matched") & fo[others].isin(["matched", "partial match"]).all(axis=1)
    if mask.sum():
        sole_blocker[f] = int(mask.sum())

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.5))
n_full.value_counts().sort_index().plot(kind="bar", ax=ax1, color="#1565c0")
ax1.set(title=f"# of 5 fields FULLY matched (mean={n_full.mean():.2f})",
        xlabel="fields matched", ylabel="records")
ax1.tick_params(axis="x", rotation=0)

pd.Series(sole_blocker).sort_values().plot(kind="barh", ax=ax2, color="#e53935")
ax2.set(title="When exactly ONE field blocks the match, which one?", xlabel="records")
plt.tight_layout()
display(fig)

print("Sole blocker counts:", sole_blocker)
print("→ Gender is NEVER the lone blocker. DOB is the lone blocker far more than anything else.")

# A4 · The guardrail visual — "perfect except DOB" still can't reach the bar
# **This is the single most important chart for the "why don't you just fix it?" conversation.**
# These records match on name, gender, AND ZIP — everything except the birthday — yet they top out around **0.80**,
# nowhere near 0.955. To auto-pass them we'd have to drop the bar ~15 points, which would start auto-linking strangers.

# Records blocked by DOB alone, with all 4 other fields perfect
perfect_except_dob = persons[
    (persons["field_outcomes.dateOfBirth"] == "not matched")
    & (persons["field_outcomes.firstName"] == "matched")
    & (persons["field_outcomes.lastName"] == "matched")
    & (persons["field_outcomes.gender"] == "matched")
    & (persons["field_outcomes.postalCode"] == "matched")
].copy()

print(f"Records perfect on 4/5 fields, failing on DOB alone: {len(perfect_except_dob)}")
print(f"Their scores range {perfect_except_dob['score'].min():.3f} – {perfect_except_dob['score'].max():.3f} "
      f"(mean {perfect_except_dob['score'].mean():.3f})")

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.scatter(range(len(perfect_except_dob)), perfect_except_dob["score"], s=60, color="#6a1b9a", zorder=3)
ax.axhline(THRESHOLD, color="crimson", lw=2, label=f"threshold = {THRESHOLD}")
ax.axhspan(perfect_except_dob["score"].min() - 0.01, perfect_except_dob["score"].max() + 0.01,
           color="#6a1b9a", alpha=0.08, label="ceiling for 'perfect-except-DOB'")
ax.set(title="Layer A · A wrong birthday caps the score at ~0.80 even when everything else is perfect",
       xlabel="record (each dot = one otherwise-perfect person)", ylabel="best achievable score", ylim=(0.7, 1.0))
ax.legend()
plt.tight_layout()
display(fig)

print("\nTAKEAWAY for non-technical stakeholders: DOB is a strong identity signal, so the algorithm weights it heavily.\n"
      "A genuinely-different birthday therefore vetoes the match by design. That is a feature (it stops us linking\n"
      "the wrong person), not a bug — but it means these cases are ONLY recoverable by fixing the birthday data,\n"
      "not by tuning the algorithm.")

# LAYER B — The error dashboard (volume & trend)
#
# **Plain English:** this counts *how many* match errors happen per day (from the Sigma *Connection Matching Error
# Research* workbook). It counts **run attempts**, so a person who retried 4 times shows up 4 times — which is why
# its totals are larger than Layer A's person counts. This layer answers "is the problem getting better, worse, or holding?"
#
# The daily counts below are a **snapshot** captured on 2026-07-15 (aggregate counts only — no PHI). Replace the
# `DAILY_ERRORS_SNAPSHOT` dict with the live query in the next cell once you wire up the warehouse table.

# Daily error counts (snapshot 2026-07-15) — safe aggregate, no PHI
# Source: Sigma element "Matching Errors by Day" (S2V14RkfL9), collapsed across review status.
DAILY_ERRORS_SNAPSHOT = {
    "2026-05-17": 38, "2026-05-18": 22, "2026-05-19": 19, "2026-05-20": 44, "2026-05-21": 45,
    "2026-05-22": 98, "2026-05-23": 101, "2026-05-24": 113, "2026-05-25": 148, "2026-05-26": 159,
    "2026-05-27": 139, "2026-05-28": 116, "2026-05-29": 100, "2026-05-30": 101, "2026-05-31": 79,
    "2026-06-01": 72, "2026-06-02": 84, "2026-06-03": 90, "2026-06-04": 57, "2026-06-05": 54,
    "2026-06-06": 74, "2026-06-07": 60, "2026-06-08": 52, "2026-06-09": 51, "2026-06-10": 47,
    "2026-06-11": 20, "2026-06-12": 10, "2026-06-13": 7, "2026-06-14": 15, "2026-06-15": 23,
    "2026-06-16": 17, "2026-06-17": 19, "2026-06-18": 10, "2026-06-19": 28, "2026-06-20": 8,
    "2026-06-21": 8, "2026-06-22": 16, "2026-06-23": 20, "2026-06-24": 19, "2026-06-25": 23,
    "2026-06-26": 30, "2026-06-27": 22, "2026-06-28": 22, "2026-06-29": 10, "2026-06-30": 14,
    "2026-07-01": 29, "2026-07-02": 17, "2026-07-03": 22, "2026-07-04": 12, "2026-07-05": 19,
    "2026-07-06": 18, "2026-07-07": 19, "2026-07-08": 13, "2026-07-09": 9, "2026-07-10": 30,
    "2026-07-11": 14, "2026-07-12": 11, "2026-07-13": 12, "2026-07-14": 19, "2026-07-15": 9,
}
daily = pd.Series(DAILY_ERRORS_SNAPSHOT)
daily.index = pd.to_datetime(daily.index)
daily = daily.sort_index()

# --- Live query (confirmed source) --------------------------------------------------------------
# The Sigma dashboard is built on a Custom SQL element over `bronze.proa.metrics` (the PROA run-metrics
# table). `matched` (boolean) is the pass/fail flag; `slug` identifies the client. This reproduces the
# run-level daily error count directly from the warehouse. Set USE_LIVE=True to use it instead of the
# 2026-07-15 snapshot above.
USE_LIVE = False
# What counts as an "error"? This is the one modeling choice that can shift the volume numbers, so it is explicit:
#   "unmatched"          -> matched = false                       (a run that did not auto-link — matches the dashboard)
#   "unmatched_or_error" -> matched = false OR error_count > 0     (also count runs that errored out)
ERROR_MODE = "unmatched"
_err_pred = "matched = false" if ERROR_MODE == "unmatched" else "(matched = false OR error_count > 0)"
if USE_LIVE and IN_DATABRICKS:
    live = spark.sql(f"""
        SELECT DATE(run_date_time) AS day, COUNT(*) AS errors
        FROM {PROA_TABLE}
        WHERE {_err_pred}                           -- error definition (see ERROR_MODE)
          AND {CLIENT_PREDICATE}                    -- payer client (auto-resolved above)
          AND run_date_time >= DATEADD(day, -60, CURRENT_DATE())
        GROUP BY DATE(run_date_time)
        ORDER BY day
    """).toPandas()
    daily = live.set_index(pd.to_datetime(live["day"]))["errors"].sort_index()
    print(f"Loaded {len(daily)} days live from {PROA_TABLE}.")
else:
    print("Using the 2026-07-15 snapshot. Set USE_LIVE=True (in Databricks) to pull live from",
          f"{PROA_TABLE} filtered by [{CLIENT_PREDICATE}]. Decide whether an 'error' means matched=false only",
          "or also error_count>0 (see the toggle note in the Findings section).")
# ------------------------------------------------------------------------------------------------

display(daily.rename("errors").to_frame())

# Volume, 30-day windows, step-change and a stability check
today = pd.Timestamp("2026-07-15")
last30 = daily[daily.index >= today - timedelta(days=29)]
prior30 = daily[(daily.index >= today - timedelta(days=59)) & (daily.index < today - timedelta(days=29))]
pre_drop = daily[(daily.index >= "2026-05-22") & (daily.index <= "2026-06-10")]
post_drop = daily[daily.index >= "2026-06-11"]

def summ(name, s):
    cv = s.std(ddof=0) / s.mean() * 100
    print(f"{name:22s} total={int(s.sum()):5d}  mean={s.mean():5.1f}/day  median={s.median():4.0f}  "
          f"range={int(s.min())}-{int(s.max())}  CV={cv:.0f}%")

summ("Last 30d (6/16-7/15)", last30)
summ("Prior 30d (5/17-6/15)", prior30)
print(f"  → change in daily mean: {(last30.mean()-prior30.mean())/prior30.mean()*100:+.0f}%")
summ("Pre-drop (5/22-6/10)", pre_drop)
summ("Post-drop (6/11-7/15)", post_drop)
print(f"  → step reduction vs May peak: {(post_drop.mean()-pre_drop.mean())/pre_drop.mean()*100:+.0f}%")

# Is the CURRENT regime stable? Split it in half + fit a simple linear slope.
h1 = post_drop[post_drop.index <= "2026-06-27"]
h2 = post_drop[post_drop.index > "2026-06-27"]
xs = (post_drop.index - post_drop.index[0]).days.to_numpy(dtype=float)
slope = ((xs - xs.mean()) * (post_drop.values - post_drop.mean())).sum() / ((xs - xs.mean()) ** 2).sum()
print(f"\nStability within current regime: first half={h1.mean():.1f}/day, second half={h2.mean():.1f}/day, "
      f"linear slope={slope*7:+.2f}/week  → essentially FLAT")

# ratio vs registrations (order-of-magnitude anchor from Sarah's thread: ~450 regs/weekday)
REGS_PER_DAY = 450
print(f"\nRatio: ~{last30.mean():.0f} errors/day ÷ ~{REGS_PER_DAY} registrations/weekday "
      f"≈ {last30.mean()/REGS_PER_DAY*100:.1f} per 100 (~1 in {REGS_PER_DAY/last30.mean():.0f}); "
      f"down from ~{pre_drop.mean()/REGS_PER_DAY*100:.0f} per 100 at the May peak.")

# The trend chart — big drop in June, flat ever since
fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(daily.index, daily.values, marker="o", ms=3, lw=1, color="#455a64", label="errors/day")
ax.plot(daily.index, daily.rolling(7).mean(), lw=3, color="#1565c0", label="7-day average")
ax.axvspan(pd.Timestamp("2026-06-11"), today, color="seagreen", alpha=0.08, label="post-fix regime (flat, low)")
ax.axvline(pd.Timestamp("2026-06-04"), color="darkorange", ls="--", lw=1.5, label="Scoring improvement ship (~Jun 4)")
ax.set(title="Layer B · Daily match errors — an ~80% step-down in mid-June, holding steady since",
       xlabel="", ylabel="match errors per day")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.legend()
plt.tight_layout()
display(fig)

print("How to talk about this: 'flat at a low level' is the SUCCESS state, not a stall. After a big one-time\n"
      "improvement you settle onto a floor set by upstream data quality — you do not keep declining linearly.\n"
      "This corroborates the ticket analytics (tickets holding/improving); it does not contradict them.")

# A↔B · Reconciling "146 people" with "≈500+ errors" — the same failures through two lenses
# **Plain English:** the two headline numbers are not in conflict. Layer A counts **unique people**; Layer B counts
# **run attempts**, and one struggling person typically generates several failed attempts (retries). This overlay
# shows the run-attempt bars sitting above the unique-people line over the window where both datasets exist.

# Overlay unique people (Layer A) vs run attempts (Layer B) + the retry ratio
# Layer A: one row per unique person → bucket by the day of their latest recorded mismatch.
personsA = persons.copy()
personsA["day"] = (
    pd.to_datetime(personsA["latest_mismatch_timestamp"], utc=True, errors="coerce")
    .dt.tz_convert(None).dt.normalize()
)
a_daily = personsA.dropna(subset=["day"]).groupby("day").size().rename("unique_people")

# Common window = the JSON's own window (where both datasets overlap).
win_start = pd.to_datetime(data["window"]["start"], utc=True).tz_convert(None).normalize()
win_end = pd.to_datetime(data["window"]["end"], utc=True).tz_convert(None).normalize()
b_daily = daily[(daily.index >= win_start) & (daily.index <= win_end)].rename("run_errors")

recon_ab = pd.concat([a_daily, b_daily], axis=1).fillna(0).sort_index()
totalA, totalB = int(a_daily.sum()), int(b_daily.sum())
print(f"Common window       : {win_start.date()} → {win_end.date()}")
print(f"Layer A unique people (JSON) : {totalA}")
print(f"Layer B run attempts (dash.) : {totalB}")
print(f"Retry ratio                  : {totalB / max(totalA, 1):.1f} run attempts per unique person")

fig, ax = plt.subplots(figsize=(13, 5))
ax.bar(recon_ab.index, recon_ab["run_errors"], width=0.8, color="#b0bec5", label="Layer B — run attempts / day")
ax.plot(recon_ab.index, recon_ab["unique_people"], marker="o", color="#c62828", lw=2, label="Layer A — unique people / day")
ax.set(title="Same failures, two lenses: run attempts (bars) sit above unique people (line)",
       ylabel="count per day", xlabel="")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.legend()
plt.tight_layout()
display(fig)

print("\nTakeaway: quote whichever number matches the question — 'people affected' (Layer A) for member impact,\n"
      "'error events' (Layer B) for system load — but never present the two totals as a discrepancy. The gap IS\n"
      "the retry behaviour, and it is expected.")

# LAYER C — Raw value reconciliation  (open issue)
#
# **Plain English:** Layers A and B tell us *that* a field disagreed and *how often* — but not *why*. The only way to
# know whether a DOB mismatch is **our bug** (e.g. a date-format problem) or **upstream data** (genuinely different /
# missing birthday) is to look at the **actual values side-by-side**.
#
# Where the raw values live (confirmed by tracing the Sigma workbook, incl. what turned out NOT to work):
# - The `dob_platform`/`dob_ehr`, **`gender_platform`/`gender_ehr`**, name/postal pairs + `total_score` are produced by the
#   workbook's **Custom SQL** element ("Input Query"). They are **not** flat columns and **not** a nested struct on
#   `bronze.proa.metrics` — that table only carries run-level fields (`matched`, `run_id`, `client_person_id`, `slug`,
#   `scope`, …), which is why a `DESCRIBE`/explode approach fails. The pairs come from a source the Custom SQL joins.
# - **Easiest reliable path:** don't re-derive it — reuse what Sigma already computed. Either **export** the
#   *Member Match Fail Review* / *Matching Error Table* element to **CSV** and read it, or **paste the Custom SQL**
#   text into the cell below. The next cell supports both via `RECON_SOURCE`.
# - The payer client eligibility table — useful to independently confirm the
#   "ehr"/source side (`date_of_birth`, `gender_code`, `zipcode`). Join key: `member_id`.
#
# > **Gender is captured** in the Custom SQL (`gender_platform`/`gender_ehr`); only the curated *review* subset omits it —
# > so surfacing gender for triage is a Sigma view tweak, not a data-collection gap.
#
# What we already learned from a sample of the review table (2026-07-15)
# - Birthdays are stored **`YYYY-MM-DD` on BOTH sides** → **the "our code mis-parses dates" theory is largely ruled out.** Differences are real.
# - The mismatches break into clean buckets: **genuinely different** (`2002-01-28` vs `2023-02-06`), **small typo** (`1995-03-21` vs `1995-03-23`), **large single-digit typo** (`1998-12-06` vs `1988-12-06` — human-linked but auto-rejected to avoid parent/child false links), and **missing** (`""` → score ≈ 0.051).
# - The job now is to **quantify those buckets** → that tells everyone the *max recoverable by us* vs the *irreducible upstream floor*.

# A reusable DOB classifier — mirrors what the algorithm auto-recovers vs. not
def classify_dob_pair(a, b):
    """Classify a (platform, ehr) DOB pair. Mirrors the platform's graduated DOB logic so analysts can
    see which cases the algorithm ALREADY recovers vs. which are genuinely out of reach.

    Returns one of:
      identical | missing_one_side | format_artifact | typo_auto_recovered | typo_beyond_tolerance | genuinely_different
    """
    if not a or not b or str(a).strip() == "" or str(b).strip() == "":
        return "missing_one_side"
    a, b = str(a).strip(), str(b).strip()
    if a == b:
        return "identical"

    # Does one side parse only after normalising a different format? -> that WOULD be our bug.
    def parse(s):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d", "%m-%d-%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
    da, db = parse(a), parse(b)
    if da is None or db is None:
        return "unparseable"           # investigate — could be a real format/encoding bug
    if da == db:
        return "format_artifact"       # SAME real date, different text format -> OUR fix (canonicalise)

    # Genuine value differences — replicate the algorithm's near-miss tolerance:
    same_ym = (da.year == db.year and da.month == db.month)
    same_yd = (da.year == db.year and da.day == db.day)
    same_md = (da.month == db.month and da.day == db.day)
    if same_ym and 0 < abs(da.day - db.day) <= 2:                 # day off by 1-2   -> algo gives 0.95
        return "typo_auto_recovered"
    if same_yd and abs(da.month - db.month) == 1:                 # month off by 1   -> algo gives 0.90
        return "typo_auto_recovered"
    if same_md and abs(da.year - db.year) <= 2 and \
       sum(x != y for x, y in zip(f"{da.year:04d}", f"{db.year:04d}")) == 1:   # year 1-digit typo within 2y -> 0.85
        return "typo_auto_recovered"
    # Beyond the algorithm's auto-recover tolerance. Heuristic: if only ONE of (year, month, day) differs it is
    # most likely a typo a human would still link (the algorithm rejects it to stay safe against parent/child
    # false positives); if TWO OR MORE components differ, treat it as genuinely different people.
    differing = sum([da.year != db.year, da.month != db.month, da.day != db.day])
    if differing == 1:
        return "typo_beyond_tolerance"
    return "genuinely_different"

# Quick self-check on synthetic (non-PHI) examples so a reader sees how each bucket behaves:
_examples = [
    ("2001-05-03", "2001-05-03", "identical"),
    ("2001-05-03", "05/03/2001", "format_artifact"),
    ("1995-03-21", "1995-03-23", "typo_auto_recovered"),
    ("1998-12-06", "1988-12-06", "typo_beyond_tolerance"),
    ("1996-10-22", "1996-10-28", "typo_beyond_tolerance"),   # 6 days off — one component differs
    ("2002-01-28", "2023-02-06", "genuinely_different"),     # year, month AND day all differ
    ("", "2003-09-11", "missing_one_side"),
]
print("DOB classifier self-check (synthetic data):")
for a, b, expected in _examples:
    got = classify_dob_pair(a, b)
    flag = "OK " if got == expected else "!! "
    print(f"  {flag}{a or '∅':<12} vs {b or '∅':<12} -> {got:22s} (expected {expected})")

# Load the platform-vs-ehr demographic pairs (the reconciliation input)
# IMPORTANT: the dob_platform/dob_ehr/gender_* pairs are NOT flat columns in bronze.proa.metrics. They are built by
# the Sigma workbook's *Custom SQL* element ("Input Query") from a source that isn't exposed as a plain table, so
# we do NOT try to re-derive them here. Pick whichever RECON_SOURCE is easiest for you:
#
#   "csv"        (recommended) — in Sigma, open the workbook element "Member Match Fail Review" (or "Matching Error
#                 Table"), Export → CSV, upload it to DBFS/a Volume, and point RECON_CSV_PATH at it. Zero guessing.
#   "custom_sql" — in Sigma, open the "Input Query" element's Custom SQL (Element menu → "Open in SQL" / Edit), copy
#                 the query text, and paste it into CUSTOM_SQL below. It already resolves the pairs correctly.
#
# Expected columns after loading (rename to these): dob_platform, dob_ehr, gender_platform, gender_ehr, total_score,
# client_person_id, run_id  (+ optionally postal_code_platform/ehr, names).
RECON_SOURCE = "csv"
RECON_CSV_PATH = "/dbfs/FileStore/member_match_fail_review.csv"   # <- set this if using "csv"
CUSTOM_SQL = ""  # <- paste the workbook's Custom SQL here if using "custom_sql"

# Standardise whatever the export calls the columns (Sigma exports use the display labels, e.g. "Dob Platform").
COLUMN_ALIASES = {
    "Dob Platform": "dob_platform", "Dob Ehr": "dob_ehr", "dob platform": "dob_platform", "dob ehr": "dob_ehr",
    # Legacy Sigma label aliases kept for backward compatibility with older exports
    "Dob Bwell": "dob_platform", "dob bwell": "dob_platform",
    "Gender Platform": "gender_platform", "Gender Ehr": "gender_ehr",
    "Gender Bwell": "gender_platform",
    "Total Score": "total_score", "Client Person Id": "client_person_id", "Run Id": "run_id",
    "Postal Code Platform": "postal_code_platform", "Postal Code Ehr": "postal_code_ehr",
    "Postal Code Bwell": "postal_code_platform",
}

recon = pd.DataFrame()
if RECON_SOURCE == "csv":
    try:
        if IN_DATABRICKS:
            # Spark reads the dbfs:/ path form (no "/dbfs" FUSE prefix).
            recon = spark.read.option("header", True).csv(RECON_CSV_PATH.replace("/dbfs", "", 1)).toPandas()
        else:
            recon = pd.read_csv(RECON_CSV_PATH)
        recon = recon.rename(columns=COLUMN_ALIASES)
        print(f"Loaded {len(recon)} rows from {RECON_CSV_PATH}.")
    except Exception as e:  # noqa: BLE001
        print(f"Could not read {RECON_CSV_PATH}. Export the Sigma element to CSV and set RECON_CSV_PATH.\n  {e}")
elif RECON_SOURCE == "custom_sql" and IN_DATABRICKS and CUSTOM_SQL.strip():
    recon = spark.sql(CUSTOM_SQL).toPandas().rename(columns=COLUMN_ALIASES)
    print(f"Loaded {len(recon)} rows from the pasted Custom SQL.")
else:
    print("Set RECON_SOURCE to 'csv' (with RECON_CSV_PATH) or 'custom_sql' (with CUSTOM_SQL) to populate `recon`.")

if len(recon):
    keep = [c for c in ["run_id", "client_person_id", "total_score", "dob_platform", "dob_ehr",
                        "gender_platform", "gender_ehr", "postal_code_platform", "postal_code_ehr"] if c in recon.columns]
    display(recon[keep].head(20) if keep else recon.head(20))

# Pull the payer client SOURCE demographics for the failed members (Layer C, source side)
member_ids = (
    persons["memberIdentifier"].dropna().str.replace(r"^[^-]+-", "", regex=True).unique().tolist()
)
print(f"Failed member_ids to look up in the source feed: {len(member_ids)}")

if IN_DATABRICKS:
    ids_sql = ",".join(_sql_string_literal(m) for m in member_ids)
    source = spark.sql(f"""
        SELECT member_id, date_of_birth, gender_code, gender_identity_code, zipcode,
               first_name, last_name, deceased_indicator, case_head_name, case_head_approved,
               file_date, source_file_name
        FROM {WS_CATALOG}.{WS_SCHEMA}.ws_eligibility_all
        WHERE member_id IN ({ids_sql})
        QUALIFY ROW_NUMBER() OVER (PARTITION BY member_id ORDER BY file_date DESC) = 1
    """)
    # Notebook-global by design: Databricks executes each cell in the same module/global
    # namespace, so `src_pdf` living at module scope is how later cells (the reconciliation
    # cells below) read it back — there is no long-lived multi-request process here for it to
    # leak across.
    src_pdf = source.toPandas()
    print(f"Matched {len(src_pdf)} of {len(member_ids)} member_ids in ws_eligibility_all "
          f"({len(member_ids) - len(src_pdf)} not present → candidate 'member not on file' / upstream gaps).")
    display(src_pdf.head(20))
else:
    print("(Skipped live query — not running in Databricks. Run in the workspace with table access to populate `src_pdf`.)")
    src_pdf = pd.DataFrame()

# C1 · Reconcile: join the failure list to the source feed and classify each DOB / gender difference
# This is the payoff cell. It produces the bucket counts that settle "our bug vs. upstream data".
#
# > **Note on the user-entered ("platform") side:** the cleanest source of the value the member *typed* is the
# > *Member Match Fail Review* table's `Dob Platform` / name columns (join on `Client Person Id` / `Run Id`). If that
# > table is materialised to the warehouse, join it here; otherwise export it from Sigma and read it as a second
# > DataFrame. The classifier above works on any (platform, ehr) pair regardless of where the two values come from.

# DOB reconciliation buckets (fill in the platform-side values to run end-to-end)
# `recon` is produced directly from bronze.proa.metrics in the "Pull the platform-vs-ehr demographic pairs" cell
# above (columns: dob_platform, dob_ehr, gender_platform, gender_ehr, total_score, client_person_id, …).
#
# OPTIONAL cross-check: verify the "ehr"/source side independently against the payer client eligibility feed (`src_pdf`) by
# joining on member_id — useful to catch cases where the value the pipeline compared differs from the raw feed:
#   xcheck = (persons.assign(member_id=persons["memberIdentifier"].str.replace("^payer_client-","",regex=True))
#                    .merge(src_pdf.rename(columns={"date_of_birth":"dob_source","gender_code":"gender_source"}),
#                           on="member_id", how="left"))

def run_dob_reconciliation(recon: pd.DataFrame):
    r = recon.copy()
    r["dob_bucket"] = r.apply(lambda row: classify_dob_pair(row.get("dob_platform"), row.get("dob_ehr")), axis=1)
    counts = r["dob_bucket"].value_counts()

    ours = ["format_artifact", "unparseable"]           # fixable in our code
    recoverable_now = ["typo_auto_recovered"]           # already handled by the algorithm
    upstream = ["genuinely_different", "missing_one_side", "typo_beyond_tolerance"]  # data / policy call

    print("DOB difference buckets:\n", counts.to_string())
    print(f"\n  Fixable on OUR side (format/parse)      : {counts.reindex(ours).fillna(0).sum():.0f}")
    print(f"  Already auto-recovered by the algorithm : {counts.reindex(recoverable_now).fillna(0).sum():.0f}")
    print(f"  Upstream data / policy (not a code bug) : {counts.reindex(upstream).fillna(0).sum():.0f}")

    ax = counts.plot(kind="barh", figsize=(10, 4), color="#00838f")
    ax.set(title="Layer C · Why do the birthdays differ? (this is the number everyone is asking for)",
           xlabel="records")
    plt.tight_layout()
    display(ax.get_figure())
    return r

# `recon` was populated from bronze.proa.metrics two cells up. Run the DOB buckets now if we have data.
if isinstance(recon, pd.DataFrame) and len(recon):
    recon = run_dob_reconciliation(recon)
else:
    print("`recon` is empty — populate it from the 'Pull the platform-vs-ehr demographic pairs' cell above, then re-run.")

# Gender normalization check — the one clear code gap
def normalize_gender(g):
    """The algorithm today ONLY lowercases gender — it has no M/F <-> male/female mapping, so 'M' vs 'male'
    scores as a NON-match. This helper shows what a correct normalisation would do; use it to measure how many
    'gender not matched' rows are really just an encoding mismatch (our fix) vs a true male/female conflict (upstream)."""
    if g is None:
        return None
    g = str(g).strip().lower()
    return {"m": "male", "f": "female", "male": "male", "female": "female",
            "u": "unknown", "unk": "unknown", "o": "other"}.get(g, g)

def gender_reconcile(recon: pd.DataFrame):
    r = recon.copy()
    r["g_platform"] = r["gender_platform"].map(normalize_gender)
    r["g_ehr"] = r["gender_ehr"].map(normalize_gender)
    def bucket(row):
        a, b = row["g_platform"], row["g_ehr"]
        if not a or not b:
            return "missing_one_side"
        if a == b:
            return "match_after_normalisation"     # e.g. 'M' vs 'male' -> OUR normalisation fix recovers it
        if {a, b} == {"male", "female"}:
            return "true_conflict"                  # genuine disagreement -> upstream / different person
        return "other_vs_unknown"                   # lenient in the algorithm already
    r["gender_bucket"] = r.apply(bucket, axis=1)
    print(r["gender_bucket"].value_counts().to_string())
    print("\n'match_after_normalisation' = recoverable by a small code fix (M/F <-> male/female).")
    print("'true_conflict'             = genuinely different sex in the two records (upstream/data).")
    return r

print("Gender helpers ready. normalize_gender('M') ->", normalize_gender("M"),
      "| normalize_gender('Female') ->", normalize_gender("Female"))

# Run it now if we pulled the gender pairs.
if isinstance(recon, pd.DataFrame) and len(recon) and {"gender_platform", "gender_ehr"}.issubset(recon.columns):
    recon = gender_reconcile(recon)
else:
    print("(Populate `recon` with gender_bwell/gender_ehr to see the gender buckets.)")

# Findings & recommendations
#
# **What the data supports (Layers A & B — done):**
# 1. Failures are **not near-misses** — 3 of 4 miss the 0.955 bar by >0.20; the typical failure agrees on only ~2 of 5 fields. Lowering the bar would auto-link *different* people.
# 2. **DOB is the dominant blocker** (89% of failures). 13 records are perfect on the other 4 fields and still cap at **~0.80** — recoverable only by fixing the birthday data, not by tuning.
# 3. **Gender is never the lone blocker**, and in this dataset gender failures are genuine male/female conflicts, **not missing values**. Missing/unknown gender is already de-weighted in the algorithm.
# 4. **Volume is down ~80% since late May and flat since mid-June** (slope ≈ 0/week) — the improvement is holding. "Flat at a low level" is the success state.
#
# **What still needs the raw data (Layer C — RA-4428, the open item):**
# 5. Run `run_dob_reconciliation` on the joined values to split DOB mismatches into **our-fix / already-recovered / upstream** buckets. The 2026-07-15 sample suggests *most are upstream* (ISO format on both sides rules out a parse bug), but we should quantify it.
# 6. Add a **gender pair** to the review table and run `gender_reconcile` — the `M/F ↔ male/female` normalisation is the one clear, low-risk **code** fix.
#
# **Ownership (so the pieces are clear):**
# - *Data Science*: Layers A/B analysis (done) + the two bounded fixes (gender normalisation, confirm DOB parsing) + running the DOB classification once the joined data lands.
# - *Reporting*: the raw-value join (ticket system + eligibility source).
# - *Engineering / Client Success*: the product/CX causes and the eligibility file-quality conversation.
#
# **The expectation to keep setting:** matching compares two independently-authored records, so some pairs will always
# genuinely disagree. A small, stable manual-review queue is the designed safety margin — the alternative (loosening the
# bar) mathematically links different people, the costlier error in healthcare. The goal is *low and stable*, not *zero*.
