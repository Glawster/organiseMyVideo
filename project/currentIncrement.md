# Current increment

## Requirement

[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md)
on `feature/camera-media-import`.

## Objective

Deliver the second REQ-004 increment: execute a conflict-free camera import only
when confirmed, copy each original through the central verified filesystem
boundary, leave source media unchanged, clean up failed temporary copies, and
write an auditable JSON manifest for the confirmed run.

## Scope for this increment

- Acceptance criteria 8-10.
- Reuse the completed typed camera import planner from acceptance criteria 1-7.
- Keep dry-run fully non-mutating: no archive, state, or manifest writes.
- Reject confirmed execution when the plan contains destination conflicts.
- Copy planned media through `FilesystemOperations.copyFile`, which uses a
  sibling temporary path, verifies size and SHA-256 identity, and only then
  finalises the destination.
- Preserve the source card after successful and failed copies.
- Record already-present assets without rewriting them.
- On copy or verification failure, leave no incomplete final file and record
  the failure in the manifest.
- Write a JSON manifest for confirmed runs containing source identity, camera
  kind, source and destination paths, capture metadata, size, digest,
  companion classification, and outcome for each planned asset, plus excluded
  and unknown paths.

## Status

In progress — confirmed import service and focused tests implemented; local
verification is next.

## Verification

Run:

- `pytest tests/test_cameraPlan.py tests/test_cameraImport.py`
- `pytest`
- `black --check .`
- `./tests/runLinter.py`
- `./tests/runLinter.py --markup`
- `manageProject --check`
- `git diff --check`

Do not fix unrelated pre-existing repository lint findings as part of REQ-004.

## Deferred to later REQ-004 increments

CLI wiring and help discovery (acceptance criteria 11-12), archive migration,
rollback-plan evidence, and empty-directory cleanup (acceptance criteria 13-18)
remain within REQ-004 but are outside this confirmed-import slice.
