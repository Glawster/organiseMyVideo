# Current increment

## Objective and status

REQ-038 movie location lookup is complete. `media locate --movie TITLE` searches
the persisted movie catalogue and prints titles with years, folders and states.

## Accepted scope and evidence

- Case-insensitive partial matching accepts surrounding whitespace and years.
- Exact title matches precede partial matches.
- Missing folders are unverified until an authoritative scan marks them stale.
- No matches exit 1; movie and show selectors are mutually exclusive.
- Default TV listing and shared debug flags retain their existing routing.
- Public CLI integration uses real movie files and a temporary SQLite catalogue.

## Final verification

- Locate, CLI and catalogue location reconciliation tests: 59 passed.
- Black applied to changed Python files; `git diff --check` passed.
- README and both locate parsers describe the new option.

## Remaining work and immediate next action

No implementation or verification remains. Review the working-tree change.
