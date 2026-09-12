# Current increment

## Requirement

[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md)
on `feature/camera-media-import`.

## Objective

Deliver the third REQ-004 increment: expose the existing camera import planner
and confirmed import service through the canonical `camera import` CLI while
keeping the domain behaviour in importable Python services.

## Scope for this increment

- Acceptance criteria 11-12.
- Add `camera import` beneath the existing `camera` object.
- Require canonical `-s/--source`; reject positional source syntax.
- Validate the source directory before invoking the import service.
- Reuse the completed camera import planner and confirmed-copy service from
  acceptance criteria 1-10.
- Keep dry-run as the default and `--confirm` as the only archive-write switch.
- Resolve GoPro, Drone, and Dashcam archive roots from application configuration
  with the documented archive paths as fallbacks.
- Permit explicit destination and manifest-directory overrides so tests and
  operator diagnostics never need to touch the real archive.
- Keep GoPro helper retention behind `--include-gopro-companions`.
- Print a concise import summary without parsing domain-service console output.
- Add help-discovery and thin-adapter tests.
- Add direct-service equivalence evidence proving the same operation is
  available without argparse or the CLI.

## Status

In progress — CLI adapter, public application-service wrapper, and focused tests
implemented remotely; local verification is next.

## Verification

Run:

- `pytest tests/test_cameraPlan.py tests/test_cameraImport.py tests/test_cli.py`
- `pytest`
- `black --check .`
- `./tests/runLinter.py`
- `./tests/runLinter.py --markup`
- `manageProject --check`
- `git diff --check`

Do not fix unrelated pre-existing repository lint findings as part of REQ-004.

## Deferred to later REQ-004 increments

Archive migration, rollback-plan evidence, and empty-directory cleanup
(acceptance criteria 13-18) remain within REQ-004 but are outside this CLI
adapter slice.
