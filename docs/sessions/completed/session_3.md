# Session 3 — ONC Self-Match Baseline Wired to `rule_eval.py`

**Status:** pending
**Thread:** Evaluation & Statistical Rigor Framework
**Estimated size:** M/L — a new pairwise matcher API, an ONC data transform, sampled negative
pair generation, and the first real `ComparisonReport` this repo has ever produced.

> Read `../conventions.md` first.

## Outcome purpose

This repo's matching methodology has no independent "these two records are/aren't the same
person" ground truth beyond the statistical framework itself (Fellegi-Sunter P(collision)),
so every future rule change (v3.3's 37 rules, the P(collision) evaluator, any fuzzy-match
tuning) has to be evaluated for its effect on false-positive rate and recall, not shipped on
judgment alone — that's `conventions.md`'s statistical-rigor gate, Tier 1. Tier 1 requires an
`evaluation/rule_eval.py`-produced `ComparisonReport`, but `rule_eval.py` has never been wired
to any real matcher or dataset (`evaluation/test_rule_eval.py` only exercises it against toy
inline data). This session makes it real: load the public ONC patient-matching benchmark,
turn `MatchingEngine`'s rule logic into something `rule_eval.py` can score, and produce the
first actual baseline report for the current (v3.2.2, 26-rule) engine. Every later
rule-changing session compares against this baseline.

## Upstream sessions (must be completed first)

None — valid start point.

## Downstream sessions (unblocked by this one)

Session 4 (real-world data source) shares this session's `rule_eval.py` wiring and report
format. Sessions 5 and 6 (P(collision) evaluator, Table 2 v3.3 expansion) need this session's
Tier-1 report to exist before they can move to `completed/` (see `conventions.md`'s
statistical rigor gate) — they can be coded in parallel with this session, just not merged
before it.

## Upstream data/system dependencies

- The public ONC 2017 Patient Matching Algorithm Challenge dataset. A copy of its 9 alphabetic
  CSV shards already exists in the sibling repo `helix.personmatching`, at
  `tests/cms_dataset/files/onc/*.csv` (confirmed present via direct inspection, 2026-07-28: 9
  shard files, e.g. `ONC Patient Matching Algorithm Challenge Test Dataset.A-C.csv`). Copy
  those files into this repo (Task 1) — they are public, de-identified data, not PHI, so this
  is a legitimate exception to the "don't duplicate external content" principle in
  `conventions.md`'s "Reference documents" section (that principle is about live/mutable
  documents this repo doesn't own; this is a static, versioned, published benchmark).

## Downstream data/system dependencies

`evaluation/fixtures/onc/*.csv` (copied data) and the baseline `ComparisonReport` this session
produces become the reference point for every later rule-changing session's Tier-1 evidence.

## Scope

### In scope
- Copy the ONC CSV shards from `helix.personmatching/tests/cms_dataset/files/onc/` into
  `evaluation/fixtures/onc/` in this repo.
- Write a CSV -> normalized-FHIR-Patient transform (`evaluation/onc_loader.py`), covering the
  same columns `helix.personmatching`'s `create_patient_resource()` maps (confirmed via direct
  inspection, 2026-07-28: `EnterpriseID, LAST, FIRST, MIDDLE, SUFFIX, DOB, GENDER, SSN,
  ADDRESS1, ADDRESS2, ZIP, MOTHERS_MAIDEN_NAME, MRN, CITY, STATE, PHONE, PHONE2, EMAIL,
  ALIAS`), extended to also populate two fields `helix.personmatching`'s transform drops on
  the floor: `MOTHERS_MAIDEN_NAME` (maps to an additional entry in `last_names` via a
  `_previousFamily`-style extension our `FieldExtractor` doesn't currently read — see Task 2's
  explicit note on this) and `ALIAS` (maps to an additional `first_names` entry). `MRN` and
  `PHONE2` remain unmapped, matching `helix.personmatching` (no rule in this repo's Table 2
  uses a bare MRN or a second phone number).
- Add `MatchingEngine.evaluate_pair(query_fields, candidate_fields) -> bool`: a new public
  method factoring the existing per-candidate rule-evaluation logic (today spread across
  `_evaluate_rule` + `_suffix_conflict`, called once per candidate inside `match()`) into a
  standalone pairwise decision, so it can be wrapped as a `rule_eval.Matcher` without
  duplicating logic. `match()` itself is left completely unchanged — `evaluate_pair()` is
  purely additive, so there is no refactor risk to the existing method.
- Build labeled pairs for `rule_eval.py` from the ONC data:
  - **True-match pairs**: `(record, masked(record))` for each ONC record, across two
    scenarios meaningful to this engine's actual field set: `none` (the unmasked self-pair,
    a baseline sanity check) and `drop_email_phone` (removes contact-channel fields, forcing
    reliance on name/DOB/address-based rules) — `is_true_match=True`, since masking some
    fields doesn't change who the record actually belongs to. This tests recall under
    realistic partial data, not a trivial always-true self-compare. Narrower than
    `helix.personmatching`'s 4 scenarios, since two of theirs (`drop_gender`,
    `gender_unknown`) would be no-ops here: this engine's `PatientFields` has no `gender`
    field at all (gender isn't a Table 2 matching field, consistent with CMS v3.3 dropping
    it entirely).
  - **True-non-match pairs**: a *sampled* set of cross pairs `(record_i, record_j)`, `i != j`
    — ONC guarantees every row is a distinct individual, so any two distinct rows are a
    genuine non-match, `is_true_match=False`. This is where the "blocking and local memory
    constraints" problem Sean raised actually bites: full pairwise cross-reference of ~28,000
    ONC records is ~400 million pairs, intractable to generate or score. Sample instead — use
    `rule_eval.min_sample_size` to size the negative sample for a specific detectable FPR
    delta (Task 4 below), rather than exhaustively enumerating all non-match pairs. This is
    the correct fix for *this* session's memory-constraint problem — a separate, related
    problem (making `InMemoryBackend.search()` itself scale for a real `match()` call against
    a large corpus, e.g. for session 4 or eventual production-shaped batch runs) is real but
    explicitly out of scope here (see "Out of scope" below); don't conflate the two.
- Run `rule_eval.compare()` with the current (v3.2.2, 26-rule) engine as *both* baseline and
  candidate (a self-comparison — there's no "candidate" change to evaluate yet; this session's
  job is to produce the reference point, not evaluate a change). Save the resulting
  `format_report()` text output to `evaluation/baselines/v3_2_2_onc_baseline.txt` so later
  sessions have a committed reference to diff against.

### Out of scope
- Fixing `InMemoryBackend.search()`'s O(n) linear-scan-per-query behavior with a real indexed
  blocking key. This matters for actual `match()`/`match_batch()` calls against a large
  corpus (relevant to session 4 and any future production-shaped work), but this session's
  `rule_eval.py` wiring uses `evaluate_pair()` directly on precomputed pairs, never calling
  `InMemoryBackend.search()` at all — so it doesn't need this fix to succeed. Track the
  backend-indexing fix as a candidate future session if a later session's use of
  `InMemoryBackend` against the full ONC corpus turns out to need it.
- Computing real precision/recall/FPR on real-world (non-ONC) data — that's session 4 (Tier 2)
  and, at population scale, Tier 3 (explicitly not a near-term blocker).
- Any change to which Table 2 rules exist or their P(collision) values — that's sessions 5/6.
  This session evaluates the *current* 26-rule v3.2.2 engine as-is.

## Tasks

1. **Copy the ONC fixtures.**
   ```bash
   mkdir -p evaluation/fixtures/onc
   cp ~/git/helix.personmatching/tests/cms_dataset/files/onc/*.csv evaluation/fixtures/onc/
   ```
   Verify: `ls evaluation/fixtures/onc/*.csv | wc -l` should print `9`.

2. **Write the ONC transform.**
   File: `evaluation/onc_loader.py` (new).
   ```python
   """Load the public ONC Patient Matching Algorithm Challenge dataset as normalized
   FHIR Patient dicts, for use as evaluation/rule_eval.py input.

   Column mapping mirrors helix.personmatching's create_patient_resource() (see
   tests/cms_dataset/test_cms_dataset.py in that repo), extended to also populate
   MOTHERS_MAIDEN_NAME and ALIAS, which that transform reads from the CSV but never
   maps into the output FHIR resource.
   """

   from __future__ import annotations

   import csv
   from datetime import date, timedelta
   from pathlib import Path
   from typing import Any, Dict, List

   _SAS_EPOCH = date(1900, 1, 1)
   _GENDER_MAP = {"MALE": "male", "FEMALE": "female", "U": "unknown"}


   def _decode_sas_date(raw: str) -> str:
       """ONC's DOB column is a SAS-style day-offset from 1900-01-01, minus 2."""
       offset_days = int(raw) - 2
       return (_SAS_EPOCH + timedelta(days=offset_days)).isoformat()


   def _row_to_patient(row: Dict[str, str]) -> Dict[str, Any]:
       given = [row["FIRST"]]
       if row.get("MIDDLE"):
           given.append(row["MIDDLE"])
       if row.get("ALIAS"):
           given.append(row["ALIAS"])
       family_names = [row["LAST"]]
       # Not mapped by helix.personmatching's transform - included here so this
       # repo's normalization/matching sees prior/maiden names per Core Principle 10.
       if row.get("MOTHERS_MAIDEN_NAME"):
           family_names.append(row["MOTHERS_MAIDEN_NAME"])

       patient: Dict[str, Any] = {
           "resourceType": "Patient",
           "id": row["EnterpriseID"],
           "name": [
               {"family": fam, "given": given, "suffix": [row["SUFFIX"]] if row.get("SUFFIX") else []}
               for fam in family_names
           ],
           "gender": _GENDER_MAP.get(row.get("GENDER", "").upper(), "unknown"),
           "birthDate": _decode_sas_date(row["DOB"]),
           "telecom": [],
           "address": [],
           "identifier": [],
       }
       if row.get("PHONE"):
           patient["telecom"].append({"system": "phone", "value": row["PHONE"]})
       if row.get("EMAIL"):
           patient["telecom"].append({"system": "email", "value": row["EMAIL"]})
       if row.get("ADDRESS1"):
           lines = [row["ADDRESS1"]] + ([row["ADDRESS2"]] if row.get("ADDRESS2") else [])
           patient["address"].append(
               {"line": lines, "city": row.get("CITY", ""), "state": row.get("STATE", ""), "postalCode": row.get("ZIP", "")}
           )
       if row.get("SSN"):
           patient["identifier"].append({"system": "http://hl7.org/fhir/sid/us-ssn", "value": row["SSN"]})
       return patient


   def load_onc_patients(csv_paths: List[Path]) -> List[Dict[str, Any]]:
       """Load one or more ONC shard CSVs into normalized FHIR Patient dicts."""
       patients: List[Dict[str, Any]] = []
       for path in csv_paths:
           with open(path, newline="", encoding="utf-8") as f:
               for row in csv.DictReader(f):
                   patients.append(_row_to_patient(row))
       return patients
   ```
   Note: this repo's normalization pipeline (`patient_matching/normalization/`) expects
   already-lowercased/diacritic-folded values; run each patient through
   `NormalizationManager` (see `patient_matching/normalization/manager.py`) before extraction,
   the same way any other caller of `MatchingEngine` must, rather than duplicating
   normalization logic inside `onc_loader.py`.

3. **Add the pairwise matcher API.**
   File: `patient_matching/matching/matching_engine.py`.
   Add a new public method to `MatchingEngine`, extracting today's per-candidate logic:
   ```python
   def evaluate_pair(
       self, query_fields: PatientFields, candidate_fields: PatientFields
   ) -> bool:
       """Decide whether two already-extracted field sets match, per Table 2.

       This is the pure pairwise decision (no backend search, no uniqueness
       check) - the same logic match() applies per candidate, factored out so
       it can be used directly against precomputed pairs (see
       evaluation/onc_baseline.py) without needing a MatchingBackend at all.
       """
       for rule in self._rules:
           evaluation = self._evaluate_rule(rule, query_fields, candidate_fields)
           if evaluation.matched and not self._suffix_conflict(
               query_fields.suffixes, candidate_fields.suffixes
           ):
               return True
       return False
   ```
   Do not modify `match()` at all — `evaluate_pair()` is new, additive code only. Note one
   known, documented limitation: `evaluate_pair()` checks a candidate's full known-value sets
   directly, while `match()`'s blocking (`_build_criteria`) only blocks on a single
   representative value per field before verification — so for a candidate with multiple
   values in a blocked field (e.g. multiple historical last names), the two paths are not
   guaranteed to agree. This is acceptable for the self-match-integrity use case in this
   session (each ONC record's masked variants share the same underlying values), but would
   need revisiting before reusing `evaluate_pair()` against genuinely multi-valued production
   data.

4. **Build labeled pairs and size the negative sample.**
   File: `evaluation/onc_baseline.py` (new).
   ```python
   """Build rule_eval.py LabeledPairs from the ONC dataset, and run the current
   engine's self-match baseline (session 3 of docs/sessions/).
   """

   from __future__ import annotations

   import random
   from pathlib import Path
   from typing import Any, Dict, List

   from evaluation.onc_loader import load_onc_patients
   from evaluation.rule_eval import LabeledPair, compare, format_report, min_sample_size
   from patient_matching.matching.field_extractor import FieldExtractor
   from patient_matching.matching.matching_engine import MatchingEngine
   from patient_matching.matching.in_memory_backend import InMemoryBackend

   MASKING_SCENARIOS = ("none", "drop_email_phone")


   def _mask(patient: Dict[str, Any], scenario: str) -> Dict[str, Any]:
       if scenario == "drop_email_phone":
           return {**patient, "telecom": []}
       return dict(patient)


   def build_onc_pairs(
       patients: List[Dict[str, Any]], *, n_negative_samples: int, seed: int = 0
   ) -> List[LabeledPair]:
       extractor = FieldExtractor()
       pairs: List[LabeledPair] = []

       # True-match pairs: each record against each masked variant of itself.
       for p in patients:
           q_fields = extractor.extract(p)
           for scenario in MASKING_SCENARIOS:
               c_fields = extractor.extract(_mask(p, scenario))
               pairs.append(
                   LabeledPair(
                       features={"query": q_fields, "candidate": c_fields},
                       is_true_match=True,
                       strata={"scenario": scenario},
                       pair_id=f"{p['id']}::{scenario}",
                   )
               )

       # True-non-match pairs: a random sample of distinct-record cross pairs.
       # ONC guarantees every row is a distinct individual, so any (i, j), i != j
       # pair is a genuine non-match - sampling avoids the O(n^2) full cross-product.
       rng = random.Random(seed)
       n = len(patients)
       seen = set()
       while len(seen) < n_negative_samples:
           i, j = rng.randrange(n), rng.randrange(n)
           if i == j or (i, j) in seen or (j, i) in seen:
               continue
           seen.add((i, j))
           q_fields = extractor.extract(patients[i])
           c_fields = extractor.extract(patients[j])
           pairs.append(
               LabeledPair(
                   features={"query": q_fields, "candidate": c_fields},
                   is_true_match=False,
                   strata={"scenario": "cross_pair"},
                   pair_id=f"{patients[i]['id']}::{patients[j]['id']}",
               )
           )
       return pairs


   def current_engine_matcher(features):
       """Adapts MatchingEngine.evaluate_pair to rule_eval.py's Matcher signature."""
       engine = MatchingEngine(backend=InMemoryBackend([]))  # backend unused by evaluate_pair
       return engine.evaluate_pair(features["query"], features["candidate"])


   if __name__ == "__main__":
       onc_dir = Path(__file__).parent / "fixtures" / "onc"
       patients = load_onc_patients(sorted(onc_dir.glob("*.csv")))
       # Size the negative sample to detect a 1-percentage-point FPR shift at a
       # ~0.1% baseline FPR, per rule_eval.py's own power-calculation utility.
       n_negative = min_sample_size(p0=0.001, delta=0.01)
       pairs = build_onc_pairs(patients, n_negative_samples=n_negative)
       report = compare(
           current_engine_matcher,
           current_engine_matcher,  # self-comparison: this run establishes the baseline
           pairs,
           baseline_name="v3.2.2 (26 rules)",
           candidate_name="v3.2.2 (26 rules)",
       )
       output_path = Path(__file__).parent / "baselines" / "v3_2_2_onc_baseline.txt"
       output_path.parent.mkdir(exist_ok=True)
       output_path.write_text(format_report(report))
       print(format_report(report))
   ```

5. **Generate and commit the baseline report.**
   ```bash
   mkdir -p evaluation/baselines
   docker compose run --rm dev python -m evaluation.onc_baseline
   ```
   This writes `evaluation/baselines/v3_2_2_onc_baseline.txt`. Commit it — it's the reference
   point sessions 5/6 diff against.

## Unit tests required

File: `evaluation/test_onc_baseline.py` (new, sibling to the existing `evaluation/test_rule_eval.py`).

```python
import pytest
from evaluation.onc_loader import _decode_sas_date
from evaluation.onc_baseline import build_onc_pairs, current_engine_matcher
from evaluation.rule_eval import LabeledPair

class TestOncTransform:
    @pytest.mark.parametrize(
        "raw_offset,expected_iso",
        [
            ("2", "1900-01-01"),   # offset 0 after the -2 correction
            ("367", "1901-01-01"), # 365 days later (1900 is not a leap year)
            ("36527", "2000-01-02"),
        ],
    )
    def test_decode_sas_date_boundaries(self, raw_offset, expected_iso):
        assert _decode_sas_date(raw_offset) == expected_iso

class TestEvaluatePairEquivalence:
    """MatchingEngine.evaluate_pair should agree with match()'s decision on this simple,
    single-valued-field case. This is a consistency check between the two decision paths,
    not a refactor-equivalence proof — see the known blocking-vs-full-value-set limitation
    noted in Task 3."""

    def test_evaluate_pair_agrees_with_match_for_matching_pair(self):
        from patient_matching.matching.field_extractor import FieldExtractor
        from patient_matching.matching.in_memory_backend import InMemoryBackend
        from patient_matching.matching.matching_engine import MatchingEngine

        def _patient(mbi):
            return {
                "resourceType": "Patient",
                "name": [{"family": "smith", "given": ["john"]}],
                "birthDate": "1980-01-01",
                "telecom": [],
                "address": [],
                "identifier": [{"system": "http://hl7.org/fhir/sid/us-mbi", "value": mbi}],
            }

        candidate = _patient("1abc2de3f45")
        candidate["id"] = "cand-1"
        backend = InMemoryBackend([candidate])
        engine = MatchingEngine(backend=backend)
        query = _patient("1abc2de3f45")

        match_result = engine.match(query)
        extractor = FieldExtractor()
        pairwise_result = engine.evaluate_pair(
            extractor.extract(query), extractor.extract(candidate)
        )

        assert (match_result.outcome.value == "match") == pairwise_result

class TestBuildOncPairs:
    def test_true_match_pairs_outnumber_or_equal_masking_scenarios(self):
        from evaluation.onc_baseline import MASKING_SCENARIOS
        patients = [{"id": "p1", "name": [{"family": "smith", "given": ["john"]}], "birthDate": "1980-01-01", "telecom": [], "address": [], "identifier": []}]
        pairs = build_onc_pairs(patients, n_negative_samples=0)
        true_pairs = [p for p in pairs if p.is_true_match]
        assert len(true_pairs) == len(MASKING_SCENARIOS)

    def test_negative_sample_count_is_respected(self):
        patients = [
            {"id": f"p{i}", "name": [{"family": "smith", "given": ["john"]}], "birthDate": "1980-01-01", "telecom": [], "address": [], "identifier": []}
            for i in range(10)
        ]
        pairs = build_onc_pairs(patients, n_negative_samples=5, seed=0)
        negative_pairs = [p for p in pairs if not p.is_true_match]
        assert len(negative_pairs) == 5

    def test_negative_pairs_never_pair_a_record_with_itself(self):
        patients = [
            {"id": f"p{i}", "name": [{"family": "smith", "given": ["john"]}], "birthDate": "1980-01-01", "telecom": [], "address": [], "identifier": []}
            for i in range(10)
        ]
        pairs = build_onc_pairs(patients, n_negative_samples=8, seed=1)
        for p in pairs:
            if not p.is_true_match:
                q_id, c_id = p.pair_id.split("::")
                assert q_id != c_id
```

## Validation (definition of "resolved")

- [ ] `evaluation/fixtures/onc/` contains all 9 ONC CSV shards.
- [ ] `evaluate_pair()` exists on `MatchingEngine` as new, additive code; `match()` is left
      unchanged; the consistency test (`TestEvaluatePairEquivalence`) passes, confirming the
      two paths agree on the simple case it covers.
- [ ] `build_onc_pairs()` produces both true-match (masked-self) and true-non-match (sampled
      cross) pairs, with the negative-sample count controllable and never pairing a record
      with itself.
- [ ] Running `python -m evaluation.onc_baseline` produces a `ComparisonReport` and writes
      `evaluation/baselines/v3_2_2_onc_baseline.txt`, which is committed.
- [ ] All new tests pass: `docker compose run --rm dev pytest evaluation/test_onc_baseline.py -v`
- [ ] `make tests` is green (full suite, including the existing `test_matching_engine.py` and
      `evaluation/test_rule_eval.py` — since `match()` is unmodified, neither should regress).
- [ ] `make run-pre-commit` is clean for all touched files under `patient_matching/` (note:
      `evaluation/` is excluded from pre-commit hooks per `conventions.md` — run
      `ruff check evaluation/` and `mypy evaluation/` manually and fix anything they flag,
      since "excluded from the automated gate" doesn't mean "exempt from the standard").

## Open questions

- The negative-sample size in Task 4 (`min_sample_size(p0=0.001, delta=0.01)`) assumes a
  ~0.1% baseline FPR and targets detecting a 1-percentage-point shift — a reasonable starting
  assumption, not a value with real data behind it yet. **Recommended default:** ship with
  this value; if session 5/6's `ComparisonReport`s come back with FPR credible intervals too
  wide to be useful (`NEEDS MORE DATA` verdicts that don't resolve), revisit the sample size
  then, informed by the actual observed FPR rather than a guess. Not a `NEEDS HUMAN DECISION`
  — this is exactly the kind of algorithm-tuning choice principle 5 says the session author
  resolves directly.

## Execution notes

Executed 2026-07-29 on branch `claude/session-3-onc-baseline`, cut from and PR'd into `main`
(not `claude/cms-matching-v1` as `conventions.md` originally said — that branch merged into
`main` earlier the same day, commit `cf9b71b`; `conventions.md` updated in this session's PR
to point at `main` going forward, with a historical note left in place).

Deviations from this doc's original plan, all discovered empirically while executing, not
guessed in advance:

- **Dataset is 1,000,000 ONC records across the 9 shards, not ~28,000** as this doc's
  intractability argument for negative sampling assumed. Doesn't change the approach (negative
  sampling was already the right call, now even more so), but it does mean true-match pairs
  (2,000,000 - every record x 2 masking scenarios, not sampled) dominate eval-set size. Timed
  end-to-end: ~17s CSV load, ~3.5min pair-building (dominated by `NormalizationManager`), ~2min
  for `rule_eval.compare()`'s 4 full passes over the pair set. A few minutes total - fine for a
  one-off script, not part of any hot path.
- **`_GENDER_MAP` needed `M`/`F` single-letter codes**, not just `MALE`/`FEMALE`/`U` - confirmed
  against the real CSVs (both forms appear) and cross-checked against
  `helix.personmatching`'s `create_patient_resource()`, which handles both. Irrelevant to
  match correctness (`FieldExtractor` never reads `gender`, since CMS v3.3 drops it as a
  matching field) but wrong data in a "normalized FHIR Patient" fixture is worth getting right.
- **Blank `DOB` values exist** (the dataset's `Null.csv` shard is deliberately incomplete) -
  `onc_loader.py` now only sets `birthDate` when `DOB` is present, mirroring
  `helix.personmatching`'s own `if row["DOB"]:` guard, instead of crashing on `int("")`.
- **The draft `onc_baseline.py` in this doc skipped `NormalizationManager`** before
  `FieldExtractor.extract()`. Task 2's own note says normalization is required, but the Task 4
  code sample didn't call it. Since `FieldComparator.exact_match` is a case-sensitive set
  intersection and raw ONC CSV values are mixed-case, skipping this would have made every
  field comparison fail silently - the "baseline" would have measured nothing. Fixed by
  normalizing once per patient before masking/extraction in `build_onc_pairs()`.
- **Packaging gap exposed by this session's own new code, fixed as a prerequisite**:
  `patient_matching` has no `[build-system]` in `pyproject.toml` and is not actually installed
  (editable or otherwise) - it only resolves via pytest's own sys.path insertion, which walks
  up through `__init__.py`-containing directories. `evaluation/` has no `__init__.py`, so
  pytest was inserting `evaluation/` itself onto `sys.path` for `evaluation/test_*.py`, never
  reaching repo root - meaning `evaluation/test_onc_baseline.py` (the first `evaluation/` test
  to need `patient_matching`) broke collection of the **entire** `pytest .` suite, since
  `evaluation/` sorts alphabetically before `patient_matching/` and pytest imports test modules
  as it collects them. Fixed with an empty root-level `conftest.py`, which pytest loads before
  collecting any test module, guaranteeing repo root is on `sys.path` from the start of the
  session. Verified this was a real, order-dependent full-suite break (not just a targeted-file
  artifact) before fixing it. `evaluation/onc_baseline.py` and `test_onc_baseline.py` use bare
  imports (`from onc_loader import ...`) for evaluation/-internal cross-references, matching
  `test_rule_eval.py`'s existing convention, to avoid mypy's "found twice under different
  module names" error that dotted `evaluation.X` imports caused; the one-off baseline-generation
  run therefore uses `PYTHONPATH=. python evaluation/onc_baseline.py`, not this doc's original
  `python -m evaluation.onc_baseline` (that invocation makes `evaluation` the running module's
  package, which conflicts with the bare-import style needed for the reasons above).
- **`docker compose run --rm dev pytest ...` / `make tests`** (Docker-based) currently fails
  full-suite collection on an unrelated, pre-existing defect: `duckdb`'s compiled extension
  can't load `libstdc++.so.6` under this image's Alpine/musl base
  (`patient_matching/api/tests/*`, `patient_matching/cache/tests/*`). Confirmed this is not
  caused by this session: this file's own tests collect and skip cleanly under Docker in
  isolation (numpy absent there, same as CI - see below), and the failure is in files this
  session never touched. This is almost certainly why CI itself moved off Docker for tests
  (commit `d51b080`, "Run pre-commit and tests directly via uv instead of Docker in CI",
  predates this session). Validated instead via `uv run pytest .` and
  `uv run pre-commit run --all-files`, which is what CI's `build_and_test.yml` actually runs
  (`uv sync --frozen --all-extras --group dev` + `uv run pytest .`) - green: 325 passed, 2
  skipped (the two `evaluation/` harness tests, cleanly, via `pytest.importorskip("numpy")` -
  numpy/scipy/pandas/matplotlib are optional harness-only deps per `evaluation/rule_eval.py`'s
  own docstring, not part of `pyproject.toml`, so CI never installs them and these tests always
  skip there, same as `test_rule_eval.py` already did before this session). Manually verified
  the actual test *logic* passes by installing numpy locally (`uv pip install numpy`) and
  re-running - 9/9 pass. Recommend a follow-up session to fix the Docker image's
  `libstdc++`/duckdb issue or retire `make tests`/the `dev` Dockerfile target in favor of the
  now-real `uv`-based flow, since the two have silently diverged.
- `ruff check evaluation/` and `mypy evaluation/` run manually (excluded from the pre-commit
  gate) against this session's 3 new files, with numpy/pandas/pandas-stubs/matplotlib/scipy
  installed locally per `evaluation/DESIGN.md`'s guidance, so real type errors weren't masked by
  missing-stub noise. Two pre-existing `mypy` findings in `rule_eval.py` (lines 266, 527) are
  untouched by this session and left alone, out of scope.
- Baseline result: TPR 0.9508, FPR 0.0011, Precision 1.0000, F1 0.9748 (self-comparison,
  `NEEDS MORE DATA` verdict as expected since baseline==candidate). The ~4.9% recall miss on
  masked self-pairs is a real, useful signal for future sessions (5/6): the current 26-rule
  engine can't always confirm a record against itself once email+phone are dropped, on top of
  whatever the ONC `Null` shard's missing fields already cost it.
- PR opened: https://github.com/icanbwell/patient-matching/pull/11, from
  `claude/session-3-onc-baseline` into `main`. Left open rather than auto-merged, since merging
  is a shared/visible action; Sean reviewed and merged it himself (merged 2026-07-30T04:28:33Z,
  commit `be1280e`). Moved from `in_review/` to `completed/` accordingly - see
  `docs/sessions/in_review/README.md` for why that's a separate step from opening the PR.
- While this session was `in_review/`, its existence surfaced a real gap: session 4 (and,
  before this doc moved here, the "start the next session" protocol's dependency check
  generally) had no way to distinguish "session 3's own work is finished" from "session 3's
  code is actually on `main`." Added `docs/sessions/in_review/` as a distinct lifecycle state
  to close that gap (`conventions.md` updated accordingly), and fed the same fix back into the
  reusable `~/git/session-planning-playbook.md` template, since the identical bug exists there
  for any project adopting this pattern.
