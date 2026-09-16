# ONC-derived test data (fetched, not committed)

These three files are **not committed to this repo**. They're downloaded on demand by
`scripts/fetch_onc_test_data.py` (`make fetch-onc-data`) from a pinned tag of the sibling
`cms-hte-patient-matching-test-set` repo, and gitignored (`/tests/fixtures/onc/*.jsonl`) here.

This repo previously committed a copy of these files directly. That was reversed: a committed
copy silently drifts from the source repo with no way to detect it short of manually re-copying
and remembering to update a provenance note. Fetching keeps the pin itself (two constants in
`scripts/fetch_onc_test_data.py`) as the single source of truth for which version of the data this
repo tests against, with no separate multi-megabyte file diff to review. The fetch itself resolves
against `SOURCE_COMMIT`, not the tag name — tags are mutable refs that can be force-moved upstream,
which would silently reintroduce the drift this change exists to eliminate.

## Getting the data

```bash
make fetch-onc-data
```

or directly:

```bash
uv run python scripts/fetch_onc_test_data.py
```

This writes `sample_labeled_pairs.jsonl`, `population_queries.jsonl`, and
`population_candidates.jsonl` into this directory. `tests/test_onc_regression.py` and
`tests/test_onc_population_regression.py` **skip** (not fail) with an actionable message if this
hasn't been run yet — see `tests/_onc_test_set.py`.

## Provenance

| File | Source |
|---|---|
| `sample_labeled_pairs.jsonl` | `cms-hte-patient-matching-test-set` @ `evaluation/cases/sample_labeled_pairs.jsonl` |
| `population_queries.jsonl` | `cms-hte-patient-matching-test-set` @ `evaluation/cases/population_queries.jsonl` |
| `population_candidates.jsonl` | `cms-hte-patient-matching-test-set` @ `evaluation/cases/population_candidates.jsonl` |

Fetched from `https://github.com/icanbwell/cms-hte-patient-matching-test-set`, tag `0.0.1`
(commit `c2454c54be9d18155996dcc10d4fa259800236e1`) — see `SOURCE_TAG`/`SOURCE_COMMIT` in
`scripts/fetch_onc_test_data.py` for the current pin, which is the authoritative version, not this
note (update this note if you bump the pin, but the script is what actually governs it).

Every record in these files ultimately traces back to the public **ONC 2017 Patient Matching
Algorithm Challenge dataset** (Office of the National Coordinator for Health IT — synthetic,
non-PHI), transformed by the sibling repo's own mutation/mining/construction code
(`mutations.py`, `hard_negatives.py`, `special_populations.py`, `normalization_edge_cases.py`,
`population_cases.py`). See that repo's `evaluation/cases/README.md` ("How this test data was
generated") for the full methodology, category definitions, and file format documentation — not
duplicated here to avoid a second copy of that explanation going stale.

## Bumping the pinned tag

When the sibling repo cuts a new tag this repo should track:

1. Update both `SOURCE_TAG` and `SOURCE_COMMIT` in `scripts/fetch_onc_test_data.py` — the tag for
   human-readable provenance, the commit SHA it resolves to for the actual fetch.
2. Run `make fetch-onc-data` and re-run both ONC tests locally.
3. Confirm the new data doesn't shift recall/precision/FPR/F1 past the checked-in thresholds
   (`RECALL_FLOOR`, `FPR_CEILING`, etc. in each test file) — if it does, that's either a real
   regression to investigate or a deliberate threshold update, not something to wave through.
4. Commit the pin bump as its own reviewable change, separate from any unrelated rule change.
