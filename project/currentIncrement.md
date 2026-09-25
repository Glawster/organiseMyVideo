# Current increment

## Objective

Resolve pytest failures on `integrate/camera-foundation` following the camera
CLI and shared media primitive integration.

## Scope

- Declare the existing shared media dependency in authoritative package metadata.
- Restore source-option aliases for media organise/clean, library rescan and
  torrent maintain, with explicit options taking precedence over positional input.
- Update config isolation and card-label permission regression tests for the
  current CLI and database-only inventory fallback.

## Status

Complete. All 602 tests pass with `python -m pytest -q` in the active
`mediaStudio` Conda environment.

## Verification

- Full suite: 602 passed.
- `git diff --check`: passed.
- Black check found existing formatting differences in the touched Python files;
  unrelated formatting was left unchanged.
- The shell's bare `pytest` resolves to a system-Python launcher, which lacks
  `organiseMediaStudio`. Use `python -m pytest` to select the active environment.

## Immediate next action

Review the branch changes. No further pytest fixes remain in this increment.
