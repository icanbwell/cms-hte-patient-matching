# In-Review Sessions

A session lands here when its own work is done — every Validation criterion met, `make tests`/
`uv run pytest .` green, `make run-pre-commit` clean — and its PR is open, but **not yet
merged** into `main`. This is deliberately a separate state from `completed/`: a session doc
in `completed/` is a claim that its code is actually on `main` and safe for another session to
build on; a session sitting here is not that yet.

Concretely, this matters for the "start the next session" protocol's upstream-dependency check
(`conventions.md` step 3): a session with a hard code dependency on one sitting in `in_review/`
should **not** start yet, even though the dependency's doc says its work is finished — branching
from `main` won't have that code until the PR merges. A session with only a *merge-gate*
dependency (not a code dependency — see `conventions.md`'s statistical rigor gate) can still be
coded in parallel; it just can't move to `completed/` before the `in_review/` session does.

When a PR sitting here later merges (possibly in a different session/conversation than the one
that opened it): move the doc from `in_review/` to `completed/`, and update `index.md` the same
way closing any other session would — see `conventions.md`'s Definition of Done.
