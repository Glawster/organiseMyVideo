# ADR-006: Implement camera workflows as Python services with subcommand adapters

## Status

Accepted — 2026-09-02

## Context

Camera ingestion needs metadata extraction, asset grouping, duplicate analysis,
safe copying, verification, and audit manifests. The behaviour must be usable
both by operators and by future Python application layers. Depending on locally
installed media executables would make installation and testing less
reproducible, while embedding the workflow in `__main__.py` would couple domain
logic to argparse and console output.

The existing packaged entry point is `python -m organiseMyVideo`, and the CLI
direction is toward discoverable object/action subcommands. Existing archives
contain a mixture of GoPro date-named directories and flat DJI storage, while
new camera media needs one consistent on-disk date hierarchy.

## Options considered

1. Implement the import workflow directly in `__main__.py` and call ExifTool or
   ffprobe for metadata.
2. Implement importable Python services with a thin `camera import` adapter and
   use Python metadata readers.
3. Implement a separate shell script outside the package.

## Decision

Use option 2. Camera-domain behaviour lives in importable, typed Python modules
and does not depend on argparse, console output, shell commands, ExifTool, or
ffprobe. The CLI exposes that behaviour through
`python -m organiseMyVideo camera import SOURCE` and
`python -m organiseMyVideo camera migrate`.

New GoPro and DJI originals use nested `YYYY/MM/DD` directories beneath their
respective archive roots. Camera ingestion copies and verifies source files; it
does not move or delete card content. Existing archive content is migrated only
through the separate `camera migrate` action, which plans by default and moves
verified, conflict-free assets only with `--confirm`.

## Rationale

One application service can support the CLI, automated tests, and future GUI or
batch integrations. A Python-only runtime is reproducible and allows metadata
and failure behaviour to be tested with controlled fixtures. A dedicated
subcommand prevents camera filenames from entering movie/TV classification.

## Consequences

- Python dependencies or a focused internal parser must cover required JPEG
  EXIF and MP4 creation-time metadata.
- `__main__.py` remains an adapter and must not own import rules.
- Direct service tests and production-path CLI tests are both required.
- Existing GoPro and Drone media will be reorganised by a separate migration
  application service and CLI action within REQ-004.
- Ambiguous, unrelated, and conflicting legacy files remain untouched for
  manual review.
- Filesystem mutations must conform to the central safety boundary described
  by ADR-003.

## Related requirements

- [REQ-004: Camera media import](../requirements/features/004-cameraMediaImport.md)
- [REQ-009: Camera card inventory](../requirements/features/009-cameraCardInventory.md)
