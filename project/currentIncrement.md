# Current increment

## Objective and status

REQ-036 incoming media preparation is complete. Clean operates inside its
selected staging source, scan is observational even with compatibility
confirmation, and organise reuses canonical library repair. The requirement
record and index agree on Completed.

## Accepted scope and evidence

- `incomingNameNormalise` supplies pure release-prefix cleanup to clean and
  movie/TV parsing. Metadata precedes the feature filename, then the cleaned
  parent. Real filename and parent-fallback fixtures retain their source paths.
- Clean no longer invokes library show/season normalisation or reconciliation.
  Real temporary-tree tests cover quarantine, sample-only/empty cleanup, source
  aliases, configured defaults, symlinks and escaped candidates. Retained
  quarantine stays inside the source and is excluded from later cleanup.
- All CLI scan aliases force an observational organizer. A real CLI pipeline
  parses sidecars, plans collisions and writes a summary while media and
  sidecar paths and bytes remain unchanged with `--confirm`.
- Samples and release markers are ancillary; multipart destinations retain
  their part suffix. Existing title/year identity guards remain active.
- Canonical titles retain valid punctuation, use a readable pipe separator and
  title-style casing for all-uppercase metadata, and preserve existing capitals.
- Existing grouped summaries, conflict locations and investigation categories
  remain in application state. Daily append naming is preserved.

| Production behaviour | Unit | Integration | Golden | UI | Resolution | Clean-room |
| --- | --- | --- | --- | --- | --- | --- |
| Incoming preparation and source boundary | Yes | Yes | Yes | N/A | N/A | Yes |
| Candidate classification and collision planning | Yes | Yes | Yes | N/A | N/A | Yes |
| Confirmed scan observation and summaries | Yes | Yes | Yes | N/A | N/A | Yes |

## Final verification

Verified in the mediaStudio Conda environment:

- Full pytest: 842 passed, including 22 new incoming-preparation cases.
- `runLinter`: no findings across application and tests.
- `runLinter --markup`: no remaining issues.
- `manageProject --check`: zero failures and zero warnings.
- Black applied to changed Python files.
- Working-tree, staged and combined diff checks passed.

## Remaining work and immediate next action

No REQ-036 implementation or verification remains. Review the feature branch.
REQ-030 unique per-invocation summaries remain separate. Direct legacy repair
methods remain reusable for organise; CLI scan invokes them only in observation
mode. Conflict overrides and duplicate review decisions remain separate work.
