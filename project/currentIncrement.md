# Current increment

## Requirement

[REQ-026: SLR card import](requirements/features/026-slrCardImport.md)
on `feature/026-slr-card-import`, extending
[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md)
and [REQ-009: Camera card inventory](requirements/features/009-cameraCardInventory.md).

## Objective

Import mixed Canon SLR cards by media type: CR3/JPEG photographs to the photo
root and SLR MP4 clips to the home-video root, both under numeric
`By Date/YYYY/MM/DD`, without weakening camera-import safety or identity.

## Scope for this increment

- Detect Canon-style `DCIM/100CANON` trees and `IMG_`/`MVI_` archive media.
- Support `.CR3` and `.JPG/.JPEG` as photographs and SLR `.MP4` as video.
- Route per asset, not per card, preserving original filenames and RAW/JPEG pairs.
- Use two-digit numeric month folders (`MM`), not `MM-MMM`.
- Prefer embedded capture metadata and report fallback-date provenance.
- Ignore Canon control/catalogue files such as `CANONMSC/*.CTG` and `comstate.to3`.
- Treat identical destination content as already present; same-name/different
  content is a conflict with no invented filename.
- Leave the source card unchanged.
- Preserve `cardId`, `snapshotId`, `importId`, manifest, and verification behaviour.
- Include CR3/JPEG/MP4 counts and capture-date range in scan/inventory/import summaries.
- Show visible progress during confirmed large-card import.

## Status

Completed — mixed SLR detection, planning, confirmed import, inventory counts,
progress output, and synthetic `DCIM/100CANON` tests are in place. GoPro, DJI,
and dash-cam archives continue to use their existing `YYYY/MM-MMM/DD` layout;
REQ-025 remains the dedicated numeric-month normalisation for those trees.

## Verification

Run:

- `pytest tests/test_cameraSlrImport.py tests/test_cameraMetadata.py tests/test_cameraPlan.py tests/test_cameraImport.py tests/test_cameraInventory.py tests/test_cli.py`
- `pytest`
- `git diff --check`

Do not use a real mounted SLR card in automated tests.
