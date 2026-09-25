# Current increment

## Requirement

[REQ-027: SLR card import](requirements/features/027-slrCardImport.md)
on `feature/027-slr-card-import`, extending
[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md)
and [REQ-009: Camera card inventory](requirements/features/009-cameraCardInventory.md).

## Objective

Import mixed Canon SLR cards by media type: CR3/JPEG photographs to the photo
root and SLR MP4 clips to the home-video root, both under numeric
`By Date/YYYY/MM/DD`, without weakening camera-import safety or identity.

## Scope

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

Mixed SLR detection, planning, confirmed import, inventory counts, progress output,
and synthetic `DCIM/100CANON` tests are in place. New GoPro, DJI and dash-cam
imports also use numeric `YYYY/MM/DD` paths. Regression fixes align collision,
copy-verification and history tests with that layout, restore internal import
dispatch for `camera archive`, and correct the CR3 metadata helper naming.

## Verification

- `python -m organiseMyProjects.runLinter`: all files OK.
- `python -m pytest -q`: 620 passed.
- `git diff --check`: passed.
- The bare `runLinter` launcher in this shell uses system Python without OMP
  package metadata; the module invocation uses the active Conda environment.

- `pytest tests/test_cameraSlrImport.py tests/test_cameraMetadata.py tests/test_cameraPlan.py tests/test_cameraImport.py tests/test_cameraInventory.py tests/test_cli.py`
- `pytest`
- `git diff --check`

Do not use a real mounted SLR card in automated tests.
