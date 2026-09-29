# Implement REQ-033: Camera folder capture-time correction

## Requirement

Implement [REQ-033](../features/033-cameraFolderCaptureCorrection.md), following
repository instructions and the REQ-024 correction architecture. This prompt
assigns all acceptance criteria; the requirement defines the contract.

## Boundaries

Add a read-only folder evidence adapter and reuse correction planning, journal,
execution and metadata primitives. Support the public `--source` alternative,
separate source/destination roots, stable confirmed scope and safe retries.
Preserve import history rather than synthesising import records. Keep domain
logic separate from presentation. Do not implement REQ-032 Tab completion here.

## Verification and handoff

Use real temporary JPEG/MP4 fixtures, CLI dispatch, SQLite and filesystem
operations. Cover preview, confirmation, companions, subsets, missing evidence,
conflicts, new/changed content, retry/interruption and subsequent organisation.
Run full relevant tests and repository checks; update user documentation and
ADR-011, and report results, limitations and any pre-existing check failures.

## Correction CLI contract

The correction interface uses `-s/--source`, `-r/--root`, `-R/--reference`,
`-a/--actual`, repeatable `-f/--file`, `--reason` and `--import-manifest`.
Exactly one scope selector is required. Keep `--reason` explicit and required
for the correction audit record. Reject obsolete `--reference-file` and
`--actual-at` options; they are not aliases.

Help describes `-R, --reference FILE` as “file whose recorded capture time
provides the correction anchor” and `-a, --actual DATETIME` as “actual capture
date/time of the reference file”. Existing preview and confirmation rules apply.

## Subsequent corrections

Apply REQ-024's repeatable-transformation contract: completed journals never
reserve a folder or media path. Read current evidence for a new operation,
preserve completed audit records, and retain frozen evidence only for unfinished
recovery. Test a second correction, same-path publication, reused source folders
and an interrupted second operation in addition to the existing acceptance work.
