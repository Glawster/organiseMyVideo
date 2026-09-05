# 011: Dash cam card support

## Status

Completed

## Outcome

As a media-library operator, I need dash-cam SD cards inventoried with the
same numeric card-ID routine as GoPro and DJI so that driving footage is
catalogued by date range, size, and camera kind.

## Context

REQ-009 catalogues GoPro and DJI cards. A third removable source is a dash
cam. Layouts vary by vendor (Viofo `DCIM/Movie`, BlackVue `Record`, Garmin
`DCIM/100EVENT`, Nextbase dated `YYMMDD_HHMMSS_*` names, Transcend DrivePro
`N-Video` / `P-Video` / `EVENT`) but they are still numbered physical cards
the operator wants in the same SQLite snapshots.

Import of dash-cam originals into a dated archive is part of still-open
REQ-004 and is planned beside GoPro/DJI, not delivered by this requirement.

## Scope

- Detect common dash-cam directories and filename patterns during
  `camera inventory`.
- Record `dashcam` as a camera kind alongside `gopro` and `dji`.
- Derive capture time from dash-cam filenames when embedded metadata is
  missing.
- Sample JPEG stills for vision summaries when `.THM` files are absent.
- Document dash-cam archive destination `Dashcam/YYYY/MM/DD/` for REQ-004.

## Out of scope

- Vendor-specific GPS, g-sensor, or proprietary viewer databases.
- Transcoding, joining front/rear channels, or map playback.
- Implementing `camera import` for dash cam in this increment.

## Acceptance criteria

1. Given a Viofo-style `DCIM/Movie` tree or BlackVue-style dated
   `YYYYMMDD_HHMMSS_NF.mp4` files, when inventory scans, then files are
   classified as `dashcam` and not as GoPro or DJI.
2. Given dash-cam filenames that encode date and time, when embedded MP4
   creation time is absent, then the card date range uses the filename
   timestamp.
3. Given Garmin-style `DCIM/100EVENT` directories, when inventory scans, then
   contained videos are classified as `dashcam`.
4. Given a GoPro `100GOPRO` tree, when inventory scans, then behaviour is
   unchanged and files are not classified as dash cam.
5. Given `--confirm` inventory of a dash-cam card, when it persists, then the
   snapshot's `cameraKinds` includes `dashcam`.
6. Given a Transcend DrivePro 250 card at `DP250/N_VIDEO` with files named
   `YYYY_MMDD_HHMMSS_sequence.mp4`, when inventory scans, then those files
   are `dashcam`, the date range uses the filename timestamp, and `SYSTEM`
   is ignored.

## Dependencies and decisions

- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [ADR-006: Camera import architecture](../../adr/006-cameraImportArchitecture.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)

## Verification

- Synthetic Viofo, BlackVue, Garmin, Transcend DrivePro, and GoPro fixtures.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/cameraInventory.py`,
  `organiseMyVideo/cameraMetadata.py`
- Tests: `tests/test_cameraInventory.py`, `tests/test_cameraMetadata.py`
- Documentation: `documentation/cameraInventory.md`,
  `documentation/cameraImport.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-04: created — operator asked to add dash-cam cards to the GoPro
  inventory routine.
- 2026-09-04: completed — Viofo, BlackVue, and Garmin layouts classify as
  `dashcam`; filename dates fill the card range.
- 2026-09-04: changed — recognise Transcend DrivePro `N-Video` / `P-Video` /
  `EVENT` cards, compact and `TS` timestamps, and `.NMEA` sidecars.
- 2026-09-04: changed — match DrivePro 250 `DP250/N_VIDEO` and
  `YYYY_MMDD_HHMMSS_sequence.mp4` names.
