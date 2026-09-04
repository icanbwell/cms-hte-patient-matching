# Vendored NPPES practitioner data

A **copy**, not a live dependency — vendored here so `tests/test_nppes_no_cross_provider_match.py`
runs standalone. See that test's module docstring for what it actually checks and why (short
version: **not** a Table 2 compliance test — this repo's Table 2 rules and Table 3 collision
probabilities are patient-specific and don't transfer to practitioner data; see
`docs/ONC_REGRESSION_TEST_DESIGN.md`'s "Alternatives Considered" for the full reasoning. This is a
narrower, still-valid safety check: does the one Table 2 rule that *can* evaluate against
NPPES-shaped data - rule 33, `First Name* + Last Name* + Phone Number + ZIP Code`, the only
approved rule requiring none of DOB/SSN/MBI/email - ever produce a false match between two
genuinely distinct real providers?).

## Provenance

Copied from `helix.personmatching`'s `tests/nppes_dataset/files/nppes/*.csv`
(`https://github.com/icanbwell/helix.personmatching`, repo commit
`400e0d9c733775babbc2cdd115aa5c75797d3bab`, files themselves last changed at commit
`6f402c322c52d10ca625a2e79097b96f178a1457`, 2026-09-03), on 2026-09-04.

That repo's own `tests/nppes_dataset/README.md` documents the ultimate source and generation
method - not duplicated in full here to avoid a second copy going stale, but in short: a sample
pulled live from the public **NPPES NPI Registry API** (`https://npiregistry.cms.hhs.gov/api/`),
not the full multi-GB monthly bulk file, via that repo's `tests/nppes_dataset/scripts/fetch_nppes_sample.py`.
Real (not synthetic) data, but not PHI - providers are legally required to have this data public
(45 CFR §162). Stratified across 5 states (`NC`, `CA`, `TX`, `NY`, `IL`) × 5 last-name prefixes,
individual providers only (Entity Type 1), excluding deactivated NPIs: **4,943 unique providers**.
Columns: `NPI`, `Last Name`, `First Name`, `Middle Name`, `Suffix`, `Gender`, `Practice Address
Line 1/City/State/Postal Code`, `Practice Address Phone`. **No DOB, no SSN, no email** - NPPES
never collects them, which is exactly the demographic gap this test's rationale depends on.

## Refreshing this copy

Not expected to change often - this is a fixed sample, not a live query. If `helix.personmatching`
regenerates its sample (grows it, adds states, refreshes against current NPPES data), re-copy
deliberately:

```bash
cp ../helix.personmatching/tests/nppes_dataset/files/nppes/*.csv tests/fixtures/nppes/
```

Update the commit hashes and date above when you do, and re-run
`tests/test_nppes_no_cross_provider_match.py` to confirm the refreshed sample doesn't surface a
new cross-provider false positive.
