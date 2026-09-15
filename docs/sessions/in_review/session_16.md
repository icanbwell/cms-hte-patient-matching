# Session 16 — CMS v3.4.0: renumber Category 1 to spec IDs, extend DOB fuzzy

**Status:** pending
**Thread:** Line B: CMS v3.4.0 migration
**Estimated size:** M — a wide-blast-radius rename (touches every file/test that cites a
Category 1 `rule_id`) plus one small, mechanical behavior extension (DOB fuzzy on 4 more
rules). No new architecture.

> Read `../conventions.md` first.

## Outcome purpose

This repo currently implements CMS Proposal v3.3.0 plus addenda v3.3.1/v3.3.3(partial)/
v3.3.4/v3.3.6(partial) — 30 Category 1 (flat) rules with the v3.2.2/v3.3-era numbering
(`01`-`12`, `17`-`33`, `36`, with gaps left by rules 13-16 moving to Category 2 in session 6)
plus 8 Category 2 (household+individual) rules already using their final v3.4.0 IDs
(`13,14,15,16,34,35,37,38` — confirmed unchanged in v3.4.0, no work needed there). v3.4.0
renumbers Category 1 into a clean, gapless `01`-`30` sequence (v3.4.0 §IV, Table 2) and
expands the `*` (±1-day) DOB-fuzzy marker from rule 28 (old numbering) to four more rules
(v3.4.0's new `01`, `02`, `03`, `10`). This session makes both changes. Imran decided
(2026-09-15): relabel `rule_id` to match the spec exactly, not maintain a separate internal-ID
mapping layer — compliance/audit optics take priority over avoiding the rename's blast radius.

## Upstream sessions (must be completed first)

Session 6 — this session renumbers/extends exactly the Category 1 rule set session 6 built;
without it there's nothing to renumber. Already `in_review/` with a merged commit
(`b7f44bc`) on `main`, so the hard-dependency code is present even though the doc itself
hasn't moved to `completed/` yet (see conventions.md step 3 — verify this before branching:
`git log --oneline -- patient_matching/matching/table2_rules.py` should show `b7f44bc`).

## Downstream sessions (unblocked by this one)

- Session 17 (relationship_linkage field + rules 39/40) — no hard code dependency on this
  session's rename (39/40 are new IDs, untouched by the Category 1 renumbering), but should
  branch *after* this session merges to avoid a rename/new-rule merge conflict on
  `table2_rules.py` (a hot file per conventions.md).
- Session 18 (audit §VII reconciliation) — the per-query audit record's `rule_id` field should
  report the post-rename spec ID; branching before this session merges would need the old IDs
  reworked a second time.
- Session 19 (§C.7 twin-handling verification) — independent of the rename; can run in either
  order relative to this session.

## Upstream data/system dependencies

CMS Proposal v3.4.0, Table 2 (Google Doc, file ID `1NytpfZ05aokS-gD7uDIQE7gEyms9zMgoiaIah_w4VTE`
— shared by Imran 2026-09-15; not yet added to `conventions.md`'s "Reference documents" list,
see Task 3 below). **Fetch it fresh at session-start** (via Google Drive access, same as this
session's own research) — this is a live, unfinalized draft (Document Control shows
`Comment Period Ends: [Date + 60 days]` and `Effective Date: [TBD after finalization]`
unfilled despite the "Final Consolidated Draft" label), consistent with why v3.3's live doc
was never committed either (see conventions.md's "Reference documents" section).

## Downstream data/system dependencies

None new.

## Scope

### In scope

**1. Renumber the 30 Category 1 `rule_id` values.** File:
`patient_matching/matching/table2_rules.py`. Old ID → new ID, field composition unchanged
except where noted:

| Old ID | New ID | Combination | Notes |
|---|---|---|---|
| 01 | 01 | First Name*+Last Name*+DOB+Street Line* | DOB becomes `*` — see Task 2 |
| 02 | 02 | First Name+Last Name*+DOB+Phone | DOB becomes `*` — see Task 2 |
| 03 | 03 | First Name*+Last Name*+DOB+Email | DOB becomes `*` — see Task 2 |
| 04 | 04 | First Name*+Last Name+DOB+SSN Last4 | unchanged |
| 05 | 05 | First Name+Last Name*+DOB+SSN Last4 | unchanged |
| 06 | 06 | First Name*+Last Name+DOB+ITIN Last4 | unchanged |
| 07 | 07 | First Name+Last Name*+DOB+ITIN Last4 | unchanged |
| 08 | 08 | First Name+DOB+MBI | unchanged |
| 09 | 09 | First Name+DOB+Legal ID | unchanged |
| 10 | 10 | Last Name*+DOB+Legal ID | DOB becomes `*` — see Task 2 |
| 11 | 11 | First Name+DOB+Phone | unchanged |
| 12 | 12 | First Name+DOB+Email | unchanged |
| 17 | 13 | First Name+Phone+SSN Last4 | id only |
| 18 | 14 | First Name+Phone+ITIN Last4 | id only |
| 19 | 15 | First Name+Email+SSN Last4 | id only |
| 20 | 16 | First Name+Email+ITIN Last4 | id only |
| 21 | 17 | Phone+MBI | id only |
| 22 | 18 | Phone+Legal ID (namespace) | id only |
| 23 | 19 | Email+MBI | id only |
| 24 | 20 | Email+Legal ID (namespace) | id only |
| 25 | 21 | Legal ID+MBI | id only |
| 26 | 22 | Namespace-bound unique identifiers | id only |
| 27 | 23 | First Name+DOB+Member ID (payer ns) | id only |
| 28 | 24 | Last Name*+DOB*+Member ID (payer ns) | id only — already has DOB* |
| 29 | 25 | Phone+Member ID (payer ns) | id only |
| 30 | 26 | Email+Member ID (payer ns) | id only |
| 31 | 27 | First Name*+Last Name+DOB+Subscriber ID | id only |
| 32 | 28 | First Name+Last Name*+DOB+Subscriber ID | id only |
| 33 | 29 | First Name*+Last Name*+Phone+ZIP | id only |
| 36 | 30 | Last Name*+DOB+Phone | id only |

This mapping was cross-checked field-by-field against v3.4.0's clean Table 2 (all 30 rows),
not inferred from ID position alone — re-verify against the live doc at session-start per the
dependency note above, since it's still a live draft.

**Correction, found during execution, not anticipated when this doc was first drafted:**
v3.4.0's Category 1 table reassigns bare `13`-`16` to brand-new flat content (First
Name+Phone/Email+SSN/ITIN Last4 — what this repo had as old rules `17`-`20`). Checking
v3.4.0's actual Category 2 material (SS C.2-C.5) directly: it never assigns those 8 rules a
live ID of their own — it only describes them as Household-row + Individual-row pairings.
"Rules 13, 14, 15, 16, 34, 35, 37, and 38" appears exactly once, in SS C.8's prose, as a
backward-reference to the legacy v3.3.1 addendum numbering `household_rules.py` was
originally built against — not a v3.4.0 ID assignment. Left as-is, this collides with
Category 1's new `13`-`16` in any audit record keyed on bare `rule_id` (the SS VII "Table 2
combination evaluated" field can't tell the two apart). Imran decided (2026-09-15): prefix
Category 2's `rule_id` values with `C2-` (`C2-13`, `C2-14`, `C2-15`, `C2-16`, `C2-34`,
`C2-35`, `C2-37`, `C2-38`) — preserves the historically-meaningful numbers while making the
collision structurally impossible. **This session now includes updating
`household_rules.py` and its tests, not skipping them as originally scoped.**

**2. Extend DOB `*` (±1-day fuzzy) to (new-numbering) rules 01, 02, 03, 10.** File:
`patient_matching/matching/table2_rules.py`. Change each rule's `DOB` `RuleField` from
`_rf(DOB)` to `_rf(DOB, _F)`. `MatchingEngine` already dispatches DOB fields generically by
field name, not by rule ID (`matching_engine.py`'s `_evaluate_rule`, `if rf.name == DOB: ...
dob_fuzzy_match`, added in session 6) — no engine change needed for the dispatch itself.
Per session 6's established finding (`collision.FIELD_U_PROBS` has no DOB-fuzzy variant), DOB
going fuzzy-eligible does not by itself change any rule's computed `p_collision_fuzzy` — the
fuzzy figure still comes entirely from whichever *other* field in the combination already has
a fuzzy variant (First Name and/or Last Name). Target figures to verify against (v3.4.0 Table
2, computed via `p_collision()`, not hardcoded):

| New ID | p(exact) | p(fuzzy) |
|---|---|---|
| 01 | 3e-13 | 9e-13 |
| 02 | 1e-14 | 2e-14 |
| 03 | 1e-14 | 3e-14 |
| 10 | 5e-13 | 1e-12 |

### Out of scope

- Everything in session 17 (relationship_linkage field, rules 39/40), session 18 (audit §VII),
  and session 19 (§C.7/§C.9) — separately scoped sessions, see "Downstream sessions" above.
- Adding the v3.4.0 doc to `conventions.md`'s "Reference documents" list as a committed file —
  it's a live unfinalized draft, same policy as v3.3 (see "Upstream data/system dependencies"
  above); only the *link* gets recorded, handled as part of this session's Task 3, not a
  separate concern.
- Any change to `evaluation/`'s ONC baseline comparison — the statistical rigor gate's Tier 1
  report (session 3, `completed/`) already exists and this session is a rename plus a
  no-numeric-effect field-eligibility change on 3 already-passing rules, not new matching
  behavior in the sense the gate is designed to catch (see Validation below for why a fresh
  Tier 1 run isn't required here, matching session 6's own precedent).

## Tasks

1. **Renumber Category 1 `rule_id` values** in `table2_rules.py`'s `APPROVED_RULES` tuple per
   the mapping table above. Field compositions, `max_fuzzy_fields`, and `p_collision_*` calls
   are otherwise unchanged except for Task 2's four rules.

1a. **Prefix Category 2 `rule_id` values with `C2-`** in `household_rules.py`'s
   `CATEGORY_2_RULES` tuple (`13`→`C2-13`, `14`→`C2-14`, `15`→`C2-15`, `16`→`C2-16`,
   `34`→`C2-34`, `35`→`C2-35`, `37`→`C2-37`, `38`→`C2-38`) — see the correction note above for
   why. Update `test_household_rules.py` and every `test_matching_engine.py` case that
   references a Category 2 rule by its bare old ID (`_category2_rule_by_id(...)`,
   `result.matched_rule_id == ...`) to match.

2. **Mark DOB fuzzy-eligible on new-numbering rules 01, 02, 03, 10** (`_rf(DOB, _F)`), and
   confirm each rule's computed `p_collision_exact`/`_fuzzy` still matches the target figures
   above (it should, unchanged, per the no-numeric-effect note — write the assertion, don't
   assume).

3. **Record the v3.4.0 doc link** in `conventions.md`'s "Reference documents" section, following
   the exact pattern already used for the v3.3 entry (live Google Doc, file ID, "fetch fresh"
   caveat, not committed to the repo) — supersede or annotate the existing v3.3 entry rather
   than deleting it (v3.3's addenda text files remain useful history).

4. **Update every reference to a renumbered `rule_id`** outside `table2_rules.py` itself:
   grep for the old ID strings (`"17"`, `"18"`, `"19"`, `"20"`, `"21"`, `"22"`, `"23"`, `"24"`,
   `"25"`, `"26"`, `"27"`, `"28"`, `"29"`, `"30"`, `"31"`, `"32"`, `"33"`, `"36"`) across
   `patient_matching/api/service.py`, `patient_matching/matching/matching_engine.py`, and every
   test file the grep in Execution notes' pre-flight check turns up (known from this session's
   own scoping: `test_table2_rules.py`, `test_matching_engine.py`, `test_in_memory_backend.py`,
   `test_service.py`) — a bare numeric-string grep will over-match (e.g. `"28"` could appear in
   an unrelated line count), so review each hit rather than a blind find/replace.

## Unit tests required

File: `patient_matching/matching/tests/test_table2_rules.py` (existing) — update
`test_ids_are_the_expected_v33_category1_set` (rename to reflect v3.4.0, e.g.
`test_ids_are_the_expected_v340_category1_set`) to assert the new gapless
`{f"{i:02d}" for i in range(1, 31)}` set. Update `test_rule_01_has_4_fields_2_fuzzy` (still ID
`01`, but the fuzzy-count assertion changes once DOB joins the fuzzy set — decide whether the
test should assert 3 or 4 fuzzy-eligible fields once DOB is included, per Task 2's actual field
list). Update `test_rule_26_namespace_id_only` to `test_rule_22_namespace_id_only` (new ID).

New/extended tests:
- One test per renumbered rule confirming its `rule_id` matches the new mapping table (can be a
  single parametrized test over the full old→new table rather than 18 separate tests, per
  conventions.md's "parameterization over duplication").
- Extend `test_field_comparator.py` (or wherever DOB fuzzy boundary tests from session 6 live)
  with a case per newly-affected rule (01/02/03/10) confirming DOB ±1 day now participates in
  that rule's match without changing its `p_collision_fuzzy`.
- A regression test confirming `household_rules.CATEGORY_2_RULES`' rule IDs (`13,14,15,16,34,
  35,37,38`) are untouched by this session (guards against an accidental double-rename if a
  future session or a careless find/replace touches that file).

## Validation (definition of "resolved")

- [x] `APPROVED_RULES` has exactly 30 entries with `rule_id` values `01`-`30`, no gaps, no
      duplicates.
- [x] Rules 01, 02, 03, 10 have DOB marked `FUZZY_ELIGIBLE`, dispatch through
      `dob_fuzzy_match` (verified by test, not just field-role inspection), and their
      `p_collision_exact`/`_fuzzy` match the target table above.
- [x] Every non-`table2_rules.py` reference to an old Category 1 ID has been updated to the new
      ID (verified by re-running the Task 4 grep and confirming zero remaining old-ID hits that
      refer to a Category 1 rule).
- [x] `household_rules.py`'s Category 2 rule IDs carry the `C2-` prefix
      (`C2-13`,`C2-14`,`C2-15`,`C2-16`,`C2-34`,`C2-35`,`C2-37`,`C2-38`) and are disjoint from
      `APPROVED_RULES`'s ID set (verified by test, not just inspection).
- [x] `uv run pytest .` is green, full suite, no regressions (470 passed; 21 deselected —
      pre-existing Docker-dependent MongoDB Atlas testcontainer tests, unrelated to this
      session, error without a local Docker daemon per conventions.md's documented exception).
- [x] `uv run pre-commit run` on all touched files is clean.
- [x] Per conventions.md's statistical rigor gate: session 3's Tier-1 report already exists on
      `main` and this session's field-composition changes don't alter any rule's computed
      collision probability (see "Out of scope") — merge gate satisfied without a fresh run,
      same precedent as session 6.

## Open questions

The two decisions this session originally depended on (relabel vs. map, and whether to
proceed) were made by Imran before execution started (2026-09-15, this doc's Outcome purpose).
One more surfaced mid-execution, not anticipated when this doc was first drafted — see
Execution notes: whether Category 2's legacy `13-16/34/35/37/38` labels should be relabeled
once Category 1's renumbering claimed those same bare IDs. Resolved by Imran (2026-09-15):
`C2-` prefix. No open items remain.

## Execution notes

Executed 2026-09-15 on branch `claude/session-16-v340-renumber-dob-fuzzy`, cut from `main`.

**Real finding, not anticipated when this doc was first drafted:** Category 1's clean v3.4.0
renumbering claims bare `13`-`16` for brand-new flat rules (First Name+Phone/Email+SSN/ITIN
Last4 — old rules `17`-`20`). This doc originally assumed Category 2's existing
`13,14,15,16,34,35,37,38` labels needed no change, reasoning from §C.8's prose ("Rules 13, 14,
15, 16, 34, 35, 37, and 38"). Checked the actual §C.2-C.5 tables directly before writing code
(not just the prose) and found they carry **no ID column of their own** — §C.8's numbers are a
backward-reference to the legacy v3.3.1 addendum numbering, not a v3.4.0 assignment. Also found
a second, independent confirmation the doc's cross-references are stale: §C.7's persistent-ID
anchoring text cites "Rule 26, ≈0 collision" for the namespace-ID rule, but v3.4.0's own master
Table 2 assigns that rule ID `22` — i.e., prose sections weren't updated after Table 2's
renumbering pass, a second instance of the same class of drafting gap. Flagged to Imran
mid-session rather than guessing; decided: `C2-` prefix (`C2-13` etc.) on Category 2's
`rule_id` values. Updated `household_rules.py`, `test_household_rules.py`, and every
`test_matching_engine.py` case referencing a Category 2 rule by its bare old ID.

**Task 4 pre-flight grep results:** no old-ID references found in `patient_matching/api/
service.py`, its test, `matching_engine.py` itself, or `test_in_memory_backend.py` (confirming
`MatchingEngine` dispatches DOB/rules generically, not by hardcoded ID). Real hits: `test_
table2_rules.py` (`rule_26_namespace_id_only` → renamed `rule_22_...`), `test_matching_engine.py`
(rule `"26"`→`"22"` in `TestMatchingEngineRuleSubset`/`TestMatchingEngineRuleEvaluations`; rule
`"28"`→`"24"` in `TestDobFuzzyDispatch`, including the local variable name `rule_28`→`rule_24`
for clarity), `test_collision.py` (`"26"`→`"22"` in the namespace-ID carve-out, plus renamed
`test_existing_26_rules_reproduce_published_values` →
`test_existing_category1_rules_reproduce_published_values` since "26" no longer means anything
after the renumbering). Also updated `collision.py`'s module docstring (stale v3.3.0 doc-ID
reference and its own cross-reference to the just-renamed test) and its own test-name
cross-reference, plus `table2_rules.py`'s module docstring (was still v3.2.2 even before this
session).

**Fixed `test_13_through_16_are_not_in_the_flat_rule_set`**, whose original assertion
(`APPROVED_RULES` must never contain `13`-`16`) is now backwards — Category 1 legitimately
owns bare `13`-`16` post-renumbering. Replaced with
`test_rule_ids_disjoint_from_category_2`, asserting `APPROVED_RULES`' and
`CATEGORY_2_RULES`' ID sets don't intersect — a more direct guard against exactly the collision
this session found, and one that will trip immediately if a future session ever drops the
`C2-` prefix.

Validation:
- `uv run pytest .`: 470 passed, 0 regressions (21 pre-existing Docker-dependent tests
  deselected, unrelated to this session).
- Direct numeric check (not just test-pass): rules 01/02/03/10's computed
  `p_collision_exact`/`_fuzzy` reproduce v3.4.0's stated figures exactly (3e-13/9e-13,
  1e-14/2e-14, 1e-14/3e-14, 5e-13/1e-12).
- `uv run pre-commit run` on all touched files: clean (ruff, ruff-format, mypy, bandit,
  detect-secrets, standard hooks) — one file was auto-reformatted by ruff-format
  (`table2_rules.py`, line-wrapping a multi-line tuple call), not a content change.

Decision: PR opened from `claude/session-16-v340-renumber-dob-fuzzy` into `main`, left
**open** rather than merged — per conventions.md's Definition of Done, merging is the project
lead's (Imran's) call. Doc moved to `in_review/` and `index.md` updated accordingly, in the
same PR.
