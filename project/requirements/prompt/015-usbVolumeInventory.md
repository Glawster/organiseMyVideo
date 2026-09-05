# Requirement: 015 — project/requirements/features/015-usbVolumeInventory.md

Role: implement and verify

Read the requirement, REQ-009, ADR-009, and the camera inventory guide.
Extend `camera inventory` so a volume without camera layout is stored as
`volumeKind` `usb` with the same numeric ID file, sold size, and free
space. Do not copy USB media. Do not run camera import.

Keep names in camelCase. Verify with `pytest` and `git diff --check`.
