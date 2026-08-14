# Synthetic CMS test-dataset generation: setup & execution

Walkthrough for running `evaluation/mutations.py`, `evaluation/hard_negatives.py`, and
`evaluation/labeled_pairs.py` (session 9) — the fuzzy-mutation and hard-negative-mining code
this repo uses to build a labeled CMS test dataset. See `SYNTHETIC_DATA_COMPARISON.md` for what
this code does and doesn't cover; this file is just how to run it.

## Setup

1. Standard repo setup first, if you haven't already: `uv sync` from the repo root.
2. `evaluation/` deliberately keeps `numpy`/`pandas`/`scipy`/`matplotlib` out of the shippable
   `patient_matching` package (see `evaluation/DESIGN.md`) — install them into the same venv to
   run anything under `evaluation/`, including this session's code (it imports `rule_eval`,
   which needs `numpy`):
   ```
   uv pip install numpy pandas scipy matplotlib
   ```
   Without this, `evaluation/test_labeled_pairs.py` (and `test_rule_eval.py`,
   `test_onc_baseline.py`) skip themselves cleanly via `pytest.importorskip("numpy")` rather than
   failing — `evaluation/test_mutations.py` and `evaluation/test_hard_negatives.py` have no such
   dependency and always run.
3. No other new dependency is required — `nicknames` and `rapidfuzz` (used by
   `mutations.py`) are already core `patient_matching` dependencies (see `pyproject.toml`).

## Running the tests

```
uv run pytest evaluation/test_mutations.py evaluation/test_hard_negatives.py evaluation/test_labeled_pairs.py -v
```

Or the full suite: `uv run pytest .` (`make tests` only collects the root `tests/` directory,
not `evaluation/` — CI's actual gate, `.github/workflows/build_and_test.yml`, runs
`uv run pytest .` from the repo root, which does collect it).

`evaluation/` and `notebooks/` are excluded from the pre-commit hook (see
`.pre-commit-config.yaml`'s `exclude:` line) — run lint/type checks on new files here manually:

```
uv run ruff check evaluation/mutations.py evaluation/hard_negatives.py evaluation/labeled_pairs.py
uv run mypy evaluation/mutations.py evaluation/hard_negatives.py evaluation/labeled_pairs.py
```

## Running the demo script

```
PYTHONPATH=. uv run python evaluation/labeled_pairs.py
```

This loads **one** ONC shard (not all 9), samples it down to `SAMPLE_SIZE` (2000 by default —
see "Memory & scale" below), builds labeled pairs, and prints counts per pair type/mutation.
Override the sample size deliberately: `SAMPLE_SIZE=20000 PYTHONPATH=. uv run python evaluation/labeled_pairs.py`.

To use the pieces individually (e.g. from a notebook or another script):

```python
from mutations import generate_fuzzy_variant
from hard_negatives import mine_shared_address_hard_negatives
from labeled_pairs import build_labeled_pairs

variant, mutation_type = generate_fuzzy_variant(patient)          # one mutated copy
candidates = mine_shared_address_hard_negatives(patients)          # List[HardNegativeCandidate]
pairs = build_labeled_pairs(patients, n_fuzzy_variants_per_patient=1, seed=0)  # List[LabeledPair]
```

## Memory & scale — read before running this against the full ONC dataset

This is a real, previously-encountered failure mode, not a hypothetical one: loading the full
ONC dataset and running large transformations against it has crashed a Databricks cluster before
(per Sean, 2026-08-14 design discussion). Three things compound this specifically for this
code path:

1. **`onc_loader.load_onc_patients()` has no streaming.** It reads whichever CSV paths you pass
   it entirely into one Python list of nested dicts. Passing it `sorted(onc_dir.glob("*.csv"))`
   (all 9 shards) materializes all ~1,000,000 records in memory at once — there is no
   chunked/lazy mode.
2. **`NormalizationManager.normalize_batch()` (or a per-record loop calling `.normalize()`)
   produces a second full copy** of whatever list you feed it — normalization is explicitly
   documented as non-mutating (`manager.py`: "The original dict is not mutated"). Running this
   over the full dataset means holding two ~1,000,000-record lists in memory simultaneously,
   not one.
3. **`build_labeled_pairs()` and `mine_shared_address_hard_negatives()` both assume their input
   is already a fully-materialized, in-memory list** — they don't take a file path or a
   generator. Whatever memory pressure steps 1-2 already created is the baseline they add their
   own (smaller, per-record-transient) overhead on top of.

None of this is new to this session's code specifically — `evaluation/onc_baseline.py`'s own
`__main__` (session 3) already loads all 9 shards unconditionally and runs the same
normalize-then-transform pattern. This session's code doesn't fix that; it just doesn't make it
worse by default, since `labeled_pairs.py`'s `__main__` loads one shard and samples it down
rather than following `onc_baseline.py`'s all-shards pattern.

**Practical guidance if you need to scale this up:**

- **Prefer one shard at a time, not all 9 concatenated.** Each shard is ~110K rows (~1/9th of
  the full dataset) — a meaningfully smaller working set than the full ~1,000,000.
- **Sample before transforming, not after.** Slice the patient list down (`patients[:N]`)
  *before* calling `NormalizationManager`/`build_labeled_pairs`, not after loading and
  normalizing everything and then discarding most of it — the peak memory is what matters, not
  the final output size.
- **If you genuinely need full-dataset scale (e.g. the Doc's §4 ≥1,000,000-record collision
  validation, which this session's code does not attempt), do it as a distributed job, not a
  single-process Python list.** On Databricks specifically: express the load/normalize/transform
  as Spark operations (`spark.read.csv(...)`, `.rdd.map(...)`, or a pandas-UDF applied per
  partition) so the work is distributed across executors rather than collected onto the driver
  as one Python list — the same shape session 4's `notebooks/fhir_match_data_source.py` already
  uses for its own real-data query (`spark.sql(...)`, never a driver-side full materialization).
  Do not `collect()` the full dataset onto the driver and then call this session's
  Python-list-based functions on it directly.
- **When in doubt, measure before you scale.** Time and profile memory on one shard, sampled
  down, before running anything against the full dataset — this is exactly the step that was
  skipped the time this crashed a cluster previously.
