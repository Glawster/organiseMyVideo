# Current increment

## Requirement

[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md)
on `feature/camera-media-import`, with supporting changes in
[REQ-009: Camera card inventory](requirements/features/009-cameraCardInventory.md).

## Objective

Deliver the next REQ-004 increment: propagate durable numbered-card identity and
inventory-snapshot history through camera import so verified archive evidence
can be attributed to the exact observed contents of a reused physical card.

## Scope for this increment

- Preserve the completed planner/import/CLI behaviour from acceptance criteria
  1-12.
- Resolve `cardId` from the existing `organiseMyVideo.NNN` label on the card.
- Treat source/mount paths as transient runtime context only; do not use them as
  durable card identity or lifecycle keys.
- Extend confirmed inventory persistence so every saved card observation has a
  durable unique `snapshotId` while retaining prior snapshots for the same
  `cardId`.
- Carry `cardId` through camera import planning/results.
- Link confirmed imports to the latest applicable inventory `snapshotId` when
  that relationship can be established.
- Assign a durable `importId` to each confirmed import run.
- Reconcile imported files to snapshot files by relative path plus verification
  evidence such as size/digest rather than mount path.
- Allow unidentified dry-run inspection but clearly report that it is not tied
  to a known card.
- Reject confirmed import from a numbered removable source when `cardId` cannot
  be resolved, before archive mutation.
- Ensure a fully archived old snapshot for card 6 does not make a later reused
  snapshot for card 6 appear archived.
- Keep historical inventory/import relationships queryable for later REQ-020
  lifecycle and `camera show --history` work.

## Identity model

```text
cardId      = physical numbered card
snapshotId  = one confirmed observed state of that card
relativePath = file location within that snapshot
importId    = one confirmed import run
```

The latest confirmed inventory snapshot is the current known contents. Earlier
snapshots and their import evidence remain immutable history.

## Status

Planned — requirements, prompts, and ADR clarified on 2026-09-12; implementation
has not yet started.

## Verification

Run:

- `pytest tests/test_cameraInventory.py tests/test_cameraPlan.py tests/test_cameraImport.py tests/test_cli.py`
- `pytest`
- `black --check .`
- `./tests/runLinter.py`
- `./tests/runLinter.py --markup`
- `manageProject --check`
- `git diff --check`

Add focused tests for card reuse, changing mount paths, unique snapshot IDs,
unidentified dry-run vs confirmed import, import-to-snapshot linkage, and
current-state derivation from the latest snapshot only.

Do not fix unrelated pre-existing repository lint findings as part of REQ-004.

## Deferred to later REQ-004 increments

Archive migration, rollback-plan evidence, and empty-directory cleanup remain
within REQ-004 but are outside this card/snapshot identity slice.
