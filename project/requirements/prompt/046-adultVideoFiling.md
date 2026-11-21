# Adult video filing implementation

Implement [REQ-046](../features/046-adultVideoFiling.md) as
`media organise --adult [SOURCE]`. The requirement is authoritative for the
naming convention, scope, exclusions and all acceptance criteria.

Keep name parsing and the performer split testable without the filesystem.
Route all moves, quarantines and folder removals through
`organiseMyVideo/filesystemOperations.py`, following
[ADR-003](../../adr/003-filesystemSafetyBoundary.md). Do not change the movie,
TV or merge workflows.

Update CLI help, `documentation/commandLineInterface.md` and `README.md`, and
add regression tests using temporary trees. Verify with `python -m pytest`.
Hand off with evidence for each acceptance criterion, including a dry-run plan
from the real download folder. Any confirmed run on real media needs the
user's approval.
