# Session 4 — Real-World FHIR Data Source for `rule_eval.py`, via Reproducible Queries

**Status:** pending
**Thread:** Evaluation & Statistical Rigor Framework
**Estimated size:** M — mostly a new Databricks notebook following an existing pattern, plus
wiring its output into session 3's `LabeledPair` shape.

> Read `../conventions.md` first.

## Outcome purpose

Session 3's ONC baseline proves the engine's self-match integrity on public, synthetic data —
necessary but not sufficient, since ONC's demographic distribution won't exactly match real
WellSense/b.well traffic. `conventions.md`'s statistical-rigor gate names this "Tier 2":
validating the engine's effect on real-population **collision rates** (how often distinct real
people share field-value combinations) — a well-posed question even without match/non-match
labels, unlike precision, which real unlabeled data structurally can't certify (see the
project's own conversation history on why precision needs certified negatives, which real,
unlabeled production data doesn't have). This session builds that real-data input as a
reproducible, PHI-safe query — not a one-off analysis that can't be rerun.

## Upstream sessions (must be completed first)

Session 3 — this session reuses its `rule_eval.py` wiring (the `LabeledPair` shape,
`compare()`/`format_report()` usage) and extends its report format; it does not make sense to
design this session's output shape independently of that one.

## Downstream sessions (unblocked by this one)

None structurally required — Tier 2 is encouraged, not a hard gate on any other session (see
`conventions.md`). Sessions 5/6 may optionally reference this session's collision-rate output
when justifying a P(collision) or Table 2 change, but don't depend on it to reach
`completed/`.

## Upstream data/system dependencies

Real FHIR Patient/Person match data in Databricks and/or MongoDB. **`NEEDS HUMAN DECISION —
Sean`:** the exact catalog/schema/table names for the FHIR Patient/Person resources and their
existing match links are not known at authoring time (2026-07-28) — the handoff doc
(`docs/handoff/README.md`) names `bronze.proa.metrics` and `bronze.wellsense.ws_eligibility_all`
for WellSense-specific error analysis, but does not name a general FHIR Patient/Person store.
**Resolve this at session-start**, per `conventions.md`'s protocol step 4, before writing any
query code — ask Sean for: (a) the catalog/schema/table holding normalized FHIR Patient
resources, (b) the catalog/schema/table (or Mongo collection) holding existing Person-Patient
match links, and (c) whether both are reachable the same way
`wellsense_member_matching_analysis.py` reaches `bronze.*` (Databricks `spark.sql`), or if the
Mongo side needs a different connection pattern.

## Downstream data/system dependencies

None — this session's only output is a `ComparisonReport` (a human-readable artifact), not
data or a service other code depends on.

## Scope

### In scope
- A new Databricks notebook, `notebooks/fhir_match_data_source.py`, following
  `wellsense_member_matching_analysis.py`'s exact pattern: `dbutils.widgets` for
  catalog/schema/table names (with sane defaults matching whatever Sean confirms at
  session-start), the same `_validate_sql_identifier`/`_sql_string_literal` safety helpers
  (copy them verbatim — they're small, tested-by-inspection, and duplicating two ~10-line
  functions is cheaper than introducing a shared-utility import between `notebooks/` and
  itself, especially since `notebooks/` is explicitly scratch space per `conventions.md`),
  and a `spark.sql(...)` query built from validated identifiers only.
- The query itself pulls (a) a sample of normalized FHIR Patient resources and (b) their
  existing Person-Patient match links, joins them, and shapes the result into
  `rule_eval.LabeledPair` objects — with `strata={"source": "current_algorithm_link"}` on
  every pair, so downstream reports can filter/separate "does the new rule agree with the
  current algorithm" from any claim about ground-truth correctness (the current algorithm's
  links are not ground truth — see "Out of scope" below).
- Compute and report **collision rates** per field and per Table 2 combination (Tier 2): for
  each field (last name, DOB, phone, etc.), what fraction of *distinct* people in the sample
  share the same normalized value? Compare against Table 3's conservative u-probability
  assumptions (session 5) once session 5 exists — until then, just report the raw observed
  rates, so the comparison is a small addition later rather than a redesign.
- No data or query *output* is committed to this repo — only the parameterized query
  notebook itself (`notebooks/fhir_match_data_source.py`). Running it produces a
  `ComparisonReport`-shaped console/notebook-cell output that a human copies into wherever
  they're tracking session results (e.g. a PR description), never into a committed file.

### Out of scope
- Treating the current algorithm's existing Person-Patient links as ground truth for
  precision/recall. They're confounded — produced by the very algorithm this repo aims to
  replace or compare against — so this session reports **agreement rate** with the current
  algorithm's links (a descriptive statistic) and **collision rate** (a well-posed statistical
  quantity), never a precision/recall/FPR number derived from those links. If a future session
  is tempted to compute precision against this data, point them back to this note and to
  `conventions.md`'s Tier 3 language.
- Any change to production Databricks jobs, dashboards, or alerts (Zane's monitoring work,
  per the handoff doc, is separate and unaffected).
- Fixing `InMemoryBackend`'s scaling behavior — if this session's sample is large enough to
  need real blocking for local processing, sample smaller rather than fixing the backend here;
  that fix (if ever needed) is a separate candidate session.

## Tasks

1. **Resolve the `NEEDS HUMAN DECISION` above with Sean** before writing any code, per
   `conventions.md`'s protocol step 4. Record the answer here in *Execution notes* once
   resolved (not as a code comment — this decision belongs in the session doc's history, not
   buried in a notebook).

2. **Copy and adapt the query-safety pattern.**
   File: `notebooks/fhir_match_data_source.py` (new).
   Copy `_validate_sql_identifier`/`_sql_string_literal` from
   `notebooks/wellsense_member_matching_analysis.py` (lines 61-73 as of 2026-07-28) verbatim.
   Add widgets for whatever table names Task 1 resolved, e.g.:
   ```python
   dbutils.widgets.text("fhir_catalog", "<TBD from Task 1>", "FHIR Patient catalog")
   dbutils.widgets.text("fhir_schema", "<TBD from Task 1>", "FHIR Patient schema")
   dbutils.widgets.text("fhir_patient_table", "<TBD from Task 1>", "FHIR Patient table")
   dbutils.widgets.text("match_links_table", "<TBD from Task 1>", "Person-Patient match links table")
   dbutils.widgets.text("sample_size", "5000", "Row sample size (keep local processing tractable)")
   ```

3. **Write the query and the transform into `LabeledPair`s**, following session 3's
   `evaluation/onc_baseline.py::build_onc_pairs` as the shape to match (same `features={...}`
   keying convention, same use of `FieldExtractor`), but sourcing rows from the Spark
   DataFrame this notebook's query returns instead of `evaluation/onc_loader.py`'s CSV reader.
   The exact column names depend on Task 1's resolution — write this step for real once that's
   known; do not guess table-specific column names here.

4. **Compute and print collision rates per field**, comparing the sample's observed
   same-value-among-distinct-people rate against Table 3's conservative assumptions (available
   once session 5 exists — until then, just print the observed rate with a note "compare
   against Table 3 once session 5 lands").

## Unit tests required

Real Databricks/Mongo access can't be unit-tested locally. Test the parts that don't need a
live connection:

File: `notebooks/test_fhir_match_data_source.py` (new — note `notebooks/` is excluded from
the pre-commit gate but tests here still run under `make tests` if collected; confirm
`pyproject.toml`'s pytest config doesn't exclude `notebooks/` from collection before assuming
this, and adjust the test file's location to `evaluation/tests/` instead if it does, keeping
the transform logic itself in `notebooks/fhir_match_data_source.py` but testing it via a
plain import).

```python
import pytest

class TestSqlSafetyHelpers:
    """Same safety contract as wellsense_member_matching_analysis.py's helpers -
    copied verbatim, so copy its test cases too."""

    @pytest.mark.parametrize(
        "identifier,should_raise",
        [
            ("bronze.fhir.patient", False),
            ("bronze", False),
            ("bronze; DROP TABLE x", True),
            ("bronze.fhir.patient--", True),
            ("", True),
        ],
    )
    def test_validate_sql_identifier(self, identifier, should_raise):
        from notebooks.fhir_match_data_source import _validate_sql_identifier
        if should_raise:
            with pytest.raises(ValueError):
                _validate_sql_identifier(identifier)
        else:
            assert _validate_sql_identifier(identifier) == identifier

    def test_sql_string_literal_escapes_quotes(self):
        from notebooks.fhir_match_data_source import _sql_string_literal
        assert _sql_string_literal("o'brien") == "'o''brien'"
```

## Validation (definition of "resolved")

- [x] The `NEEDS HUMAN DECISION` above is resolved and recorded in *Execution notes* before
      any query code is written.
- [x] `notebooks/fhir_match_data_source.py` exists, uses widget-based configuration (no
      hardcoded table names), and reuses the validated-identifier pattern for every
      interpolated value.
- [ ] Running the notebook (in Databricks, with real access) produces `LabeledPair`s
      shaped identically to session 3's, each tagged `strata={"source": "current_algorithm_link"}`.
      **Not yet run** — this executing agent has no Databricks access; the code path is
      implemented and unit-tested at the transform level (see *Execution notes*), but the
      live end-to-end run, and the `_uuid`-join-key empirical check it prints, is outstanding.
- [x] Collision-rate output is printed per field, with an explicit note that it is descriptive
      (Tier 2), not a precision/recall claim. (Implemented and compared against session 5's
      Table 3 `FIELD_U_PROBS`; not yet exercised against live data — see above.)
- [x] No real data, query output, or table contents are committed to this repo — only the
      notebook file itself.
- [x] The SQL-safety unit tests pass: `uv run pytest notebooks/test_fhir_match_data_source.py -v` (15 passed, with `numpy` available; skips cleanly without it, matching `evaluation/`'s existing convention).
- [x] `make tests` is green (verified via `uv run pytest .`, CI's actual full-suite command per `.github/workflows/build_and_test.yml` — the Docker-based `make tests` target only runs the top-level `tests/` stub and doesn't reflect the real suite; flagged separately, not fixed here since it's out of this session's scope).

## Open questions

- **`NEEDS HUMAN DECISION — Sean`** (already stated above under "Upstream data/system
  dependencies"): the exact catalog/schema/table names for FHIR Patient resources and
  Person-Patient match links, and whether Mongo needs a different access pattern than
  Databricks `spark.sql`. Recommended default if genuinely stuck: start with whatever table
  the handoff doc's `enterprise-person-service` logs reference (per `docs/handoff/README.md`
  §2.4's data table), since that's the closest named real-data source already documented for
  this project, and confirm with Sean before treating it as authoritative.
  **RESOLVED 2026-08-06 (Zack):** see *Execution notes* below.

## Execution notes

**2026-08-06 — `NEEDS HUMAN DECISION` resolved by Zack:**
- FHIR Patient resources: `bronze.fhir_lake.patient_4_0_0` (standard FHIR R4 Patient shape —
  `name`, `birthDate`, `telecom`, `address`, `identifier`, `gender`, plus a platform-internal
  `_uuid` cross-reference field used by every `reference`-typed struct elsewhere in the same
  schema, e.g. `generalPractitioner[]._uuid`).
- Person-Patient match links: `silver.fhir_lite.person_patient` (`person_uuid`,
  `patient_uuid`).
- Both are Databricks tables reachable via `spark.sql` — **no Mongo access pattern is
  needed**, simplifying part (c) of the original question away entirely.
- The join key is `patient._uuid = person_patient.patient_uuid` — a high-confidence inference
  from schema-wide `_uuid` naming (not independently confirmed against real row data, since
  the schema was retrieved without ever selecting row-level values, per the PHI guardrail).
  `notebooks/fhir_match_data_source.py` prints the joined-row count against the requested
  `sample_size` the first time it runs in Databricks specifically so this assumption is
  verified empirically rather than trusted blindly — a near-zero join rate would mean it's
  wrong for this workspace and needs re-checking with Sean/Zack.

**2026-08-06 — Session executed:**
- `notebooks/fhir_match_data_source.py` implements the widget-configured join (Task 2),
  the `LabeledPair` transform (Task 3, mirroring `onc_baseline.build_onc_pairs`'s shape),
  and per-field collision-rate reporting (Task 4) — extended beyond the original Task 4 to
  do the Table 3 comparison *now* rather than deferring it, since session 5 (Table 3
  u-probabilities) is already in `completed/` as of this session's start, so
  `patient_matching/matching/collision.py`'s `FIELD_U_PROBS` was available to compare
  against directly.
- Also added an **agreement-rate** helper (not explicitly scoped in Task 4, but implied by
  the Outcome purpose's "strata enables filtering on agreement with the current algorithm"):
  reports how often the candidate `MatchingEngine` agrees with the current algorithm's
  existing `person_uuid` links — explicitly logged as descriptive only, never a
  precision/recall claim, per "Out of scope."
- Collision-rate coverage is limited to the 11 fields `FieldExtractor` currently populates
  (`first_name`, `last_name`, `dob`, `street_line`, `phone`, `email`, `ssn_last4`,
  `itin_last4`, `mbi`, `legal_id`, `namespace_id`) — `zip_code`/`city`/`state`/
  `insurance_member_id`/`insurance_subscriber_id` aren't extracted yet (v3.3 additions,
  session 6's scope), so they're absent from this session's report rather than guessed.
- Unit tests (`notebooks/test_fhir_match_data_source.py`) cover the SQL-safety helpers,
  the join-row-to-Patient-dict transform, pair-building (true-match-from-shared-person_uuid,
  cross-person negative sampling), and the collision-rate estimator — all pure-Python logic
  that doesn't need a live Spark session, per "Unit tests required." The real query/transform
  end-to-end path can only be validated by running the notebook in Databricks with actual
  workspace access (not done here) — that run is the outstanding empirical check for the
  `_uuid` join-key assumption above.
- `make tests` equivalent (`uv run pytest .`) is green: 373 passed, 3 skipped (2 pre-existing
  numpy-gated `evaluation/` tests + this session's own numpy-gated test file, following
  `evaluation/test_rule_eval.py`'s established `pytest.importorskip("numpy")` convention
  since `notebooks/fhir_match_data_source.py` imports `LabeledPair` from `evaluation/
  rule_eval.py`). `uv run pre-commit run --all-files` is clean (notebooks/evaluation are
  excluded from that gate per `.pre-commit-config.yaml`; `ruff check` was run manually against
  the new files per the "Testing structure" gotcha and passes — `ruff format` reports the
  file as unformatted, but so does the pre-existing, already-merged
  `wellsense_member_matching_analysis.py`, confirming notebooks/ isn't format-enforced in
  this repo today, not a regression introduced here).
- Not exempt from the statistical rigor gate at Tier 1 in the strict sense (this session adds
  no new matching *behavior* — no rule, threshold, or comparator change — only an evaluation
  data source), so no new ONC `ComparisonReport` was generated; session 3's existing baseline
  is unaffected.
- PR opened: [#22](https://github.com/icanbwell/patient-matching/pull/22), per "Every session
  ends with a PR"; left **open** rather than merged immediately — merging is Zack's/Sean's
  call, not assumed here. Doc moved to `in_review/`, not `completed/`, until the PR merges.
