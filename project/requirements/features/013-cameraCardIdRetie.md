# 013: Camera card ID reassign

## Status

Completed

## Outcome

As a media-library operator, I need an explicit confirmed action to change
the numeric ID bound to an SD card so that a mis-labelled card can be
corrected without silently overwriting the on-card file.

## Context

REQ-012 refuses a `--card` that disagrees with `organiseMyVideo.NNN`. That
is the safe default. Operators still need a deliberate way to change the ID
when the handwritten number or first bind was wrong.

## Scope

- Add `--reassign` to `camera inventory`.
- Require SOURCE and `--card` with the new ID.
- Overwrite the on-card label only with `--confirm`.
- Keep earlier SQLite snapshots under the old ID.

## Out of scope

- Rewriting or deleting historical snapshots for the old ID.
- Changing the handwritten sticker.

## Acceptance criteria

1. Given a card labelled 1, when inventory runs with `--card 5` and no
   `--reassign`, then it fails and the label is unchanged.
2. Given a card labelled 1, when inventory runs with `--card 5 --reassign`
   without `--confirm`, then the label stays 1.
3. Given a card labelled 1, when inventory runs with `--card 5 --reassign
   --confirm`, then the label becomes 5 and a new snapshot is stored for ID 5.
4. Given `--reassign` without `--card` or without SOURCE, when parsing runs,
   then it exits non-zero.

## Dependencies and decisions

- [REQ-012: Camera card ID file](012-cameraCardIdFile.md)

## Verification

- `pytest`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/cameraInventory.py`,
  `organiseMyVideo/__main__.py`
- Tests: `tests/test_cameraInventory.py`, `tests/test_cli.py`
- Documentation: `documentation/cameraInventory.md`

## Change history

- 2026-09-04: created and completed — operator asked how to change a card ID.
- 2026-09-04: changed — CLI flag renamed from `--retie` to `--reassign`.
