# Vendored ONC-derived test data

These three files are a **copy**, not a live dependency — vendored here so this repo's ONC
regression tests (`tests/test_onc_regression.py`, `tests/test_onc_population_regression.py`) run
standalone, without needing a second repo checked out alongside this one. This was a deliberate
reversal of the original design (`docs/ONC_REGRESSION_TEST_DESIGN.md`), which read these files
live from a sibling `cms-hte-patient-matching-test-set` checkout — see that doc's "Vendoring
decision" section for why.

## Provenance

| File | Source |
|---|---|
| `sample_labeled_pairs.jsonl` | `cms-hte-patient-matching-test-set` @ `evaluation/cases/sample_labeled_pairs.jsonl` |
| `population_queries.jsonl` | `cms-hte-patient-matching-test-set` @ `evaluation/cases/population_queries.jsonl` |
| `population_candidates.jsonl` | `cms-hte-patient-matching-test-set` @ `evaluation/cases/population_candidates.jsonl` |

Copied from `https://github.com/icanbwell/cms-hte-patient-matching-test-set`, repo commit
`050d9db4e88ae66d1268e21250b325be3a59d086` (files themselves last changed at commit
`7b191b1b90be0c79416fc033bafd0351953fb3a2`, 2026-09-01), on 2026-09-04.

Every record in these files ultimately traces back to the public **ONC 2017 Patient Matching
Algorithm Challenge dataset** (Office of the National Coordinator for Health IT — synthetic,
non-PHI), transformed by the sibling repo's own mutation/mining/construction code
(`mutations.py`, `hard_negatives.py`, `special_populations.py`, `normalization_edge_cases.py`,
`population_cases.py`). See that repo's `evaluation/cases/README.md` ("How this test data was
generated") for the full methodology, category definitions, and file format documentation - not
duplicated here to avoid a second copy of that explanation going stale.

## Refreshing this copy

**This does not update automatically.** If the sibling repo regenerates its dataset (new mutation
types, a labeling fix, a larger sample, etc.), this copy will silently drift unless someone
deliberately re-syncs it:

```bash
cp ../cms-hte-patient-matching-test-set/evaluation/cases/sample_labeled_pairs.jsonl tests/fixtures/onc/
cp ../cms-hte-patient-matching-test-set/evaluation/cases/population_queries.jsonl tests/fixtures/onc/
cp ../cms-hte-patient-matching-test-set/evaluation/cases/population_candidates.jsonl tests/fixtures/onc/
```

Update the commit hashes and date in the Provenance table above when you do, and re-run both ONC
tests to confirm the new data doesn't shift recall/precision/FPR/F1 past the checked-in thresholds
(`RECALL_FLOOR`, `FPR_CEILING`, etc. in each test file) - if it does, that's either a real
regression to investigate or a deliberate threshold update, not something to wave through.
