# Learnings

Concrete technical findings from running this code against real data or real environments —
read this before re-investigating something already solved here.

## FHIR fields: `dict.get(key, default)` is not enough

Real FHIR payloads (e.g. `bronze.fhir_lake.patient_4_0_0`) can have an optional field present
in the dict but explicitly `null`, not merely absent. `dict.get("suffix", [])` only substitutes
the default when the *key is missing* — a present-but-`null` value passes straight through as
`None`, which then crashes on `len()`/iteration/subscript downstream. ONC's synthetic test data
never exercises this shape, which is why it wasn't caught until a live run.

**Fix pattern:** `dict.get(key) or default`, not `dict.get(key, default)`, for any field that
gets iterated or subscripted afterward. Applied in `patient_matching/normalization/` and
`patient_matching/matching/field_extractor.py` — see git blame on those files for the exact
before/after. Regression tests for each shape live alongside the existing tests in those
modules (search for `null` in test names).

**Where this could still bite:** any *new* field extraction/normalization code that reads a
FHIR dict without going through the existing normalizer/extractor helpers.

## scourgify's failure modes are already handled

`usaddress-scourgify`'s `normalize_address_record` raises `UnParseableAddressError` on a street
line it can't decompose (e.g. `"Main St"` with no house number, or `"PO BOX"`). This is a
subclass of `AddressNormalizationError`, which `address_normalizer.py` already catches and
falls back to basic text normalization for. Verified directly against the installed library,
not just by reading its source — see `test_unparseable_street_line_falls_back_instead_of_raising`.

## Library compliance: `usaddress-scourgify` and its transitive deps

`usaddress-scourgify` (0.7.1), `usaddress` (0.5.16), and `probableparsing` (0.0.1) all resolve
from the organization's JFrog Artifactory PyPI virtual repository — confirmed both in
`uv.lock` and via a live `%pip install` in the prod Databricks workspace. No compliance gap;
`pyproject.toml`'s `usaddress-scourgify>=0.6.0` already resolves to an approved version through
the lockfile. (A local `.venv` may lag behind `uv.lock` — e.g. it had 0.6.0 installed instead of
the locked 0.7.1 — that's a stale local sync, not a registry/compliance issue; run `uv sync`.)
