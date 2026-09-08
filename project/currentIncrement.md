# Current increment

## Requirement

[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md)
on `feature/camera-media-import`.

## Objective

Deliver the first REQ-004 increment: a typed, non-mutating camera import planner
that detects supported GoPro, DJI and dash-cam content, reads capture dates with
documented fallback, assigns archive destinations, handles companions and ignored
content, and classifies duplicates and conflicts without changing source,
destination, application state or manifest storage.

## Scope for this increment

- Acceptance criteria 1-7.
- Reuse the existing pure-Python camera metadata readers.
- Accept card roots, DCIM directories and individual supported camera directories.
- Preserve original filenames and plan GoPro, Drone and Dashcam `YYYY/MM/DD`
  destinations.
- Exclude GoPro LRV/THM helpers unless explicitly included.
- Keep DJI same-stem SRT companions with their MP4.
- Report unknown or date-ambiguous content rather than importing it.
- Classify an existing identical destination as already present and a same-name,
  different-content destination as a conflict.
- No filesystem mutation, manifest writes, CLI adapter or confirmed import yet.

## Status

In progress — planner implementation and production-path tests are next.

## Verification

Run:

- `pytest`
- `black --check .`
- `./tests/runLinter.py`
- `./tests/runLinter.py --markup`
- `git diff --check`

Do not fix unrelated pre-existing repository lint findings as part of REQ-004.

## Deferred to later REQ-004 increments

Confirmed copy/verification, atomic finalisation, import manifests, CLI wiring,
archive migration, rollback-plan evidence and empty-directory cleanup remain
within REQ-004 but are outside this first planner slice.
