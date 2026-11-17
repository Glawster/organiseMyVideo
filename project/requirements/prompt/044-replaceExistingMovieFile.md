# Replace an existing movie file implementation

Implement [REQ-044](../features/044-replaceExistingMovieFile.md). The requirement
is authoritative for scope, exclusions and all acceptance criteria.

Before starting, get the user's decision on the two pending items in the
requirement: whether TV episodes are included, and whether interactive runs
prompt for each collision.

Fix existing-folder matching first, in `findExistingMovieDir` in
`organiseMyVideo/video.py`, reusing the identity comparison in
`organiseMyVideo/movieIdentity.py`. Then add `--replace` to `media organise`,
deciding replacements from the collision classification in
`_movieFileCollisionOutcome` in `organiseMyVideo/videoRescan.py`.

Route every copy, publish and quarantine through
`organiseMyVideo/filesystemOperations.py`, following
[ADR-003](../../adr/003-filesystemSafetyBoundary.md). Probe files through
`organiseMediaStudio`, following
[ADR-010](../../adr/010-sharedMediaProcessingBoundary.md). Do not delete the
replaced file, change `movie.xml` or artwork, or replace anything without
`--replace`.

Update CLI help and `documentation/commandLineInterface.md`, and add regression
tests using temporary trees and a stubbed probe. Verify with `python -m pytest`
and `manageProject --check`. Hand off with evidence for each acceptance
criterion, including a dry-run plan from a real staging folder. Any confirmed run
on real media needs the user's approval.
