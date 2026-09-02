Requirement: 001 — project/requirements/features/001-standardsAdoption.md
Role: implement and verify

Read the authoritative requirement, the standards audit, and all applicable
repository instructions before changing anything. Deliver acceptance criteria
1–5 only. Preserve the packaged CLI and runtime behaviour.

Limit changes to `project/` governance records and the root README documentation
index. Do not implement technical remediation from Phases 2–7 and do not invent
requirements for historical work.

Verify with:

- `pytest -q`;
- `git diff --check`;
- a local Markdown-link check for the introduced governance files; and
- manual comparison of the roadmap with the standards audit.

If the requirement is ambiguous or its outcome must change, stop and report the
decision needed. Do not infer new scope.

Handoff with:

- files changed and why;
- acceptance-criterion-to-evidence mapping;
- commands run and results; and
- assumptions, risks, decisions, and unresolved items.
