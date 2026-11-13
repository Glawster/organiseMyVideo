# Rugby video filing implementation

Implement [REQ-041](../features/041-rugbyVideoFiling.md) as
`media organise --rugby [SOURCE]`. The requirement is authoritative for the naming
convention, scope, exclusions and all acceptance criteria.

Use the results sources named in the requirement. Before starting, agree how
earlier seasons are looked up and record the decision,
including how results are read and cached, in an ADR. Do
not assign a played date from a file's modified time or from an inference. Hold a
file for review whenever the evidence does not identify one fixture.

Keep parsing, season and naming logic testable without the filesystem or network.
Route all moves through the boundary in `organiseMyVideo/filesystemOperations.py`,
following [ADR-003](../../adr/003-filesystemSafetyBoundary.md). Do not write
metadata tags, re-encode, alter existing store files or change the movie and TV
organise workflows.

Update CLI help, `documentation/commandLineInterface.md` and
`documentation/homeVideo.md`, and add regression tests using temporary trees and a
stubbed results source. Verify with `python -m pytest` and `manageProject check`.
Hand off with evidence for each acceptance criterion, including a dry-run plan from
a real download folder. Any confirmed run on real media needs the user's approval.
