# Catalogue stale location removal implementation

Implement [REQ-043](../features/043-catalogueStaleLocationRemoval.md). The
requirement is authoritative for scope, exclusions and acceptance criteria.

Change catalogue rows only. Never move or delete media. Keep a location `stale`
for one scan before removing it, and never treat an unmounted or unlistable disk
as retired. Use temporary trees in tests, and rehearse against a copy of the
real catalogue rather than the live file.

Verify with `python -m pytest`, `runLinter` and `manageProject check`.
