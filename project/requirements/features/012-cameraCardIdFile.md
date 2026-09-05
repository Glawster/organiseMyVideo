# 012: Camera card ID file

## Status

Completed

## Outcome

As a media-library operator, I need a confirmed card inventory to write a
small ID file onto the SD card so that later scans can verify the numeric
card ID from the volume itself rather than relying only on a handwritten
label.

## Context

Physical cards already have a number written on them. REQ-009 stores that
number in SQLite when `--card` is supplied. If the operator passes the wrong
`--card` later, snapshots are attributed to the wrong identity. A file on the
card is a second, machine-readable binding.

The only card mutation allowed is this ID file, and only with `--confirm`.
Media files are still never copied, moved, or deleted by inventory.

## Scope

- Write `organiseMyVideo.NNN` at the card volume root on confirmed
  `camera inventory`, where `NNN` is the zero-padded card ID.
- Record the numeric `cardId` and the latest card summary, including free
  space, in JSON inside that file.
- Read the file on later scans; use it when `--card` is omitted.
- Refuse a labelled card bound to a different `--card` unless `--reassign`
  is given.
- Keep dry-run from writing the file.
- Ignore the ID file when counting card media.

## Out of scope

- Formatting, ejecting, or deleting other files on the card.
- Encrypting or hiding the ID file.
- Changing the handwritten physical label.

## Acceptance criteria

1. Given `--confirm` and `--card 1`, when inventory runs, then
   `organiseMyVideo.001` is written at the card root with that card ID and a
   summary that includes free space.
2. Given dry-run, when inventory runs, then the ID file is not created or
   changed.
3. Given a card that already has the ID file, when inventory runs without
   `--card`, then the stored ID is used.
4. Given a card whose ID file says 1, when inventory runs with `--card 2`,
   then the command fails and neither SQLite nor the ID file is changed.
5. Given a first scan with no ID file and no `--card`, when inventory runs,
   then it fails and asks for `--card`.
6. Given the ID file is present, when the card is scanned, then that file is
   not counted as camera media.

## Dependencies and decisions

- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-007: Persist camera-card inventory in SQLite](../../adr/007-cameraInventoryPersistence.md)

## Verification

- Service tests with temporary card trees.
- CLI tests for missing `--card`, matching file, and mismatched file.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/cameraInventory.py`
- Tests: `tests/test_cameraInventory.py`, `tests/test_cli.py`
- Documentation: `documentation/cameraInventory.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-04: created — operator asked to bind the numeric card ID onto the
  SD card itself.
- 2026-09-04: completed — confirmed inventory writes organiseMyVideo.cardId;
  later scans read it; mismatched --card is refused.
- 2026-09-04: changed — label file is `organiseMyVideo.001` and stores the
  card summary including free space. A legacy `organiseMyVideo.cardId` file
  is still read.
