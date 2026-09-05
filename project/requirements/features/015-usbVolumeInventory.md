# 015: USB volume inventory

## Status

ToDo

## Outcome

As a media-library operator, I need USB thumb drives inventoried with the
same numeric volume ID, size, and free-space snapshot as camera SD cards so
that I can see what is stored on each stick, including backups.

## Context

REQ-009 catalogues camera SD cards. USB sticks are also numbered physical
volumes, but they usually hold mixed files or backups rather than `DCIM`
camera trees. The operator still wants sold size, remaining space, and a
summary of what is on the volume.

Detection already treats a path as a camera card when GoPro, DJI, or
dash-cam layouts are present. A mounted USB without those layouts is a
storage volume. Both write `organiseMyVideo.NNN` at the volume root and
append snapshots in `cardInventory`.

## Scope

- Accept a USB mount or copied USB directory in `camera inventory`.
- When no camera layout is detected, record `volumeKind` `usb`.
- Keep the same `--card` / on-volume label / `--reassign` identity rules.
- Record sold size when the volume matches a marketed USB/SD size, plus
  live `freeBytes`, `usedBytes`, and `contentBytes`.
- Summarise content from top-level folder names and file-type counts.
  Sample JPEGs for vision only when present and `--confirm` is given.
- List USB volumes through `catalogueCardsList()` (or the same UI list)
  with size and free space.
- Do not copy, move, or delete USB media except the ID file on confirm.

## Out of scope

- Treating a USB stick as a `camera import` source.
- Formatting, ejecting, or cloning backup drives.
- Inventing a second ID number space for USB vs SD cards.
- Using USB-reader vendor strings as the stick brand.

## Acceptance criteria

1. Given a mounted directory of mixed documents and videos with no camera
   layout, when `camera inventory SOURCE --card ID` runs in dry-run, then
   the snapshot `volumeKind` is `usb` and camera kinds are empty.
2. Given that volume and `--confirm`, when inventory persists, then
   `organiseMyVideo.NNN` is written and the catalogue row includes
   `cardRatedGigabytes` when the volume matches a marketed size, and
   `freeBytes`.
3. Given a GoPro `DCIM/100GOPRO` tree, when inventory scans, then behaviour
   is unchanged and `volumeKind` is not `usb`.
4. Given a USB volume whose usable size matches 32, 64, 128, or 256 GB,
   when scanned, then `cardRatedGigabytes` is that sold size.
5. Given a later scan of a labelled USB without `--card`, when the label
   is present, then the stored ID is reused.
6. Given `--confirm`, when inventory runs, then USB media files are not
   copied, moved, or deleted.
7. Given `catalogueCardsList()`, when USB and camera snapshots exist, then
   both appear with size and free space.

## Dependencies and decisions

- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-012: Camera card ID file](012-cameraCardIdFile.md)
- [ADR-007: Camera inventory persistence](../../adr/007-cameraInventoryPersistence.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)
- [ADR-009: Numbered removable volumes](../../adr/009-numberedRemovableVolumes.md)

## Verification

- Synthetic USB tree fixtures (no DCIM) and existing GoPro fixtures.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: [Camera card inventory](../../../documentation/cameraInventory.md),
  [Media catalogue](../../../documentation/mediaCatalogue.md)
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-04: created — operator asked card inventory to include USB
  thumb drives used for file storage and backup.
