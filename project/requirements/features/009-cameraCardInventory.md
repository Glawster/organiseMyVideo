# 009: Camera card inventory

## Status

In progress — baseline inventory completed; full filename snapshot extension pending.

## Outcome

As a media-library operator, I need to assign a numeric ID to a mounted camera
SD card and record an inventory of that card so that I can later recall the
card's date range, capacity, general content, and complete file listing without
importing or altering the media.

## Context

Physical GoPro and DJI cards are reused. After a card is copied or set aside,
the operator still needs to know which numbered card holds which outing. A
numbered card therefore has a durable physical identity (`cardId`) but may have
many different contents over its lifetime.

Each confirmed inventory run represents one observed state of that physical
card. It must receive its own durable `snapshotId`. Re-inventorying card 6 after
reuse creates a new snapshot rather than replacing the previous one. Earlier
snapshots and their complete file lists remain historical evidence.

The existing camera-import plan in [REQ-004](004-cameraMediaImport.md) copies
originals into the archive. Import evidence can be linked back to a particular
card and inventory snapshot so the application can later determine whether the
contents observed in that snapshot were completely archived and verified.

GoPro cards expose `.THM` JPEG thumbnails beside video files. Those thumbnails,
and still images when thumbnails are absent, are enough for a vision model to
summarise what the card contains without reading full movies.

The inventory must also support later discovery of arbitrary files on removable
media. A card may contain software packages, documents, archives, or other
non-camera content, so inventory must retain the complete relative filename/path
set rather than only camera-media counts.

Application state already belongs under the XDG local-state directory used by
`organiseMyProjects.logUtils`. The inventory database lives in that local/state
folder rather than beside the media archive.

## Identity model

- `cardId` identifies the physical numbered card across its entire lifetime.
- `snapshotId` identifies one confirmed inventory observation of that card.
- Relative paths identify files within that snapshot; they are not durable card
  identity by themselves.
- A mount path such as `/media/andy/XXXX-XXXX` is temporary runtime context and
  must never be used as card identity or as the key for archive/lifecycle state.
- Reusing a card creates a new snapshot under the same `cardId`.
- The latest confirmed snapshot describes the card's current known contents;
  older snapshots remain queryable for history and audit.

## Scope

- Provide card scanning, capture-date ranging, volume sizing, complete filename
  inventory, thumbnail sampling, and SQLite persistence as importable Python
  services.
- Add `python -m organiseMyVideo camera inventory -s SOURCE --card ID` as the
  canonical scan-and-record action.
- Require an explicit `-s/--source` for canonical inventory scans.
- Accept a card root, `DCIM` directory, or supported camera media directory.
- Require a positive integer card ID supplied by the operator or discovered
  from the existing numbered card label according to the card-ID requirement.
- Assign a durable unique `snapshotId` to every persisted inventory snapshot.
- Record date range, volume capacity, used and content size, camera kinds,
  file counts, and a content summary.
- Record a complete per-snapshot inventory of relative file paths/names for all
  files present at scan time, including non-camera files such as installers,
  packages, documents, and archives.
- Persist the raw file list as observed. Ignore/filter/presentation rules for
  unwanted filenames may evolve without changing the underlying snapshot
  evidence.
- Preserve historical file inventories with their parent snapshot so later
  scans do not overwrite the evidence of what was present previously.
- Expose both `cardId` and `snapshotId` to sibling services such as camera import
  and removable-media lifecycle derivation.
- Derive the content summary from `.THM` thumbnails when present, otherwise
  from JPEG stills, using xAI image understanding.
- Keep dry-run as the default; require `--confirm` to write SQLite or call the
  vision API.
- Store SQLite under the application local-state directory
  (`$XDG_STATE_HOME/organiseMyVideo`, defaulting to
  `~/.local/state/organiseMyVideo`).
- Keep module, function, test, documentation, and SQLite identifiers in
  camelCase.

## Out of scope

- Copying, moving, deleting, formatting, or ejecting card media.
- Joining, transcoding, or playing camera files.
- Importing cards into the GoPro or Drone archive (REQ-004).
- Migrating existing archive directories (REQ-004).
- Using the transient Linux mount path as durable card identity.
- Defining filename suppression/filtering policy beyond preserving the complete
  underlying file inventory.
- A graphical card browser.

## Acceptance criteria

1. Given a mounted card or copied card directory and a positive integer
   `--card` value, when `camera inventory -s SOURCE --card ID` runs in dry-run,
   then it reports date range, volume size, file counts, and sampled thumbnail
   count without writing SQLite or calling the vision API.
2. Given `--confirm` and a valid source, when inventory runs, then a new
   snapshot for that card ID is written to SQLite under the application
   local-state directory and receives a durable unique `snapshotId`.
3. Given the same card ID is inventoried again with `--confirm`, when the latest
   snapshot is queried, then a new `snapshotId` is created and earlier snapshots
   and their file inventories remain stored unchanged.
4. Given a confirmed inventory scan, when files exist anywhere beneath the
   selected card/source root, then every discovered file is recorded in the
   snapshot using a relative path so the original directory structure can be
   reconstructed for display/search purposes.
5. Given non-camera files such as software packages, documents, archives, or
   miscellaneous data, when inventory runs, then those filenames are retained
   in the full snapshot instead of being omitted merely because they are not
   camera media.
6. Given JPEG EXIF or MP4 creation time is present, when scanning runs, then
   the date range uses that capture metadata; when it is absent, filesystem
   modification time is used and reported as the fallback.
7. Given GoPro `.THM` files exist, when `--confirm` inventory runs with a
   vision client, then sampled thumbnails are described and a card-level
   content summary is stored.
8. Given no `.THM` files but JPEG stills exist, when confirmed inventory
   runs, then stills are sampled instead of thumbnails.
9. Given no API key and no injected vision client, when confirmed inventory
   runs, then file metadata is still stored and the missing content summary is
   reported without aborting the scan.
10. Given `--card` is missing, zero, or negative and no valid on-card identity
    can be resolved, when the command is validated, then it exits non-zero
    before persisting a snapshot.
11. Given canonical `camera inventory` is invoked without `-s/--source`, then
    argument parsing fails before scanning.
12. Given a card is reused and inventoried again, then the latest snapshot is
    treated as the current known contents while prior snapshots remain
    addressable by `snapshotId` for archive reconciliation and history.
13. Given an inventory source is mounted at different Linux paths on different
    runs, then those mount paths do not change or replace the card's `cardId` or
    any historical `snapshotId`.
14. Given `python -m organiseMyVideo --help` and `camera --help`, when help is
    displayed, then the camera object and inventory action are discoverable.
15. Given the application service is used directly, when it scans or persists,
    then it does not depend on argparse or console output.
16. Given dry-run, when inventory runs, then the source card is not modified.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md) — sibling workflow;
  import may consume `cardId`/`snapshotId` evidence but inventory does not copy
  media.
- [REQ-020: Removable media discovery and lifecycle](020-removableMediaDiscovery.md)
  consumes historical snapshots and their filename inventories to derive the
  current card state.
- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-006: Camera import architecture](../../adr/006-cameraImportArchitecture.md)
- [ADR-007: Persist camera-card inventory in SQLite](../../adr/007-cameraInventoryPersistence.md)

## Verification

- Unit tests for JPEG EXIF and MP4 capture-time readers using synthetic
  fixtures.
- Service tests for scan, dry-run immutability, confirmed SQLite snapshots,
  card ID validation, unique snapshot IDs, complete relative file inventory,
  historical snapshots, card reuse, non-camera filenames, and injected vision
  descriptions.
- Tests proving changing the temporary mount path does not change card or
  snapshot identity.
- CLI tests through `python -m organiseMyVideo camera inventory -s SOURCE`.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/cameraInventory.py`,
  `organiseMyVideo/cameraMetadata.py`
- Tests: `tests/test_cameraInventory.py`, `tests/test_cameraMetadata.py`,
  `tests/test_cli.py`
- Documentation: `documentation/cameraInventory.md`,
  `documentation/commandLineInterface.md`, `README.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-04: created — operator-requested numeric SD-card inventory with
  SQLite local-state storage and thumbnail vision summaries.
- 2026-09-04: completed — `camera inventory` scans numbered cards, persists
  camelCase SQLite snapshots under local state, and summarises sampled
  thumbnails through injectable xAI vision.
- 2026-09-12: reopened for extension — inventory now also requires a complete
  persisted relative filename/path snapshot for every card scan, with filtering
  policy intentionally deferred.
- 2026-09-12: clarified identity/history model — `cardId` identifies the
  physical card, each confirmed inventory receives a durable `snapshotId`, card
  reuse creates a new snapshot, and transient mount paths are not identity.
