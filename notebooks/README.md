# notebooks/

Exploratory and demo material for the CMS patient-matching algorithm work — not part of the
`patient_matching` package and not covered by the repo's pre-commit hooks (see the
`exclude:` line in `.pre-commit-config.yaml`).

## What's here

- `cms_matching_demo.ipynb` — end-to-end demo of the CMS matching algorithm against a
  handful of patients using the in-memory backend, no external infrastructure required.
- `rule_eval_demo.ipynb` — walkthrough of `evaluation/rule_eval.py`'s baseline-vs-candidate
  rule comparison (Bayesian credible intervals, ship/reject/needs-more-data verdict).
- `wellsense_member_matching_analysis.py` — a one-off WellSense member-matching
  investigation (Jira RA-4428): failure-log analysis, error-volume trend, and DOB/gender
  raw-value reconciliation. Kept as a plain Python script, not a Databricks-notebook-source
  file — no `# MAGIC` / `# COMMAND ----------` cell markers.

## Why this folder still exists

This repo is a greenfield rebuild of the CMS person-matching algorithm; the notebooks above
were used to validate it against the legacy `helix.personmatching` system during
development. Per the 2026-08-12 Sean/Zack sync, the folder is being **kept intentionally**
for that experimental comparison — but the intent is to **deprecate and delete it** once the
new algorithm's build-out goals are met (see `docs/sessions/`), so that the final, shipped
version of this repo does not carry demo/analysis notebooks.

Until then:
- New files added here should be plain, production-style Python (or `.ipynb`) — no
  Databricks magic-cell scaffolding (`# MAGIC`, `# DBTITLE`, `# COMMAND ----------`).
- Don't treat anything here as a stable public API — nothing outside this folder should
  import from it.
- No real patient data, query output, or table contents belong in this folder or in git —
  see each file's own PHI-handling notes.
