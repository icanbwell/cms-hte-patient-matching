# u-probability sanity-check tool

A standalone tool that downloads public US Census (and ACS) data and computes
empirical "u-probabilities" -- the probability that two randomly chosen,
distinct people agree on a given field (first name, last name, date of
birth, ZIP, city, state, street line) -- to sanity-check the hand-picked
conservative u-values used by a probabilistic patient-matching model.

This tool is **not part of** and does **not import from** the
`patient_matching` package elsewhere in this repository. It is a separate,
self-contained Python project that lives in this directory only. It does not
use any patient data -- only public Census/ACS aggregate data.

## Setup

Requires Python 3.12 (`python3.12`).

```bash
cd calculations
python3.12 -m venv .venv        # or: uv venv .venv --python 3.12
source .venv/bin/activate
pip install -r requirements.txt  # or: uv pip install -r requirements.txt
```

Optional credentials (put in a `calculations/.env` file, gitignored):

```
CENSUS_API_KEY=your_key_here   # avoids Census API rate limiting on ZCTA-level calls
HUD_TOKEN=your_token_here      # enables the optional HUD USPS ZIP crosswalk step
```

Get a free Census API key at https://api.census.gov/data/key_signup.html and
a free HUD USER API token at https://www.huduser.gov/hudapi/public/register.
Without `CENSUS_API_KEY`, the ~34k-row ZCTA-level ACS queries still work but
may be throttled. Without `HUD_TOKEN`, the HUD crosswalk step is skipped and
city u-probabilities are computed from Census places/CDPs only (this is
printed clearly at runtime, with instructions -- it does not fail silently).

## Running

```bash
python run_all.py                 # download + compute + write outputs, in one pass
python run_all.py --download-only # just download raw sources into data/raw/
python run_all.py --compute-only  # compute from whatever is already in data/raw/
```

Or via the `Makefile`:

```bash
make venv       # create .venv and install requirements.txt
make download   # downloads all raw sources into data/raw/ (idempotent)
make calculate  # computes u-probabilities from data/raw/, prints the headline
                # table to stdout, and (re)writes outputs/
make all        # download, then calculate
make test       # pytest tests/
```

Downloading is idempotent (re-running skips files that already exist).
`make calculate` / `--compute-only` never touches the network -- it only
reads whatever is already in `data/raw/`, so it's the fast path for
re-running the math after a `compute.py` change without re-downloading.
Either mode computes every u-probability and writes:

- `outputs/u_probabilities.csv`
- `outputs/u_probabilities.md` (same table + methods + caveats + sources)

The last-name and first-name fuzzy-match computations (edit-distance-1
matching over ~156k and ~54k Census names, respectively) are the slowest
step and are checkpointed to `data/processed/*_ball_mass.npy`; re-running
after an interruption reuses the checkpoint instead of recomputing.

Run the tests with:

```bash
pytest tests/
```

## What this computes

For each field, `u = Σ p_v^2` over the population frequency of each value.
Two versions are reported:

- `u_simple` = `Σ (n_v/N)^2` (plug-in estimator)
- `u_unbiased` = `Σ n_v(n_v-1) / (N(N-1))` (unbiased estimator for the
  probability two *distinct* people, sampled without replacement, share a
  value) -- this is the headline number.

Fields computed: last name (exact + fuzzy), first name (exact + fuzzy), year
of birth, full date of birth (derived), ZIP (via ZCTA proxy), state, city,
and street-line-given-ZIP / street-line-and-ZIP (a co-resident floor, not a
point estimate -- see `outputs/u_probabilities.md` for why).

See `outputs/u_probabilities.md` for the full results table, per-field
methodology notes, suppression/coverage caveats, and source URLs with
download dates. See `config.py` for exactly which URLs were resolved from
which Census landing pages and how. See
[`docs/PROCESS.md`](docs/PROCESS.md) for how this tool itself was built --
how the source URLs were resolved, the design decisions behind the fuzzy
name matching and checkpointing, and how to reproduce or extend it.

## Known limitations (see outputs/u_probabilities.md for detail)

- Census name files only list names occurring >=100 times; a coverage
  percentage and a conservative lower bound are reported alongside the
  headline renormalized-listed-names estimate.
- ZCTAs (used as a ZIP proxy) are not identical to USPS ZIP codes.
- Full-DOB assumes a uniform distribution of birthdates within a birth year.
- The street-line-and-ZIP calculation is an explicit floor: it captures only
  the "share a household" effect and ignores street-name collisions between
  unrelated households in the same ZIP, so real street-line agreement is
  higher than this estimate.
- All inputs are national population estimates, not any specific payer's or
  provider's member population.
