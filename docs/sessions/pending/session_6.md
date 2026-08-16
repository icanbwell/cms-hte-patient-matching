# Session 6 — Expand Table 2 to CMS v3.3 (base spec + addenda v3.3.1/v3.3.3/v3.3.4/v3.3.6)

**Status:** pending
**Thread:** Line B: CMS v3.3 migration
**Estimated size:** L — larger than originally scoped. Three new canonical fields, a new DOB
fuzzy mode, a new two-tier Household/Individual evaluation architecture, 8 rules reclassified
into that architecture (4 of which are *already merged* into `main` and need amending, not just
adding), 1 recovered rule (38), and 2 rules explicitly deferred as not-ready. See "Re-scope
note" below.

> Read `../conventions.md` first.

**On hold (Imran, 2026-08-16):** do not start this session yet, even once the live-spec-fetch
blocker (below) clears — separate from that blocker, Imran asked to hold off adding the v3.3
37-rule expansion for now. Confirm with him before beginning. Session 11
(`docs/sessions/pending/session_11.md`) has a hard dependency on this session and is therefore
on hold too.

## Re-scope note (2026-08-12)

This doc was originally authored 2026-07-28 against CMS Proposal **v3.3.0 alone** — the
"37 rules" framing that used to open this section. Per the 2026-08-12 Sean/Zack sync and a
read of all six v3.3.x addenda now in `docs/`, that scope was incomplete: **v3.3.1, v3.3.3,
v3.3.4, and v3.3.6 all materially change Table 2's structure**, not just its rule count.
**v3.3.2 and v3.3.5 do not** — they're compliance/audit/testing-methodology changes (§VI/§VII)
with zero Table 2 rule content; confirmed out of scope for this session, see "Out of scope."

The rest of this document has been rewritten to incorporate v3.3.1/v3.3.3/v3.3.4/v3.3.6.
Original v3.3.0-only content that no addendum touches (the 3 new fields and DOB-fuzzy work for
rules 27-33) is preserved essentially as originally authored.

## Outcome purpose

This repo currently implements CMS Proposal **v3.2.2** (26 rules, no ZIP or insurance-ID based
combinations, no DOB tolerance, no household/individual distinction). The actual mid-August
target is the full **v3.3 rule set**: v3.3.0's base 37-rule table, restructured by v3.3.1 into
30 single-step "Category 1" rules plus 8 two-step "Category 2" (Household-then-Individual)
rules — 38 total — with v3.3.4's expanded placeholder-exclusion requirement applying across
all of them, and v3.3.6 defining (but this session not yet implementing) how "institutional
address" gets determined for the Household-tier fields that need it. v3.3.3's two new rules
(39, 40) are analyzed but explicitly **not** built in this session — see "Out of scope."

## Upstream sessions (must be completed first)

Session 5 — every new/reclassified rule's `p_collision_exact`/`_fuzzy` is computed via session
5's evaluator; this session cannot correctly score any new combination without it.

## Downstream sessions (unblocked by this one)

None currently authored. Two explicit candidates fall out of this session's analysis (not
authored yet, both need a human decision first — see "Out of scope"):
- Rules 39/40 (guardian-verified minor / newborn-via-maternal-linkage), once Imran resolves
  Rule 39's flagged math problem and someone confirms whether a per-encounter birth identifier
  is available.
- Institutional-address registry/postal-validation integration (v3.3.6), once Sean/Imran weigh
  the cost/privacy tradeoff v3.3.4's own footnote raises about calling an address-verification
  service on every patient address.

The (not-yet-authored) per-value P(collision) refinement, if Imran signs off on it, would apply
to this session's full rule set once it exists.

## Upstream data/system dependencies

The CMS v3.3 spec's Table 2 (Google Doc, file ID `1ABHR6e4N-K9lEj1vc7DuzoAy8CuaAqwqAZSpJH9T4Yg`
— see `conventions.md`). **Fetch it fresh at session-start.** The rule tables below transcribe
v3.3.0 (as read 2026-07-28) plus the four addenda text files committed at `docs/Proposal
v3.3.{1,3,4,6}_*.txt` (as read 2026-08-12) — re-verify rule numbering, field combinations, and
collision-probability figures against the live docs before implementing, since all of these
are drafts under active public comment and adversarial review has already revised several
figures mid-draft (see v3.3.1 §4.5's callout on rules 13-16/37, and v3.3.3's Rule 39 caveat).

**New dependency this session did not have before:** v3.3.6's institutional-address
methodology requires external registry data (CMS Provider of Services/Care Compare, Federal
BOP + state DOC facility lists, NCES IPEDS, HIFLD GIS layers) and/or a CASS-certified postal
validation vendor. Neither is wired into this repo today, and `FieldExtractor` only ever sees
a FHIR `Patient` dict with no network/external-service call in its current design. This
session does **not** resolve that dependency — see "Out of scope."

## Downstream data/system dependencies

None new, beyond the institutional-address gap noted above (tracked as a deferred item, not a
downstream dependency of this session's own deliverable).

## Scope

### In scope

**1. Three new canonical fields, end-to-end** (needed by rules 27-32 below — unaffected by any
   addendum, carried over unchanged from the original v3.3.0-only plan):
   - `zip_code` (rules 33, 34, 35) — 5-digit ZIP, exact only.
   - `insurance_member_id` (rules 27-30) — individual-level, payer-namespace-scoped, exact
     only. Per the spec: "the bare subscriber base value without dependent suffix SHALL NOT
     be treated as a Member ID."
   - `insurance_subscriber_id` (rules 31, 32, 38) — policyholder-level, payer-namespace-scoped,
     exact only. (Also needed by new Rule 38 below — same field, no new work.)

**2. A new DOB comparison mode**: several v3.3 rules mark DOB as fuzzy-eligible (shown with
   `*` in the spec), but v3.3's DOB tolerance is **+/-1 day**, not Damerau-Levenshtein edit
   distance (DOB is a date, not a name/street string) — this needs new comparator logic, not
   reuse of the existing string-fuzzy path. Unaffected by any addendum.

**3. Rules 27-33, per the v3.3.0 base spec** (unaffected by v3.3.1 — confirmed by that
   proposal's own §4.2/§3.6 disposition table, which lists 27-33 as "Unaffected"/"No change"):

   | # | Combination | p(exact) | p(fuzzy) | Notes |
   |---|---|---|---|---|
   | 27 | First Name + DOB + Member ID (payer namespace) | 2e-12 | — | |
   | 28 | Last Name* + DOB* + Member ID (payer namespace) | 5e-13 | 1e-12 | DOB* = +/-1 day |
   | 29 | Phone Number + Member ID (payer namespace) | 1e-12 | — | |
   | 30 | Email Address + Member ID (payer namespace) | 1e-12 | — | |
   | 31 | First Name* + Last Name + DOB + Subscriber ID (payer namespace) | 1e-12 | 1.5e-12 | |
   | 32 | First Name + Last Name* + DOB + Subscriber ID (payer namespace) | 1e-12 | 2e-12 | |
   | 33 | First Name* + Last Name* + Phone Number + ZIP | 3e-14 | 9e-14 | Category 1 — confirmed unaffected by v3.3.1 |

   For each rule, the `p_collision_exact`/`_fuzzy` column values above are what session 5's
   `evaluate_combination()` should reproduce once the rule's `fields` tuple is correctly
   built — don't hardcode the spec's numbers as literals (same principle as session 5's
   Task 3); use them here only to verify the computed value against the spec's own stated
   figure as a sanity check while authoring the rule.

   **Note:** row 31's p(fuzzy) is 1.5e-12, not a 2e-12 figure that would assume a 2x first_name
   fuzzy multiplier — consistent with session 5's Table 3 (first_name fuzzy u=0.03, a 1.5x
   multiplier), and with the same correction already applied to session 5's rules 04/06. Row
   32 is unaffected (its fuzzy field is last_name, whose 2x multiplier is correct as stated).

   **Rule 36** (`Last Name* + DOB + Phone Number`, already in `_V322_RULES`) is also confirmed
   Category 1 by v3.3.1 §3.6 — retained as a "legacy exception" with a multiple-birth caveat
   (§4.7: it has no First Name field and cannot disambiguate twins sharing a household/DOB;
   treat a same-DOB multi-candidate case as unresolved, don't guess). No code change to Rule
   36 itself; the caveat is a runtime/twin-handling concern, not a field-list concern — twin
   handling itself is not in this session's scope (v3.3.1 §3.7/§4.7 is a candidate future
   session; flag but do not build it here).

**4. NEW — the Household-tier / Individual-tier two-step architecture (v3.3.1 §3-4).**
   Supersedes the original plan's `enable_household_risk_rules` flag idea entirely — see the
   callout after Task 4 below for why.

   Field classification (v3.3.1 Tables A/B — u-values are the standard record-linkage
   probability-of-chance-agreement figures, same style as this repo's existing
   `collision.FIELD_U_PROBS`):

   | Field | Tier | Conservative u | Notes |
   |---|---|---|---|
   | SSN Last 4 | Household | 0.0001 | Reclassified — frequently the head-of-household's number on dependent records. |
   | ITIN Last 4 | Household | 0.0001 | Same handling as SSN Last 4. |
   | Insurance Subscriber ID | Household | 0.0001 | ~40% of commercially insured people share a base subscriber ID with a household member (base doc §IV.H). |
   | Verified Phone Number | Household | 0.000001 | Frequently a shared household/family-plan line. |
   | Verified Email Address | Household | 0.000001 | Frequently shared by spouses/guardians. |
   | Verified Street Line (non-institutional) | Household | 0.00003 | **Gated on v3.3.6's institutional-address exclusion — not yet implemented, see "Out of scope."** |
   | ZIP Code (5-digit) | Household | 0.0003 | Too weak alone; must pair with another Table-A field. |
   | Last Name | Household (corroboration only) | 0.005 | Advisory only — SHALL NOT withhold a match because Last Name differs; SHALL NOT count as an individual-tier field. |
   | First Name (exact) | Individual | 0.02 | Required (not fuzzy) whenever DOB is shared by >1 candidate in the resolved household (twins). |
   | First Name (fuzzy, 1 edit, ≥5 chars) | Individual | 0.03 | Only permitted when DOB is *not* shared by another household candidate. |
   | Date of Birth (exact) | Individual | 0.0001 | No individuating value between twins/multiples sharing a birth date. |
   | Middle Name | Individual (last-resort only) | 0.01 | Not a standing field — twin-tiebreaker inside the existing two-candidate escalation path only. Not built this session (twin handling is out of scope, see Rule 36 note above). |

   Household Match rows (Table 2-H — pairs of Table-A fields, each independently ≥1e-8, well
   under the 1e-7 structural floor):

   | ID | Combination | P(household collision) |
   |---|---|---|
   | H-01 | SSN Last 4 + Phone | 1.0e-10 |
   | H-02 | SSN Last 4 + Email | 1.0e-10 |
   | H-03 | SSN Last 4 + Street Line | 3.0e-9 |
   | H-04 | ITIN Last 4 + Phone | 1.0e-10 |
   | H-05 | ITIN Last 4 + Email | 1.0e-10 |
   | H-06 | ITIN Last 4 + Street Line | 3.0e-9 |
   | H-07 | Subscriber ID + Phone | 1.0e-10 |
   | H-08 | Subscriber ID + Email | 1.0e-10 |
   | H-09 | Subscriber ID + Street Line | 3.0e-9 |
   | H-10 | Phone + Email | 1.0e-12 |
   | H-11 | SSN Last 4 + Subscriber ID | 1.0e-8 (weakest row — correlation caveat, see v3.3.1 §3.3) |
   | H-12 | Phone + ZIP | 3.0e-10 |
   | H-13 | Email + ZIP | 3.0e-10 |
   | H-14 | Phone + Street Line | 3.0e-11 |

   Individual Match rows (Table 2-I):

   | ID | Combination | P(individual\|household) | Gating |
   |---|---|---|---|
   | I-01 | First Name + DOB | 2.0e-6 exact / 3.0e-6 fuzzy | Default. Exact First Name required if DOB is shared by another candidate in the household (twins). |
   | I-02 | First Name + Last Name + DOB | 1.0e-8 | Optional extra-conservative variant; I-01 already clears the bar without it. |
   | I-03 | First Name alone (exact) | 0.02 | Only valid paired with a Household row ≤1.0e-10 (H-01/02/04/05/07/08/10/14). **Not used by any rule this session builds** — every Category 2 rule below uses I-01, not I-03 (see the "generational name reuse" rationale in the callout after Task 4). Defined here only as a building block for a possible future rule. |

   Combined decision rule (v3.3.1 §3.5): a match requires Household-tier fields resolving to
   **exactly one** household per Table 2-H, Individual-tier fields resolving to **exactly
   one** member of that household per Table 2-I, and `P(household) x P(individual) <= 2e-12`
   — the same Core Principle 1 bar, just assembled from two independently-validated numbers
   instead of one flat product. Zero candidates at either step -> decline. Exactly two ->
   escalate to the base doc's existing two-candidate path. Three or more -> stricter
   1-in-a-million re-check or decline (all unchanged from the base doc's §III.B logic, just
   applied per-step instead of once).

**5. NEW — reclassify 4 already-merged rules + 3 of this session's own new rules into
   Category 2, plus add new Rule 38.** These are the only 8 rules in the entire 38-rule set
   that need the two-step process (v3.3.1 §3.6/§4.5):

   | Rule | Status in this repo today | Household leg | Individual leg | Combined P(collision) | Change |
   |---|---|---|---|---|---|
   | 13 | **Already merged**, in `_V322_RULES` as flat `Last Name + Phone + SSN Last 4` | H-01 (SSN Last 4 + Phone) | I-01 (First Name + DOB); Last Name = non-scored corroboration | 2.0e-16 | Amend — First Name + DOB added; the existing flat rule could not select an individual. |
   | 14 | **Already merged**, flat `Last Name + Phone + ITIN Last 4` | H-04 (ITIN Last 4 + Phone) | I-01; Last Name corroboration | 2.0e-16 | Amend, same basis as 13. |
   | 15 | **Already merged**, flat `Last Name* + Email + SSN Last 4` | H-02 (SSN Last 4 + Email) | I-01; Last Name* corroboration | 2.0e-16 | Amend, same basis as 13. |
   | 16 | **Already merged**, flat `Last Name* + Email + ITIN Last 4` | H-05 (ITIN Last 4 + Email) | I-01; Last Name* corroboration | 2.0e-16 | Amend, same basis as 13. |
   | 34 | New, this session's own plan (Task 3 below) | H-12 (Phone + ZIP) | I-01 | 6.0e-16 | Build directly as Category 2 — do not build as a flat rule first. |
   | 35 | New, this session's own plan | H-13 (Email + ZIP) | I-01 | 6.0e-16 | Same as 34. |
   | 37 | New, this session's own plan | H-14 (Phone + Street Line) | I-01 | 6.0e-17 | Same as 34; gated on institutional-address exclusion via H-14's Street Line component, see caveat above. |
   | 38 | **New rule** — recovers Table 4's previously-rejected "Subscriber ID + DOB" | H-07 (Subscriber ID + Phone) — H-08 (+ Email) is an equally valid alternative | I-01 | 2.0e-16 | New. Authoritative recovery per v3.3.1; v3.3.3 independently identified the same gap and defers to this rule rather than proposing a second, incompatible one — do not build a second "Subscriber ID + DOB" rule from v3.3.3. |

   Important implementation note: rules 13-16 are **not new additions** — they already exist,
   merged into `main`, in `_V322_RULES`'s current flat form. This task is an *amendment* to
   already-shipped rule definitions, which the original (v3.3.0-only) version of this doc did
   not anticipate (it assumed `_V322_RULES`'s 26 entries "keep their exact current contents —
   no rule inside it changes"). That assumption no longer holds for 4 of those 26.

   On Last Name as corroboration (rules 13-16): advisory only. A responder MAY log/flag a
   mismatch for data-quality review but SHALL NOT withhold an otherwise-qualifying match
   because Last Name differs (that would silently reintroduce the exact blended-family failure
   — a dependent with a different last name than the subscriber — these rules exist to fix).

### Out of scope

- **Rules 39/40 (v3.3.3 — guardian-verified minor / newborn via maternal linkage). Not built
  this session.** Rule 39 (`First Name + DOB + clinical Relationship Linkage + Street Line`)
  has a flagged, *unresolved* problem in the source proposal itself: Street Line is the
  household's own address and the "child-of an address-matched guardian" relationship term is
  anchored to that same address, so the two terms are correlated, not independent — the flat
  product (≈6e-13) overstates the actual margin, and the proposal says this "should not be
  treated as equivalent in strength to Rule 01" until either Street Line is dropped (weakening
  the rule) or an explicit dependency discount is applied. Rule 40 (`DOB + a per-encounter
  namespace-bound birth ID + clinical Relationship Linkage`) requires a genuinely
  per-encounter unique identifier — a shared *facility* ID does not qualify and the rule
  "does not clear" without one. This repo's `FieldExtractor` only ever sees a `Patient` dict
  (no birth-encounter/Coverage resource wiring); whether a real per-encounter ID is even
  obtainable from upstream FHIR data is unconfirmed. **`NEEDS HUMAN DECISION — Sean/Imran`**:
  (a) how Rule 39's independence problem should be resolved before it's implementable, and
  (b) whether a per-encounter birth identifier is actually available to this system. Until
  both are answered, these are a candidate future session, not this one.
- **v3.3.6's institutional-address registry/postal-validation methodology — not implemented
  this session.** The methodology itself (registry match against CMS/BOP/IPEDS/HIFLD data,
  then CASS-postal fallback, then default-residential) is now specified, but wiring in any of
  those external data sources is new integration work this repo has no existing pattern for,
  and v3.3.4's own footnote raises a real cost/privacy concern about calling an
  address-verification service on every patient address (caching addresses for repeat lookups
  is itself an added attack surface). **`NEEDS HUMAN DECISION — Sean/Imran`**: whether/how to
  build this integration, and whether the cost/privacy tradeoff is acceptable. Until resolved,
  any Household-tier row that includes Street Line (H-03, H-06, H-09, H-14, and rule 37's
  household leg) should be implemented at the code level per this doc's tables, but treated as
  **not yet safe to rely on** for populations with meaningful institutional-address density —
  this replaces the original doc's `enable_household_risk_rules` flag concern with a more
  precisely-scoped one (see callout after Task 4).
- **v3.3.2 (compliance/audit restructuring — Path A/B, §VII changes) and v3.3.5 (accuracy-
  floor charter, §VI.C).** Confirmed via both documents' own text: these modify §II/§VI/§VII
  (compliance verification and audit reporting), not Table 2. Zero matching-rule or field
  content. Out of scope for this session; relevant instead to whoever owns compliance
  reporting or session 8's legacy-comparison/accuracy-validation work.
- The per-value (name-frequency-conditioned) collision-probability refinement — separate,
  not-yet-authored candidate session needing Imran's sign-off.
- Gender as a matching field — v3.3 drops it entirely; this repo's Table 2 rules never
  referenced gender in the first place (confirm by grep before assuming there's cleanup work
  here — `grep -rn gender patient_matching/matching/` and check whether any hits are
  matching-relevant or just FHIR resource shape).
- Twin/multiple-birth handling (v3.3.1 §3.7/§4.7 — exact-match override, placeholder fail-
  closed, middle-name tiebreaker, persistent-ID anchoring). Referenced above wherever it
  affects a field's status (e.g., Rule 36's caveat, I-01's gating condition) but not built as
  runtime logic this session — candidate future session once this session's rule set exists
  to hang it off of.
- Wiring any adversarial household-sharing test case into Thread B's harness — follow-up once
  session 3/4/8 exist, not part of this session's Definition of Done.

## Tasks

1. **Add the three new canonical fields to the field model.**
   File: `patient_matching/matching/table2_rules.py` — add constants alongside the existing
   ones:
   ```python
   ZIP_CODE = "zip_code"
   INSURANCE_MEMBER_ID = "insurance_member_id"
   INSURANCE_SUBSCRIBER_ID = "insurance_subscriber_id"
   ```
   File: `patient_matching/matching/field_extractor.py` — add three new `Set[str]` fields to
   `PatientFields` (`zip_codes`, `insurance_member_ids`, `insurance_subscriber_ids`), add them
   to `get_values()`'s mapping dict, and add extraction logic in `FieldExtractor`:
   - `zip_codes`: extend `_extract_addresses` to also pull `addr.get("postalCode")` per
     address entry.
   - `insurance_member_ids`/`insurance_subscriber_ids`: extend `_extract_identifiers` — these
     come from FHIR `Coverage` resources in a real system, but this repo's `FieldExtractor`
     only ever sees a `Patient` dict (per its docstring: "Extract canonical field values from
     a normalized FHIR Patient resource"). Per the spec, an insurance identifier requires a
     co-submitted Payer ID and SHALL be namespace-scoped — represent this the same way
     `legal_ids`/`namespace_ids` already do (`f"{assigner}|{value}"` — see
     `_extract_identifiers`'s existing `legal_ids` branch for the pattern), reading from
     `patient.get("identifier", [])` entries whose `type.coding` includes a member-ID or
     subscriber-ID type code. **Decide the exact FHIR identifier type codes to key off of at
     implementation time** (check `patient_matching/fhir_client/` and
     `patient_matching/ial2_extraction/` for how identifiers arrive in practice before
     inventing new codes).

2. **Add DOB fuzzy (+/-1 day) comparison.**
   File: `patient_matching/matching/field_comparator.py` — add:
   ```python
   from datetime import date, timedelta

   DOB_FUZZY_TOLERANCE_DAYS = 1

   @staticmethod
   def dob_fuzzy_match(query_values: Set[str], candidate_values: Set[str]) -> bool:
       """CMS v3.3 DOB tolerance: +/-1 day, exact date comparison (not edit distance)."""
       try:
           q_dates = {date.fromisoformat(v) for v in query_values}
           c_dates = {date.fromisoformat(v) for v in candidate_values}
       except ValueError:
           return False  # partial/malformed dates never fuzzy-match
       for q in q_dates:
           for c in c_dates:
               if abs((q - c).days) <= DOB_FUZZY_TOLERANCE_DAYS:
                   return True
       return False
   ```
   File: `patient_matching/matching/matching_engine.py`, method `_evaluate_rule` — change only
   the fuzzy-branch condition to dispatch on field name (DOB uses `dob_fuzzy_match`, everything
   else keeps `fuzzy_match`), leaving the rest of the method unchanged. Import `DOB` from
   `.table2_rules` if not already imported.

3. **Add rules 27-33 (Category 1, unaffected by any addendum).**
   File: `patient_matching/matching/table2_rules.py`. First, rename the existing 26-rule tuple
   literal from `APPROVED_RULES` to `_V322_RULES` — but see Task 4 below, because 4 of those 26
   entries (13, 14, 15, 16) get amended in this same session, not carried over unchanged as
   originally planned. Add rules 27-33 as their own tuple using the fields/values from the
   Scope table above, following the existing `MatchingRule(...)` pattern (see rule 27 in the
   codebase's current rule set for the closest analog — same shape, new field constants).

4. **NEW — build the Household/Individual two-step architecture, then use it to amend rules
   13-16, add rules 34/35/37/38 as Category 2 from the start, and retire the flag idea.**

   > **Why this replaces `enable_household_risk_rules` entirely:** the original (v3.3.0-only)
   > version of this doc treated rules 33-37 as one undifferentiated "household-risk cluster"
   > and proposed shipping 34-37 behind a default-off flag pending a `NEEDS HUMAN DECISION` on
   > whether the false-positive risk was acceptable. v3.3.1 resolves that concern
   > *structurally*: rule 33 turns out to already be fine as a flat Category 1 rule (confirmed
   > unaffected, no household-sharing defect); rules 34/35/37 get the two-step
   > Household-then-Individual treatment instead of a flag, which the source proposal's own
   > math shows clears 2e-12 with 3-4 orders of magnitude of margin (6.0e-16, 6.0e-16, 6.0e-17
   > respectively — see the table above); and rule 36 is retained as an explicitly-flagged
   > legacy exception with a twin caveat, not gated by any flag either. There is no longer a
   > `NEEDS HUMAN DECISION` about enabling a risky rule cluster — the risk was in an
   > *architecture* (flat multiplication of household-shared fields), and v3.3.1 fixes the
   > architecture rather than asking a human to accept the risk. Do not implement
   > `ENABLE_HOUSEHOLD_RISK_RULES` or any equivalent flag.

   a. **Household/Individual row types.** File: `patient_matching/matching/table2_rules.py`
      (or a new sibling module, e.g. `household_rules.py`, if that keeps the file more
      readable — implementer's call). Add a `HouseholdRow` and `IndividualRow` dataclass
      (mirroring `MatchingRule`'s shape: `row_id`, `fields`, `p_collision`) and the H-01
      through H-14 / I-01 through I-03 tuples from the tables above, each computed via
      `p_collision(...)` (session 5's evaluator) rather than hardcoded, as a sanity check
      against the source-doc figures transcribed above.

   b. **Category 2 rule type.** Add a `HouseholdIndividualRule` type (or extend `MatchingRule`
      with an optional household/individual pairing — implementer's call on which reads more
      naturally against the existing `MatchingEngine` code) representing "one H-row + one
      I-row, evaluated as two sequential steps, combined by multiplication." Build the 8
      entries from the table above (13, 14, 15, 16, 34, 35, 37, 38) — worked example for 38:
      ```python
      _CATEGORY_2_RULES: tuple[HouseholdIndividualRule, ...] = (
          HouseholdIndividualRule(
              rule_id="38",
              description="Subscriber ID (household) + First Name/DOB (individual) — "
                           "recovers Table 4's previously-rejected Subscriber ID + DOB",
              household_row=H_07,  # Subscriber ID + Phone
              individual_row=I_01,  # First Name + DOB
              # p_collision computed as household_row.p_collision * individual_row.p_collision,
              # verify == 2.0e-16 against the source table above.
          ),
          # ... 13, 14, 15, 16, 34, 35, 37 go here, same pattern, using the pairings table above ...
      )
      ```
      Build all 8 in full — the `# ...` above is the only intentionally-incomplete part of
      this snippet, standing for the other 7 fully-specified rows in the table above.

   c. **Amend, don't just add.** Remove rules 13, 14, 15, 16 from `_V322_RULES` (Task 3's
      rename) and construct them instead as Category 2 rules per (b). This is the one place
      in this session that changes already-merged rule behavior, not just adds new rules —
      call this out clearly in the session's PR description so Sean/reviewers know it's
      intentional, not scope creep.

   d. **Two-step evaluation path.** File: `patient_matching/matching/matching_engine.py`. Add
      a method (e.g. `_evaluate_household_individual_rule`) that: resolves candidates against
      the household row (decline if zero, escalate per existing two-candidate logic if
      exactly two, stricter re-check if three+, proceed only if exactly one); then, within that
      resolved household, resolves the individual row the same way; then multiplies the two
      probabilities and compares to 2e-12. Reuses the existing candidate-count/escalation logic
      already in the engine (per v3.3.1 §4.1, this is explicitly "applied at each step instead
      of once," not new logic) — do not duplicate that logic, extract it if it isn't already a
      standalone helper.

5. **NEW — extend placeholder exclusion for Subscriber/Member ID (v3.3.4).**
   File: `patient_matching/normalization/placeholder_detector.py`. This module already covers
   6 of v3.3.4's 7 field categories (name, DOB, phone, email, address, SSN — see
   `is_placeholder_name`/`_date`/`_phone`/`_email`/`_address`/`_ssn`). The one gap: no
   `is_placeholder_subscriber_id`/`is_placeholder_member_id` method for v3.3.4's table row
   ("All-zero or all-nine strings, 'PENDING', 'TBD', 'NONE', a payer's documented
   default/test enrollment value"). Add one following the existing methods' pattern (a
   `_PLACEHOLDER_SUBSCRIBER_ID_PATTERNS` list + a same-shaped `is_placeholder_subscriber_id`
   method), and wire it into `FieldExtractor`'s new `insurance_member_id`/
   `insurance_subscriber_id` extraction from Task 1 so placeholder values are stripped before
   they ever reach `PatientFields`. **Do not** assume the existing `is_placeholder_ssn`/
   `_phone`/etc. methods need changes for this session — spot-check them against v3.3.4's
   table (they already appear to cover it: `_PLACEHOLDER_SSN_PATTERNS`'s `^0{3}`/`^9{3}`
   patterns catch all-zero/all-nine last-4 strings, `_PLACEHOLDER_PHONE_PATTERNS` already has
   the 555-exchange and repeated-digit cases, etc.) — only implement what's actually missing.

## Unit tests required

File: `patient_matching/matching/tests/test_table2_rules.py` (existing — update
`test_total_count`, which currently asserts `len(APPROVED_RULES) == 26`; the final count after
this session is 30 Category 1 rules (04-12, 17-33, 36 minus the 4 moved to Category 2) + 8
Category 2 rules (13-16, 34, 35, 37, 38) = 38 total, split across whatever container types
Task 4 introduces — write the exact assertion once that structure exists, don't assume a single
flat `APPROVED_RULES` tuple still holds all 38 if Task 4b's implementer chooses a separate
Category 2 container).

New test files needed:
- `patient_matching/matching/tests/test_household_rules.py` (or wherever Task 4a's module
  lands) — one test per H-row and I-row verifying `p_collision(...)` reproduces the source-doc
  figure transcribed above, within rounding.
- Extend `test_field_comparator.py` with DOB fuzzy boundary cases (exact, +/-1 day true,
  +/-2 days false, year-boundary case) and a malformed-date-never-matches case.
- Extend `patient_matching/normalization/tests/test_placeholder_detector.py` with cases for
  the new subscriber/member-ID method (all-zero, all-nine, "PENDING", "TBD", "NONE", and a
  real-looking ID that should NOT be flagged).
- A test asserting rules 13-16 (post-amendment) can no longer resolve a match using
  Last-Name-differs-from-subscriber data alone (the exact blended-family case v3.3.1 warns
  against silently reintroducing) — i.e., verifies Last Name truly is non-blocking
  corroboration, not an accidental hard requirement.

## Validation (definition of "resolved")

- [ ] `zip_code`, `insurance_member_id`, `insurance_subscriber_id` are extractable via
      `FieldExtractor`/`PatientFields`, with placeholder values already stripped per Task 5,
      and tests covering at least one populated and one empty/placeholder case each.
- [ ] `FieldComparator.dob_fuzzy_match` exists, is used by `MatchingEngine` specifically for
      the `dob` field, and all boundary cases pass.
- [ ] Rules 27-33 exist as Category 1 (flat) rules with `p_collision` figures matching the
      Scope table above.
- [ ] H-01 through H-14 and I-01 through I-03 exist as reusable rows with `p_collision`
      figures matching the tables above.
- [ ] Rules 13, 14, 15, 16, 34, 35, 37, 38 exist as Category 2 (household+individual) rules,
      each pairing the H-row/I-row specified in the pairings table above, with combined
      `p_collision` matching that table.
- [ ] Rules 13-16 no longer exist as flat rules anywhere in the rule set (confirm the old
      3-field literal is gone, not just shadowed).
- [ ] No `enable_household_risk_rules`-style flag exists anywhere in the new code — the
      household/individual architecture is unconditional, per the callout in Task 4.
- [ ] Rules 39, 40, and any institutional-address registry/postal-validation logic are **not**
      present in this session's diff — confirm via the PR description explicitly stating they
      were evaluated and deferred, per "Out of scope," so a reviewer doesn't wonder if they
      were simply missed.
- [ ] `make tests` is green (full suite — this touches shared field-extraction/comparator code
      and amends already-merged rules 13-16, so regressions in rules 01-26 are the main risk).
- [ ] `make run-pre-commit` is clean.
- [ ] Per `conventions.md`'s statistical rigor gate: this session does not move to
      `completed/` until session 3's Tier-1 `ComparisonReport` exists.

## Open questions

- **`NEEDS HUMAN DECISION — Sean/Imran`**: Rule 39's independence/math problem (Street Line
  correlated with the relationship term) — how should it be fixed before the rule is
  implementable? (See "Out of scope.")
- **`NEEDS HUMAN DECISION — Sean/Imran`**: is a genuinely per-encounter, namespace-bound birth
  identifier available anywhere in this system's real data, for Rule 40? If not, Rule 40 has
  no path to adoption as specified.
- **`NEEDS HUMAN DECISION — Sean/Imran`**: whether/how to build v3.3.6's institutional-address
  registry/postal-validation integration, given the cost/privacy tradeoff v3.3.4's own footnote
  raises (calling an address-verification service on every patient address; caching addresses
  as an added attack surface). Until decided, Street-Line-based Household rows are implemented
  at the code level but should not be relied on for institutional-address-heavy populations.
- The exact FHIR identifier type codes for `insurance_member_id`/`insurance_subscriber_id`
  extraction (Task 1) were deliberately left for implementation time rather than guessed —
  this is a legitimate implementation detail the executing agent resolves by reading
  `patient_matching/fhir_client/`/`patient_matching/ial2_extraction/`'s actual identifier
  shapes, not a `NEEDS HUMAN DECISION`.
- **Resolved, no longer open**: the original doc's `NEEDS HUMAN DECISION — Sean/Imran` on
  whether to enable a household-risk rule cluster by default. Superseded by v3.3.1's
  structural fix — see the callout in Task 4. Listed here only so it isn't mistaken for a
  still-open item from the original version of this doc.

## Execution notes

_(empty at authoring time; filled in by whoever executes the session)_
