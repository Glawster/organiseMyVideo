# 030: Operational run audit

## Status

ToDo

## Outcome

As a media-library operator, I need destructive cleanup to leave explicit verification evidence and each processing run to retain its own summary report so that completed operations can be audited without mixing evidence from separate runs.

## Context

Two operational audit gaps have been identified.

First, `media organise --merge` may remove a source folder after its useful contents have been safely merged elsewhere. The deletion is currently an important destructive step, so the log should contain a post-operation filesystem check proving whether the source directory is actually absent rather than relying only on the successful return of the delete operation.

Second, summary reports currently use a date-only path such as:

```text
~/.local/state/organiseMyVideo/summary.20260925.txt
```

The current report writer appends subsequent summaries to an existing report. This combines separate executions into one daily file. A summary should instead represent one invocation so it can be correlated directly with that run's log and actions.

## Scope

### Post-delete verification for folder merges

- After a confirmed folder merge removes a source directory because it is no longer useful, perform a read-only filesystem existence check for that exact path.
- Record the verification check and its result in the normal application log.
- Successful verification must explicitly show that the deleted directory is no longer present.
- If the directory still exists unexpectedly, record that as a warning or error rather than reporting deletion as verified.
- The verification itself must not make further filesystem changes.
- Dry-run merge must not perform or report a real post-delete verification because no deletion has taken place.
- Apply this initially to source-folder deletion performed by `media organise --merge`; the verification primitive should be reusable by other destructive cleanup workflows.

Illustrative log output may be equivalent to:

```text
filesystem check - /mnt/video1/TV/Example - not found - deletion confirmed
```

The exact logging format may follow the established logger conventions, but the checked path and verification result must be clear.

### One summary report per run

- Every invocation that produces a summary report must create a distinct summary file.
- Do not append a new run's summary to a summary created by an earlier run.
- Do not overwrite an earlier run's summary.
- Include sufficient run-time identity in the filename to keep multiple summaries from the same day distinct and naturally sortable.
- Prefer a timestamp-based filename such as:

```text
summary.20260925-190759.txt
summary.20260925-203412.txt
```

- If two runs can begin within the filename's timestamp resolution, resolve the collision without overwriting or appending to the existing file, for example by adding a deterministic incrementing suffix.
- Continue logging the actual summary-report path so the run log can be correlated with its summary.
- Each summary file contains only the summary for the invocation that created it.
- Summary files are application-state artifacts and belong under
  `~/.local/state/organiseMyVideo/` (or `XDG_STATE_HOME`), not under `.config`.
- Rename entries should group a movie folder rename with its corresponding
  feature-file rename and use aligned `folder` / `movie` / `to` labels.
- End each summary with `Needs further investigation`, containing unresolved
  identity conflicts, same-identity merge candidates, possible duplicate feature
  files and other unresolved collisions.
- Identity-conflict investigation entries must include the affected folder path
  as well as current/proposed identity and available evidence.

## Out of scope

- Running a full filesystem repair utility such as `fsck` after a folder deletion. The required check is a filesystem/path existence verification, not a block-device integrity scan.
- Deleting additional content when post-delete verification fails.
- Combining historical daily summary files into the new per-run format.
- Historical summary files already written in the old location are not migrated automatically.

## Acceptance criteria

1. Given a confirmed `media organise --merge` successfully removes an empty obsolete source folder, when deletion completes, then the application checks that exact path and records in the log that the path is absent and deletion is verified.
2. Given a merge attempts source-folder deletion but the path still exists afterwards, when verification runs, then the log clearly records that deletion was not verified and does not falsely report success.
3. Given a dry-run merge, when source-folder cleanup is planned, then no filesystem deletion or real post-delete verification is performed.
4. Given two summary-producing invocations on the same date, when both complete, then each has a different summary-report pathname and both files remain available.
5. Given a summary file already exists for an earlier run, when another run produces a summary, then the earlier file is neither appended to nor overwritten.
6. Given a summary-producing invocation, when its summary is written, then the application log records the exact path of that invocation's summary file.
7. Given multiple summary files, their filenames sort in run-time order under normal chronological operation.
8. Tests cover successful post-delete verification, failed verification, dry-run behaviour, multiple summaries on one day, filename collision handling, and preservation of previous summary files.
9. New summaries are written under the application state directory, not the configuration directory.
10. Rename output groups related folder/file changes and aligns labels for readability.
11. Unresolved scan findings are repeated in a final `Needs further investigation` section.
12. Movie identity-conflict entries in that section include the affected folder path.

## Dependencies and decisions

- [REQ-007: Central filesystem safety](007-filesystemSafety.md)
- [REQ-017: Merge duplicate TV and movie folders](017-mergeDuplicateTvFolders.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)

Post-delete verification is deliberately read-only and should occur after the established filesystem-safety boundary has completed the destructive operation.

Summary files are application-state artifacts. Their uniqueness is a run-audit concern and does not change the dry-run rules governing media-library mutations.

## Verification

- Unit tests using temporary directories for confirmed deletion and failed deletion verification.
- Dry-run test proving no false deletion verification is emitted.
- Summary-path tests with multiple runs on the same date.
- Tests proving existing summary files remain byte-for-byte unchanged after later runs.
- Filename collision test.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-27: created — require logged post-delete verification after folder merges and one uniquely named summary report per invocation.

- 2026-10-02: extended summary requirements with XDG state location, grouped
  rename layout and an actionable `Needs further investigation` section.
