# ADR-009: Numbered removable volumes share one inventory

## Status

Accepted — 2026-09-04

## Context

Camera SD cards already use a numeric ID, `organiseMyVideo.NNN` on the
volume, and `cardInventory` snapshots with sold size and free space. USB
thumb drives need the same “what is on this stick” record. A second
database or ID sequence would split the UI list the operator uses to find
things.

## Options considered

1. Keep inventory camera-only; catalogue USB drives some other way.
2. Add a separate `usbInventory` table and ID space.
3. Treat every removable volume as one numbered inventory: camera SD cards
   set `volumeKind` to `sd`, USB storage sets
   `volumeKind` to `usb`, same `--card` labels and catalogue list.

## Decision

Use option 3. `camera inventory` remains the command. USB mounts without
GoPro, DJI, or dash-cam layouts are `usb`. Card IDs stay one positive
integer sequence. The UI list is still `catalogueCardsList()`, showing
sold size and free space for both.

Vision summaries stay optional. USB backups are described from top-level
folder names and file-type counts unless JPEGs are present and confirm
authorizes sampling.

## Rationale

The operator’s question is “what is where”, not “is this an SD card”. Size
and free space are already the UI fields. Reusing the on-volume label
avoids a second identity scheme. Import stays camera-only (REQ-004).

REQ-016 prepares the schema with `sd` as the backward-compatible default.
Camera families remain in `cameraKinds`; USB detection and inventory belong
to REQ-015.

## Consequences

- `cardInventory` may store non-camera volumes; `volumeKind` distinguishes
  them.
- `camera import` must still refuse USB storage trees that are not camera
  layouts.
- Tests need a non-camera USB fixture as well as GoPro/DJI/dash-cam trees.

## Related requirements

- [REQ-009: Camera card inventory](../requirements/features/009-cameraCardInventory.md)
- [REQ-015: USB volume inventory](../requirements/features/015-usbVolumeInventory.md)
