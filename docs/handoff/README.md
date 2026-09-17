> _Repo-safe copy: no PHI; internal emails, infra identifiers (Databricks workspaces / service principals / secret scopes), and internal deep-links have been removed. The full internal version lives with the DS team._

# Data Science Handoff — AI Visit Summary & Patient Matching

Single-document handoff for Zack Malone's areas while out **~2026-07-20 → 2026-08-01**. CMS matching target: **live by mid-August 2026**. Everything is inline below — no external files needed.

**Interim leads:** AI Visit Summary → `baileyai` team · Patient Matching → **Sean**.

## Contents

1. **AI Visit Summary**
2. **Patient Matching**
   - 2.1 Current scoring model
   - 2.2 WellSense work
   - 2.3 CMS proposal work
   - 2.4 Data — what & where it lives
   - 2.5 Ownership & hand-off
   - 2.6 Risks, caveats & best practices
   - 2.7 Glossary
3. **Zane — Person Matching Monitoring Work**

---

## 1. AI Visit Summary

_Separate area (batch LLM → FHIR CarePlan pipeline), off-domain for this repo. Operational and infrastructure specifics (Databricks workspaces, service principals, secret scopes) are intentionally kept out of the repo — see the internal DS handoff doc or ping the `baileyai` team / `#tech-dev`._

---

## 2. Patient Matching


**Key links & contacts for this chapter**

- 📓 Databricks notebook (prod workspace): (prod Databricks notebook — link in the internal handoff)
- Repos (`github.com/icanbwell/…`): `helix.personmatching` (current scoring library, PyPI) · `person-matching-service` (FastAPI FHIR `$match`, **prod for WellSense**) · `patient-matching` (new CMS engine — PR #2 the project lead, PR #3 v1 demo)
- Dashboard: **Sigma → "Connection Matching Error Research"** (base table `bronze.proa.metrics`; WellSense source feed `bronze.wellsense.ws_eligibility_all`)
- Slack: **`#client-wellsense`** · **"WellSense Member Matching"** group DM
- Jira: **BAI-188 / PAY-1940** (June-2026 scoring improvement) · **RA-4428** (raw value-vs-source reconciliation report)

| Person | Role | Contact |
|---|---|---|
| Zack Malone | DS owner — scoring algorithm & this handoff | (internal) |
| **Sean** | **Interim lead while Zack is out**; BAI-188 code reviewer | (Slack) |
| The project lead | Author of the CMS v3.3 proposal & P(collision) reference script | (internal) |
| Anmol Godiyal | Engineering — matching investigation | (internal) |
| Rohit Parihar | Added the "Matching Failure insight" log (PAY-1789/2038); ticket debugging | (Slack) |
| Laurel Salvati | CX / WellSense project lead | (internal) |
| Sarah Jones | Analytics / ticket analysis | (internal) |
| Kristen Valdes | Executive stakeholder (KV) | (internal) |


**Executive summary**

- **Today's matching works and is stable.** WellSense member-match errors are **down ~80% since late May and flat since mid-June** (~17/day, from ~90/day at peak). The remaining failures are **overwhelmingly upstream data problems** (mismatched or missing birthdays in the source vs. what the user typed), **not** the algorithm being too strict. A small, steady manual-review queue is by design, not a defect.
- **There are two separate work streams**, and they should not be confused:
  - **Line A — DOB & gender tuning of the *current* algorithm.** Low effort. **Important finding: even if fully implemented, it recovers essentially none of the current WellSense failures**, because those failures are genuine data conflicts, not algorithm pickiness. Its real value is (a) correctness/consistency and (b) building normalization plumbing that Line B needs anyway.
  - **Line B — Replace the current weighted-rule algorithm with the CMS v3.3 "Probability of Collision" approach.** This is the strategic work and the mid-August target. It is a **paradigm change**, and it is **net-new** — no part of it exists in code yet.
- **The DOB/gender debate largely resolves itself under CMS v3.3:** CMS **does not use gender as a matching field at all**, and it makes **DOB exact (or ±1 day)**. So heavy investment in Line A is hard to justify if Line B lands on schedule.
- **Schedule reality:** mid-August is achievable but tight, because the primary developer (Zack) is out for two of the ~four remaining weeks. The plan de-risks this with **shadow mode** (run CMS logic alongside the current engine in production without acting on it) and by **keeping the current engine as the fallback**. We recommend "**live in staging + shadow in prod by mid-August, prod cutover immediately after validation**" rather than a hard prod cutover on a fixed date.

---

**The two lines of work at a glance**

| | **Line A — DOB/Gender tuning** | **Line B — CMS v3.3 migration** |
|---|---|---|
| What | Small fixes to the *current* algorithm | Replace the algorithm with Probability-of-Collision matching |
| Effort | Low (days) | High (net-new; weeks) |
| Recovers current WellSense failures? | **~0** (failures are upstream data) | Changes the paradigm; measured on ONC data |
| Strategic? | No — largely superseded by Line B | **Yes — the mid-August target** |
| Gender | Normalize `M/F ↔ male/female` | **Gender is dropped entirely (not a matching field)** |
| DOB | Already tolerant (±2d / month±1 / year-typo) | **Exact, or ±1 day only** (stricter) |
| Validated on | WellSense prod data (no ground truth) | **ONC labeled test dataset** (precision/recall/FPR) |
| Recommendation | Do only the reusable normalization part | Focus here |

---

### 2.1 Current scoring model

#### 1.1 Architecture (what runs in production today)

```
FHIR $match request
      │
      ▼
person-matching-service  (FastAPI service; prod for WellSense)
   • parses the request, blocks candidates in MongoDB
   • calls the scoring library
   • filters to score ≥ threshold, shapes the FHIR response
      │
      ▼
helix.personmatching  (pure scoring library, published to PyPI)
   • 17 weighted "uniqueness" rules (Sequoia Project table)
   • per-field comparison (name, DOB, gender, ZIP, …)
   • returns a single 0–1 score + `matched` boolean
```

- **Service:** `person-matching-service` — implements FHIR `POST /$match`. Entry point `personmatching/service/match_service.py`; scoring called at `match_service.py:70`.
- **Library:** `helix.personmatching` — the algorithm. Core scorer `logics/score_calculator.py`, rule set `logics/rule_library.py`, per-field logic `models/rules/attribute_rule.py`.
- **How a score is produced:** each rule scores a field combination; the engine takes the **highest** rule score, adds small boosts, and compares to a threshold. Confidence is effectively driven by *which fields agree and how strongly*.
- **⚠️ Two thresholds exist in two layers** (worth fixing/clarifying during the migration):
  - Library default `MATCH_THRESHOLD = 0.955` (`matcher.py:36`).
  - Service re-filters at `_DEFAULT_MATCH_THRESHOLD = 0.9555` (`match_service.py:32`), set in prod via env `MATCH_SCORE_THRESHOLD = "0.9555"` (`.helm/common.values.yaml`). The service does not pass its threshold into the library, so the library computes `matched` at 0.955 and the service re-filters at 0.9555. **Behavioral tuning of the threshold ships via Helm env, without a code release.**
- **Provenance / lineage:** the current tolerant behavior (nickname/initial handling, graduated DOB near-miss credit, "ignore missing fields") shipped under **BAI-188 / PAY-1940 (~June 4, 2026)** — the mid-June error drop coincides with it.

#### 1.2 State of errors (the numbers, as of mid-July 2026)

| Metric | Value | Source |
|---|---|---|
| WellSense match errors, last 30 days | **~17/day** (519 run-attempts total) | Sigma "Connection Matching Error Research" |
| vs. prior 30 days | **−75%** | Sigma |
| vs. late-May peak (~90/day) | **−81%** | Sigma |
| Trend within current regime | **Flat** (slope ≈ 0/week) — holding, not regressing | Sigma |
| Unique people who failed to auto-match (30-day window) | **146** | enterprise-person-service logs |
| Of those, DOB disagreed | **89%** (130/146) | logs |
| Of those, gender disagreed | **47%** (69/146) — but **never the sole blocker** | logs |
| "Perfect on 4 of 5 fields, only DOB wrong" | **13 records**, all capping at score **~0.80** | logs |

**Plain-English read:** the two birthdays being compared — the one WellSense sent us vs. the one the person typed at sign-up — genuinely differ (or one is blank). We confirmed the values are stored in the **same `YYYY-MM-DD` format on both sides**, so this is **not a date-parsing bug on our side**. A wrong birthday caps the score around 0.80 no matter how perfect everything else is; recovering those would mean dropping the bar from 0.955 to 0.80 and **auto-linking different people** — an unacceptable trade in healthcare.

**Why "zero errors" is not a goal:** matching compares two independently-authored records. As long as humans type and upstream files carry gaps, some pairs will genuinely disagree. The job is to link the same person *without* linking different people; the only way to auto-recover the last genuine-disagreement cases is to loosen matching, which mathematically links wrong people. A **small, stable manual-review queue is the designed safety margin.**

---

### 2.2 WellSense work

#### 3.1 The problem being asked about

Stakeholders have asked whether DOB and gender are "behaving incorrectly." Findings:

- **Gender:** the current code only lowercases gender; it has **no `M/F ↔ male/female` mapping**. So a source value of `"M"` vs. a typed `"male"` scores as a *non-match* even though they mean the same thing. Missing/unknown gender is already treated leniently (and dropped from the average when ≥3 other fields are present). In the WellSense failure set, gender is **never the sole blocker**.
- **DOB:** exact-only with graduated near-miss credit (day ±2 → 0.95, month ±1 → 0.90, single-digit year typo within 2 years → 0.85). We verified DOB mismatches are **genuinely different dates / typos / missing**, not a format bug.

#### 3.2 Proposed changes and expected impact

| Change | What it does | Expected impact | Reusable for CMS? |
|---|---|---|---|
| **Gender normalization** (`M/F ↔ male/female`, unknown/other handling) | Stops encoding differences from reading as conflicts | **Correctness/consistency only. ~0 additional WellSense auto-matches** (gender is never the lone blocker). | ❌ CMS doesn't use gender |
| **Confirm DOB parsing** (done) | Rule out a format/parse bug | Confirmed *not* a bug → **no code change warranted**; failures are upstream | ✅ knowledge reused |
| **Do NOT extend DOB tolerance** | (Considered and rejected) | Loosening DOB to accept genuinely-different dates would **increase false links**; CMS makes DOB *stricter* anyway | — |
| **Placeholder / junk-value suppression** (e.g. `000-00-0000`, test names, `UNKNOWN`) | Ignore non-comparable values | Modest quality gain now | ✅✅ **required by CMS §V — build once** |
| **Wire normalization consistently** (diacritics, whitespace/punctuation, E.164 phone, Project US@ address) into the live compare path | These utilities exist but aren't consistently applied | Modest quality gain now | ✅✅ **required by CMS §V** |

**Key takeaway for stakeholders:** *Line A does not meaningfully reduce the current WellSense error count* — those errors are upstream data quality, which no algorithm change fixes. The parts of Line A worth doing (**placeholder suppression + consistent normalization**) are worth doing because **CMS v3.3 requires them anyway**. Treat them as the first, shared step of Line B, not as a separate WellSense "fix."

#### 3.3 How to test Line A

- Unit tests: `helix.personmatching/tests/test_scoring_improvements.py` (add gender-normalization and placeholder-suppression cases).
- Regression: `make tests` in `helix.personmatching` (`pytest -m "not integration"`).
- Real-world check: the **RA-4428** raw value-vs-source reconciliation (see §5) tells us how many gender "mismatches" are encoding vs. genuine, so we can *measure* the gender-normalization benefit instead of guessing.
- Notebook: `helix.personmatching/notebooks/held_out_evaluation.py` (precision vs. Sigma reviewer labels).

#### 3.4 Line A risks
- **Over-crediting a fix that recovers nothing.** Don't report gender normalization as a WellSense error reducer; report it as correctness + CMS groundwork.
- **Scope creep into "add a rule per edge case"** → overfitting and false positives. Avoid.

---

**WellSense resources:** analysis lives in the prod Databricks notebook linked at the top of this chapter (3-layer data explainer + reconciliation); the failure export analyzed was the 2026-06-11→07-11 demographics pull from `enterprise-person-service` logs. Dashboard: Sigma "Connection Matching Error Research". Reconciliation tracked in **RA-4428**.


### 2.3 CMS proposal work


#### Do we understand what the proposal is saying? Yes.

The proposal replaces vendor-specific, ad-hoc matching logic with a **deterministic rule set grounded in collision probability**. The rule: if an incoming query's identity fields correspond to one of ~37 pre-approved field combinations (Table 2), and the match resolves to **exactly one** candidate in our system, we **SHALL return** the patient's records. Refusing to return in that case is non-compliance.

Each approved combination was selected because its **P(collision)** — the probability that two *different* people share identical values across all fields in the combination — is ≤ **2×10⁻¹²** (1 in 500 billion). P(collision) is computed Fellegi-Sunter style: multiply conservative per-field u-probabilities (Table 3), e.g., Last Name (0.005) × DOB (0.0001) × Phone (0.000001) = 5×10⁻¹³ → approved. Passing the threshold is **necessary but not sufficient** — combinations are also screened administratively for correlated fields, family/twin sharing, recyclable IDs, etc. (Table 4 rejections).

The philosophical stance: false negatives (records silently not returned — ~50–60% of cross-org queries today) cause invisible, cumulative harm; false positives (wrong-patient release) are rare, auditable, and correctable. The framework deliberately optimizes for **recall** while capping false-positive risk via the threshold, uniqueness check, and tiered escalation (2 candidates → disambiguate; 3+ → stricter 1-in-a-million threshold or decline).

#### Key implementation steps

| # | Step | Technical implementation | ELI5 |
|---|------|--------------------------|------|
| 1 | **Normalize all fields** | Case-fold, strip punctuation/whitespace, diacritic folding; addresses → Project US@ format; phones → E.164; DOB → YYYY-MM-DD (never impute partial dates); split names into components | Clean everything up the same way so "O'Brien" and "OBRIEN" look identical before comparing |
| 2 | **Suppress placeholders** | Maintain versioned reference tables + regexes for junk values (Baby Boy, TEST, 999-99-9999, DOB >120 yrs old); treat as *unavailable*, never as match or conflict | Throw out fake filler values so "UNKNOWN" never accidentally matches "UNKNOWN" |
| 3 | **Match against value sets (history)** | Each field = set of all known values (all prior last names, addresses, phones); a match on any set member satisfies the field | Check the person's old names/numbers too, not just the current ones |
| 4 | **Apply Table 2 combinations** | Test the query's fields against the approved combination list; only listed combos qualify; MBI/SSN-4/email/ZIP/IDs always exact; insurance IDs only within payer namespace | Only use the pre-approved "recipes" of fields that are proven to be nearly impossible for two people to share |
| 5 | **Constrained fuzzy matching** | Damerau-Levenshtein distance ≤ 1, only on first name, last name, street line; only fields starred in Table 2; string ≥ 5 chars; max one fuzzy field per combination; no Soundex (unless validated against test data) | Forgive exactly one typo, only in names/street, and only where the rules say it's safe |
| 6 | **Uniqueness check** | Query must resolve to exactly 1 candidate in our source system; 2 candidates → escalate/disambiguate; 3+ → apply 1e-6 threshold or decline | If two patients both fit, don't guess — release nothing |
| 7 | **Deterministic contraindication** | If generational suffix (Jr./Sr.) is present on both sides and disagrees, negate the match even if a Table 2 combo passed | A "Jr. vs Sr." mismatch is a hard stop — it's probably the father/son |
| 8 | **IAL2 token validation** (patient-facing apps) | Validate OIDC token: signature vs CSP JWKS, iss/aud/exp/iat, jti anti-replay log; extract demographics from token and run them through steps 1–7 like any query | Check the app's government-grade ID badge is real and unused before trusting the identity data inside it |
| 9 | **Validate before go-live** | Benchmark against ONC patient-matching test dataset (or approved successor) before production and after any matching-logic change; report precision, recall, FP rate at operating point; local acceptance testing even if vendor benchmarked | Prove on a standardized exam that our matcher behaves correctly before turning it on |
| 10 | **Audit & monitor** | Log every Table 2 evaluation: initiator, combo used, exact/fuzzy, records matched, uniqueness result, determination, timestamp, (ideally) software version; monitor ambiguity rates, FP incidents, drift | Keep receipts for every decision so any mistake can be found, explained, and fixed |

#### Precision / Recall / Sensitivity — what to watch while building

- **Precision** = of the matches we return, what fraction are the right patient? = TP / (TP + FP). Here a false positive is a **wrong-patient record release** — the critical error. The 2e-12 threshold, uniqueness check, and suffix rule exist to keep precision effectively at 1.0. Watch: any FP on the ONC test set at the configured operating point is a red flag; fuzzy-rule violations (distance > 1, short strings, >1 fuzzy field) are the likeliest source.
- **Recall** = of the queries that truly belong to a patient we hold, what fraction do we return? = TP / (TP + FN). A false negative is **silent non-return** — the harm the whole framework targets (status quo ≈ 40–50%). Watch: over-aggressive placeholder suppression, missing historical values, and failure to normalize (accents, hyphens, nicknames) will quietly destroy recall; also, failing to return on a valid Table 2 match is *non-compliance*, not caution.
- **Sensitivity** = the same quantity as recall (TP / (TP + FN)) — the clinical/epidemiology term for it. In validation reports, "recall" and "sensitivity" are interchangeable here.

**The build target:** maximize recall subject to a near-zero false-positive constraint — the threshold and administrative rules handle precision by design; our implementation quality (normalization, history handling, placeholder tables) is what determines recall. Both must be reported, with FP rate, on the ONC dataset before production.

#### CMS migration plan (Line B)

#### 4.1 What CMS v3.3 is, in plain terms

CMS v3.3 (`CMS_Patient_Matching_Proposal_v3.3.0 (1).md`, draft 6/24/2026) replaces "score the fields and compare to a threshold" with a fundamentally different idea:

- **Confidence is measured by how unlikely a coincidence is, not by counting fields.** Each field has a "collision probability" (how often two *different* people share the same value). A combination of fields is **approved** only if the odds that two different people share *all* of them is **≤ 2 in a trillion (2e-12, ~1 in 500 billion)**.
- **Matching is combination-based.** The proposal ships **Table 2 — 37 approved field combinations** (e.g. *First + Last + DOB + Street*, *First + DOB + Member ID (within payer namespace)*). If a query matches **any** approved combination **and** resolves to a **single unique candidate** in your system, you **must** return the record.
- **Tiered uniqueness logic** controls false positives: 1 unique candidate → return; 2 candidates → may escalate (MFA/disambiguation); 3+ → apply a stricter 1-in-a-million threshold and may decline.
- **Disagreement on fields *outside* the matched combination does not break the match** — the assumption is the extra field is stale/incomplete, not that the match is wrong. (This is the opposite of today, where a DOB conflict tanks an otherwise-perfect match.)
- **Heavy normalization is mandatory** (§V): case-insensitive, strip punctuation/whitespace, diacritic folding, DOB `YYYY-MM-DD` (no imputing partial dates), nickname tables, match against **all known/historical values**, phones to E.164, addresses to Project US@, and **placeholder suppression**.
- **Fuzzy matching is tightly constrained:** Damerau-Levenshtein distance of 1 (one insert/delete/substitute or one transposition), name fields + street line only, ≥5 characters, at most one fuzzy field per combination. DOB gets **±1 day** where a rule marks it fuzzy. No Soundex.
- **Gender/sex is not a matching field anywhere in Table 2.** **Suffix mismatch is a deterministic veto** (if both sides have a generational suffix and they differ, do not match).

#### 4.2 How it differs from what we do today

| Dimension | Current (weighted rules) | CMS v3.3 (collision probability) |
|---|---|---|
| Decision basis | Highest weighted rule score ≥ 0.955 | Any Table 2 combination clears P(collision) ≤ 2e-12 **and** unique candidate |
| Gender | Weighted field | **Not used** |
| DOB tolerance | ±2 days / month±1 / year-typo | **Exact or ±1 day** |
| Non-matched extra field | Drags the score down (can block) | **Does not negate the match** |
| Ambiguity (2+ candidates) | Return best above threshold | **Tiered: escalate / decline** (uniqueness required) |
| Historical values | Not systematically used | **Must match against all known/historical values** |
| Normalization | Partial, inconsistent | **Extensive and mandatory** |
| Validation | Prod data + reviewer labels | **ONC labeled test set: precision/recall/FPR** |

#### 4.3 What it means for WellSense specifically

WellSense member sign-up maps naturally onto Table 2 insurance rules — **#27** (First + DOB + Member ID w/ payer namespace), **#28** (Last\* + DOB\* + Member ID), **#31/#32** (First/Last + DOB + Subscriber ID). Two consequences:
- **Member ID must include the dependent suffix** (individual-level), and matching must be **scoped to the payer namespace**. Bare subscriber IDs are treated more conservatively (family-shared).
- The current DOB-dominated failure pattern changes: under CMS, a wrong DOB still matters (DOB is in these rules), but the **uniqueness + namespace-scoped Member ID** does more of the work, and gender drops out entirely.

#### 4.4 Implementation plan (net-new build)

There is **no existing code to reuse** — this is a new matching engine inside `helix.personmatching`, exposed through `person-matching-service` behind a feature flag.

**Component build list (in `helix.personmatching`):**
1. **Normalization layer (§V)** — the shared groundwork from Line A, completed: consistent diacritic/whitespace/punctuation folding, E.164 phones, Project US@ addresses, **placeholder suppression** (currently missing), nickname tables (exist), name-component split (exists), DOB out-of-range suppression (>120y / >today+2d), historical-value handling.
2. **Per-field u-probability table (Table 3)** and **P(collision) evaluator** — validate our numbers against the proposal's **reference script** (the project lead's gist / Colab, linked in the doc §IV.I).
3. **Table 2 combination engine** — evaluate a query against the 37 approved combinations; exact vs. fuzzy per the field's `*` flag; ≤1 fuzzy field; suffix veto.
4. **Uniqueness + tiered-response logic** — 1 / 2 / 3+ candidate handling.
5. **Audit record** (§VII) — combination evaluated, exact/fuzzy, uniqueness result, decision, timestamp, version.

**Service integration (in `person-matching-service`):**
6. Add a **matching-engine feature flag** (env) so `match_service.py` can call *either* the current scorer *or* the CMS engine. Default off → shadow → on.
7. **Shadow mode:** run CMS engine alongside current in prod, log both decisions, act on neither difference until validated.

#### 4.5 How to test Line B (this is the crux of "going live")

CMS §VI **requires** validation on the **ONC patient-matching test dataset** and reporting **precision, recall, and false-positive rate** at the operating point. We already have the harness scaffold:

- **Location:** `helix.personmatching/tests/cms_dataset/` — `test_cms_dataset.py` (self-match integrity), `test_cms_performance.py` (masking/robustness), ONC shards in `files/onc/*.csv`, generated bundles + `*.metrics.json` in `files/bundles/`.
- **Run:** `pytest -m integration tests/cms_dataset` inside the dev container (excluded from default `make tests`, which runs `-m "not integration"`).
- **Gap to close first:** the harness currently reports **counts** (`passed / wrong / nomatch / wrong_higher_prob`) with **lenient asserts** (`< 1.0`) and no precision/recall gates. **First task:** extend it to compute and assert **precision / recall / FPR**, and record a **baseline for the *current* algorithm** so we can prove the CMS engine meets-or-exceeds it. (Current illustrative numbers on shard A-C, 1000 records: `passed 956, wrong 7, nomatch 37` — i.e. ~95.6% recall, ~0.7% wrong — this is the bar to beat.)
- **P(collision) validation:** run the proposal's reference script against our u-values to confirm each Table 2 combination clears 2e-12 as claimed.
- **Service-level:** Bruno API collection (`person-matching-service/bruno/`) for `$match`; end-to-end tests in `tests/end_to_end/match/`.
- **Shadow validation:** compare CMS vs. current decisions on live WellSense traffic before cutover.

#### 4.6 Expected impact of Line B

- **Recall (correct records returned) should rise:** combination coverage + "extra field disagreement doesn't block" + historical values are designed to return more true matches than a single-threshold score. To be **measured** on ONC data, not assumed.
- **False positives controlled differently but rigorously:** the uniqueness check + tiered logic + 2e-12 collision bar are the guardrails, replacing the 0.955 threshold. Target: **FPR at or below the current algorithm and within the framework benchmark** (the CMS "safe harbor" self-attestation).
- **The WellSense DOB/gender debate is neutralized:** gender is gone; DOB is exact/±1 day and no longer the dominant single-field veto once namespace-scoped Member ID carries the match.
- **Success criteria for go-live:** on the ONC dataset, **recall ≥ current baseline AND FPR ≤ current baseline AND ≤ framework benchmark**, with documented precision/recall/FPR and a passing uniqueness/normalization test suite.

#### 4.7 Timeline to mid-August

| Window | Dates (approx.) | Owner | Deliverable |
|---|---|---|---|
| **Wk 0 — prep** | Jul 16–18 (Zack present) | Zack → hand to Sean | Freeze scope; extend ONC harness to emit precision/recall/FPR; **record current-algorithm baseline**; finalize this doc; Line A normalization started |
| **Wk 1–2 — build** | Jul 21 – Aug 1 (**Zack OUT**) | **Sean leads** | Normalization layer + P(collision) evaluator + Table 2 engine + uniqueness/tiered logic, iterating against ONC harness; all behind feature flag |
| **Wk 3 — validate** | Aug 4–8 (Zack back) | Zack + Sean | Tune to meet success criteria on ONC; **shadow mode** in prod vs. current; reconcile differences |
| **Wk 4 — ship** | Aug 11–15 | Zack + Sean + Platform | Staging deploy + acceptance tests → **prod cutover behind flag**, current engine as fallback; monitoring live |

> **Schedule caveat (call this out to leadership):** two of the four remaining weeks are without the primary developer. "Live by mid-August" is realistic as **"in staging + shadowing prod by mid-August, prod cutover on validation."** A hard prod cutover on a fixed date with the lead just back from PTO is the riskier reading and is not recommended.

---

### 2.4 Data — what & where it lives

**This is the most-confused point, so it is stated explicitly: the two lines of work are validated on *different* data, answering *different* questions.**

| Dataset | Where | Grain | Ground truth? | Used by |
|---|---|---|---|---|
| **WellSense failure logs** (JSON) | `wellsense-member-matching-demographics-*.json` (from `enterprise-person-service` logs) | 1 row / unique failed person | No | Current state / Line A |
| **Sigma error dashboard** | Sigma "Connection Matching Error Research"; base table `bronze.proa.metrics` (Databricks) | 1 row / pipeline run (retries counted) | No | Volume & trend |
| **Raw value reconciliation (RA-4428)** | Sigma "Member Match Fail Review" element (Custom SQL) + `bronze.wellsense.ws_eligibility_all` (source feed, join on `member_id`) | 1 row / reviewed run | Partial (analyst) | Line A diagnosis |
| **ONC patient-matching test dataset** | `helix.personmatching/tests/cms_dataset/files/onc/*.csv` (from github.com/onc-healthit/patient-matching) | Labeled test records | **Yes** | **Line B validation (required by CMS §VI)** |
| **P(collision) reference script** | The project lead's gist / Colab (linked in proposal §IV.I) | — | — | Line B: validate Table 3 u-values |

**Why this matters:**
- **Line A / current state uses WellSense *production* data** — real and messy, but with **no ground-truth labels**. It tells you *how the system behaves in the wild* and *where the upstream data is broken*. It cannot, by itself, tell you precision/recall (we don't know the "right" answer for each record).
- **Line B uses the ONC *labeled* test dataset** — a standardized set where the correct answer is known, so you can compute **precision, recall, false-positive rate**. CMS *requires* this. It is **not WellSense-specific** and won't reflect WellSense's exact population.
- **The right workflow:** *tune and accept the CMS engine on ONC labeled data (is it correct?), then confirm it on WellSense prod data via shadow mode (does it behave well on our real traffic?).* Two datasets, two questions — don't substitute one for the other.
- **Handling note:** the WellSense/reconciliation data is **PHI**. Keep it in governed environments (Databricks/Sigma); don't export raw values into local files or notebooks.

---

### 2.5 Ownership & hand-off

**Interim lead: Sean** (already the code reviewer on the current algorithm; knows the repo).

**Sean can proceed without Zack on:**
- The **normalization layer** (placeholder suppression, E.164, Project US@, diacritics) — well-specified in CMS §V, benefits both lines.
- **Extending the ONC harness** to emit precision/recall/FPR and recording the current-algorithm baseline.
- **Building the P(collision) evaluator + Table 2 engine + uniqueness/tiered logic** behind the feature flag, iterating against the ONC harness.
- Everything stays **behind a feature flag; no production behavior changes** in Zack's absence.

**Decisions to hold for Zack's return (Aug 4) or escalate to the project lead:**
- **Final threshold/operating-point acceptance** and any deviation from the 2e-12 framework bar.
- **Prod cutover** decision (shadow → live).
- Any change that would **alter current production matching behavior** before CMS is validated.

**Guardrails during PTO (do NOT):**
- Do **not** cut over prod to the CMS engine while Zack is out.
- Do **not** lower the current `MATCH_SCORE_THRESHOLD` to chase WellSense recovery — the failures are upstream; loosening creates false links.
- Do **not** add per-edge-case rules to the current algorithm (overfitting).

**Checkpoints:** end of Wk1 (Jul 25) and Wk2 (Aug 1) written status in the WellSense/matching channel; baseline + interim ONC metrics attached.

**Reference material for whoever picks this up:**
- CMS spec: `CMS_Patient_Matching_Proposal_v3.3.0 (1).md`
- This plan: `Patient_Matching_Plan_2026-07.md`
- Current-state analysis notebook: `wellsense_member_matching_analysis.py`
- Scoring code to replace: `helix.personmatching/logics/score_calculator.py`, `logics/rule_library.py`, `models/rules/attribute_rule.py`
- Service seam: `person-matching-service/personmatching/service/match_service.py` (threshold `:32`, scoring call `:70`)
- Validation harness: `helix.personmatching/tests/cms_dataset/`

---

### 2.6 Risks, caveats & best practices

**Risks / caveats**
1. **CMS v3.3 is a DRAFT** ("Draft for Technical Validation," 6/24/2026, in comment period). Table 2, the 2e-12 threshold, and fuzzy rules **can still change.** Build to the spec but **keep u-values and the threshold in config**, not hard-coded, so a spec revision is a config change.
2. **Schedule compression** — see §4.7. Primary dev out 2 of 4 weeks. Mitigate with shadow-first and current-engine fallback.
3. **Net-new code = new bug surface.** The current engine is battle-tested; the CMS engine is not. Shadow mode + ONC gates + keeping the fallback are the safety net.
4. **Normalization gaps are real** (placeholder suppression missing; E.164/Project US@/diacritics only partial). Getting normalization wrong silently changes match results. Test normalization in isolation.
5. **Namespace binding for insurance IDs** (payer namespace required; Member ID must include dependent suffix) is easy to get wrong and directly affects WellSense.
6. **Uniqueness is now load-bearing.** "Return only if exactly one candidate" requires reliable blocking/candidate generation; a blocking miss becomes a non-return.
7. **PHI handling** — keep reconciliation/prod data in governed environments.
8. **Two-threshold confusion** (0.955 vs 0.9555) should be reconciled during the migration to avoid ambiguity.

**Best practices baked into this plan**
- **Evidence over assertion:** no "it's better" claims without ONC precision/recall/FPR numbers vs. a recorded baseline.
- **Feature-flagged + shadow mode + fallback:** never a blind cutover.
- **Don't tune toward zero errors:** a small stable review queue is correct; loosening to recover genuine data conflicts creates false links (the costly error in healthcare).
- **Config, not code, for thresholds/u-values** so spec drift and tuning don't require releases.
- **Separate the data questions:** correctness on ONC labeled data; real-world behavior on WellSense prod via shadow.
- **Audit everything** (CMS §VII): combination, exact/fuzzy, uniqueness, decision, version — required and invaluable for debugging.

---

### 2.7 Glossary

- **Match threshold (0.955 / 0.9555):** current cutoff; score at/above it → auto-link. (Library 0.955; service re-filters at 0.9555.)
- **P(collision):** probability two *different* people share the same values for a field combination. CMS approves a combination only if ≤ **2e-12** (~1 in 500 billion).
- **u-probability:** per-field collision probability (Fellegi-Sunter record-linkage term); the building block of P(collision).
- **Table 2:** the 37 CMS-approved field combinations eligible to trigger a match.
- **Uniqueness check:** CMS requires a query to resolve to exactly **one** candidate to return.
- **Fuzzy (Damerau-Levenshtein 1):** tolerate one edit or one adjacent transposition; names + street only, ≥5 chars.
- **Shadow mode:** run the new engine alongside the old in prod, log both, act on neither, to compare safely.
- **Precision / Recall / FPR:** correctness metrics computable only with ground-truth labels (→ ONC dataset).
- **ONC dataset:** the labeled patient-matching test set CMS §VI requires for validation.
- **Safe harbor (CMS §IX):** organizations at/above the framework's benchmarks may self-attest rather than adopt a prescribed method.
- **BAI-188 / PAY-1940:** the June-2026 scoring improvement (nicknames, initials, DOB near-miss, missing-field handling) whose deploy coincides with the mid-June error drop.

---

## 3. Zane — Person Matching Monitoring Work

**Owner:** Zane · **Scope:** anomaly detection & monitoring for person-matching **ingestion volume, error counts, and error rate** (and, next, the scoring metrics) — surfaced via Sigma dashboards and recurring Slack alerts.

**Dashboards (published in Sigma):**
- Overall daily total ingestion, error counts, and error rate
- Per-connection daily total ingestion, error counts, and error rate
- Top-error rankings table; error-metric definitions/explanation included

**Alerts:**
- V1 volume + error monitoring alert queries created and tested
- Open feedback from Sean: re-evaluate the queries to determine the best anomaly-detection method

**Done / feedback implemented:**
- `sigma_write` access workaround found
- Explanation for error metrics added
- Top error rankings table added
- Sigma dashboard published
- Alerts tested

**Distribution analysis:**
- Data does **not** follow a normal distribution
- Reviewed transformation histograms → **log transform** judged the best method

**Next steps:**
- Test whether a **percentile** method works well for ingestion counts
- Implement the decided method for ingestion counts
- Set up recurring Slack alerts
- Decide the method for errors / error rates (leaning **Poisson**)
- Then extend monitoring to the scoring metrics

**Goal by Zack's return:**
- Volume + error-rate detection fully complete
- V1 anomaly detection for the 3 metrics involving **scoring** and the **`sigma_write`** tables

