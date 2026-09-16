# How to test this engine against `cms-hte-patient-matching-test-set`

Runbook for validating `patient_matching`'s Table 2 matching engine against the ONC-derived data
produced by the sibling `cms-hte-patient-matching-test-set` repo. For *why* this is built the way
it is (fetch-on-demand decision, threshold rationale, per-category measured values), see
`docs/ONC_REGRESSION_TEST_DESIGN.md` — this doc only covers the *how*.

There are two ways to do this, depending on what you're trying to check:

| You want to... | Use |
|---|---|
| Run the standard regression gate (what CI runs on every PR) | **Fetched data** — `make fetch-onc-data`, no sibling checkout needed |
| Try out a change to the sibling repo's generation code, or test against a larger/regenerated sample before it's tagged | **Live sibling checkout** — `~/git/cms-hte-patient-matching-test-set` |

## 1. Running the standard regression suite (fetched data)

```bash
make fetch-onc-data
uv run pytest tests/test_onc_regression.py tests/test_onc_population_regression.py -v
```

`make fetch-onc-data` downloads three JSON Lines files from a pinned tag of the sibling repo
(`scripts/fetch_onc_test_data.py`'s `SOURCE_TAG`) into `tests/fixtures/onc/`. This is a separate,
explicit step, not a dependency of `make tests` — running `pytest`/`make tests` without it first
just skips the two ONC tests rather than fetching over the network on every invocation.

What runs, once the data is present:

- **`test_onc_regression.py`** (pairs tier) — every `(source, target, expected_match)` triple in
  `tests/fixtures/onc/sample_labeled_pairs.jsonl` through `NormalizationManager().normalize()` →
  `FieldExtractor().extract()` → `MatchingEngine.evaluate_pair()`. Asserts recall ≥ 0.95 and
  FPR ≤ 0.01. Precision is computed and printed in the failure summary but **not** asserted — this
  tier deliberately over-samples rare/high-risk categories, so precision has no real-world
  interpretation here (see `evaluation/cases/README.md` in the sibling repo, "Frequency and
  real-world representativeness").
- **`test_onc_population_regression.py`** (population tier) — same pipeline, but scored over
  `population_queries.jsonl` + `population_candidates.jsonl` (one query patient against a
  ~40-candidate pool). This tier *is* representative, so precision/recall/FPR/F1 are all asserted:
  precision ≥ 0.99, recall ≥ 0.95, FPR ≤ 0.001, F1 ≥ 0.97.

Both tests skip (not fail) with an actionable message pointing at `make fetch-onc-data` if the
files aren't present — the expected state before that command has been run, not an error path.

If a threshold trips, the assertion message includes the full tp/fp/tn/fn breakdown (and, for the
pairs tier, a per-`rationale`-category breakdown) — use that to tell a real regression from a
threshold that needs a deliberate, documented update.

## 2. Testing against a live sibling checkout

Use this when you're actively changing something in `cms-hte-patient-matching-test-set` (a new
mutation type, a fix to hard-negative mining, a larger sample) and want to see its effect on this
engine *before* it's tagged and this repo's pin is bumped to pick it up.

### 2a. Regenerate the sibling repo's data, then score against the regenerated files

```bash
cd ~/git/cms-hte-patient-matching-test-set
uv sync
PYTHONPATH=. uv run python evaluation/export_test_dataset.py
PYTHONPATH=. uv run python evaluation/export_population_dataset.py
```

This overwrites that repo's own `evaluation/cases/*.jsonl` in place. Score against them directly
from this repo (see 2b) rather than copying them into `tests/fixtures/onc/` — that directory is
gitignored and only meant to hold what `make fetch-onc-data` downloads from a real tagged release,
not untagged local output.

### 2b. Ad hoc: score this engine against the live checkout's files directly

```python
# run from this repo's root, e.g. `uv run python scratch_check.py`
import json
from pathlib import Path

from patient_matching.matching.field_extractor import FieldExtractor
from patient_matching.matching.matching_engine import MatchingEngine
from patient_matching.normalization.manager import NormalizationManager

from tests._null_backend import NullBackend

SIBLING_CASES = Path.home() / "git" / "cms-hte-patient-matching-test-set" / "evaluation" / "cases"

normalizer = NormalizationManager()
extractor = FieldExtractor()
engine = MatchingEngine(backend=NullBackend())

tp = fp = tn = fn = 0
with (SIBLING_CASES / "sample_labeled_pairs.jsonl").open() as f:
    for line in f:
        case = json.loads(line)
        source = extractor.extract(normalizer.normalize(case["source"]))
        target = extractor.extract(normalizer.normalize(case["target"]))
        predicted = engine.evaluate_pair(source, target)
        actual = case["expected_match"]
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1

recall = tp / (tp + fn) if (tp + fn) else float("nan")
fpr = fp / (fp + tn) if (fp + tn) else float("nan")
print(f"n={tp + fp + tn + fn} recall={recall:.4f} fpr={fpr:.4f}")
```

This mirrors `tests/test_onc_regression.py` exactly, just pointed at the sibling checkout's own
output directory instead of `tests/fixtures/onc/`. Adapt the same pattern for
`population_queries.jsonl`/`population_candidates.jsonl` following
`test_onc_population_regression.py`. See the sibling repo's `evaluation/cases/README.md` ("Option
A"/"Option B") for the scoring contract this follows.

If the result looks good and you want this repo to actually track it, tag the sibling repo commit,
then bump `SOURCE_TAG` in `scripts/fetch_onc_test_data.py` (see `tests/fixtures/onc/README.md`,
"Bumping the pinned tag") — don't copy the files in by hand.

### 2c. Statistical before/after comparison (`rule_eval.py`)

If you're comparing two versions of a rule (not just checking pass/fail against a floor), the
sibling repo ships a rule-agnostic Bayesian comparison harness independent of both tiers above:

```bash
cd ~/git/cms-hte-patient-matching-test-set
uv run jupyter notebook notebooks/rule_eval_demo.ipynb
```

It takes a labeled gold set and two sets of predictions and returns a SHIP / REJECT /
NEEDS-MORE-DATA verdict with a stratified split — see `evaluation/rule_eval.py`'s module docstring.
Not wired into this repo's test suite; run it manually from the sibling checkout.

## 3. Interpreting results

| Tier | File(s) | Trust | Don't trust |
|---|---|---|---|
| Pairs | `sample_labeled_pairs.jsonl` | recall, FPR | precision, FDR, F1, accuracy — should-match ratio is a generation artifact, not a real base rate |
| Population | `population_queries.jsonl` + `population_candidates.jsonl` | precision, recall, FPR, FDR, F1, accuracy | — (naturally representative) |

Break pairs-tier results out by `rationale` category (`case["rationale"].split("/")[0]`) rather
than reading one blended number — a regression concentrated in one category (e.g. `fuzzy_variant`)
can be invisible in an aggregate that's dominated by another (e.g. `normalization_edge_case`, 64%
of the file by construction).

## 4. Gotchas

- **The sibling repo does not normalize its data.** Field values carry whatever case/punctuation
  the underlying ONC CSVs used. Always run `NormalizationManager().normalize()` before
  `FieldExtractor().extract()` — comparing raw fields directly will look far worse than the engine
  actually performs.
- **`tests/fixtures/onc/*.jsonl` is gitignored and fetched, not committed.** Don't `git add` files
  you copy in there manually for a local experiment — regenerate via `make fetch-onc-data` (which
  overwrites them from the pinned tag) if you need to get back to the tracked state.
- **Regenerating a larger sample than the sibling repo's committed default (2,000 patients, one ONC
  shard) has crashed a cluster before** — read the sibling repo's `SYNTHETIC_DATA_SETUP.md`
  ("Memory & scale") before raising `SAMPLE_SIZE`/`POOL_SIZE` or loading more than one shard.
- **A raised exception during extraction/evaluation should fail the run, not be silently
  skipped and excluded from the metrics** — both fetched-data tests assert zero extraction errors
  for exactly this reason; follow the same pattern in any ad hoc script.
- **Literal twins are absent from every tier by design**, not a gap — CMS spec §IV.G already
  acknowledges this case can't be resolved through field matching alone.

## 5. Where to go for more detail

- `docs/ONC_REGRESSION_TEST_DESIGN.md` — why these tests fetch data the way they do, measured
  values, thresholds, and the `helix.personmatching` comparison.
- `tests/fixtures/onc/README.md` — provenance of the pinned tag and how to bump it.
- `scripts/fetch_onc_test_data.py` — the fetch script itself; `SOURCE_TAG` is the authoritative
  pin.
- `~/git/cms-hte-patient-matching-test-set`'s `evaluation/cases/README.md` — full generation
  methodology, file formats, and the Option A/B scoring contracts this doc's snippets follow.
- `~/git/cms-hte-patient-matching-test-set`'s `docs/METHODOLOGY.md` — current-state summary of what
  the generator covers and what's still missing (e.g. insurance-identifier pairs, twins).
