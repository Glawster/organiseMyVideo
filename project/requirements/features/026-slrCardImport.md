# 026: SLR card import

## Status

Completed

## Outcome

As a media-library operator, I need SLR camera cards containing still images and video clips to be imported by media type and capture date so that photographs enter the photo archive and camera video enters the home-video archive without changing the source card.

## Context

A Canon SLR card may contain mixed camera media beneath a normal `DCIM` tree, including same-stem RAW/JPEG photograph pairs such as `IMG_0154.CR3` and `IMG_0154.JPG`, as well as camera video such as `MVI_0204.MP4`. Camera control and catalogue files may also be present and must not be archived as user media.

SLR cards are therefore mixed-media sources. The card as a whole must not be classified as either a photo card or a video card. Each supported asset is routed according to its media type while retaining common camera-card identity, inventory, import history, duplicate handling, verification, and source-preservation rules.

## Scope

- Detect supported SLR camera content beneath a card root, `DCIM` directory, or supported camera media directory.
- Support Canon CR3 RAW photographs and JPEG photographs as archive-worthy photo media.
- Support MP4 clips recorded by the SLR as archive-worthy video media.
- Route still-image assets to the configured photo root beneath `By Date/YYYY/MM/DD/`.
- Route video assets to the configured video root beneath `By Date/YYYY/MM/DD/`.
- Use the canonical two-digit numeric month hierarchy for both roots.
- Prefer embedded capture metadata for destination dating; use the documented fallback only when capture metadata is unavailable and report the provenance of the chosen date.
- Preserve original filenames.
- Keep same-stem RAW/JPEG pairs together in the same capture-date directory.
- Ignore known Canon control/catalogue files and non-media card metadata such as `CANONMSC/*.CTG` and `comstate.to3`.
- Preserve existing camera-card identity, inventory snapshot, import history, duplicate/conflict, verification, manifest, dry-run, and source-preservation behaviour from REQ-004 and REQ-009.
- Treat identical destination content as already present rather than creating a renamed duplicate.
- Treat same-name/different-content destinations as conflicts; do not invent alternate filenames.
- Include per-type counts and capture-date range in normal camera scan/inventory/import summaries where those summaries expose content information.
- Show progress during confirmed SLR import so a large RAW/JPEG card does not appear to have hung.

## Destination rules

For a photograph captured on 17 September 2026:

```text
<photo-root>/By Date/2026/09/17/IMG_0154.CR3
<photo-root>/By Date/2026/09/17/IMG_0154.JPG
```

For an SLR video clip captured on the same date:

```text
<video-root>/By Date/2026/09/17/MVI_0204.MP4
```

The photo and video roots are independent configured archive roots. Routing is decided per asset, not per card.

## Out of scope

- RAW development, colour correction, transcoding, or conversion.
- Renaming camera originals.
- Deleting, cleaning, ejecting, or formatting the source card.
- Importing camera control/catalogue files as user media.
- Treating a RAW/JPEG pair as one physical file; both originals are retained when both are present.

## Acceptance criteria

1. Given an SLR card containing CR3, JPEG, and MP4 media, when detection runs, then all supported assets are identified by media type without classifying the whole card as only photo or only video.
2. Given `IMG_0154.CR3` and `IMG_0154.JPG` with the same capture date, when planning runs, then both target the same `<photo-root>/By Date/YYYY/MM/DD/` directory and preserve their original filenames.
3. Given an SLR MP4 clip, when planning runs, then it targets `<video-root>/By Date/YYYY/MM/DD/` and preserves its original filename.
4. Given capture metadata is available, when a destination is planned, then the `YYYY/MM/DD` hierarchy is derived from that capture timestamp and its metadata source is recorded.
5. Given capture metadata is unavailable, when fallback dating is used, then the documented fallback source is reported rather than silently substituted.
6. Given a Canon control/catalogue file such as `CANONMSC/*.CTG` or `comstate.to3`, when planning runs, then the file is ignored and is not copied to either media archive.
7. Given identical content already exists at the planned destination, when planning runs, then it is reported as already present and no duplicate filename is created.
8. Given the planned destination name exists with different content, when planning runs, then the asset is reported as a conflict and no alternate filename is invented.
9. Given dry-run, when an SLR import is planned, then neither source nor destination is modified.
10. Given a conflict-free confirmed import, when it runs, then each archive-worthy asset is copied, verified, and finalised using the existing camera-import safety boundary while the source card remains unchanged.
11. Given a confirmed SLR import containing many RAW/JPEG assets, when files are processed, then terminal output provides visible progress until completion.
12. Given a numbered SLR card, when inventory/import history is recorded, then the same durable `cardId`, `snapshotId`, and `importId` model used by other camera cards is retained.
13. Given camera summaries expose card content, when an SLR card is scanned or inventoried, then CR3, JPEG, and MP4 counts and the available capture-date range are represented without counting ignored Canon control files as media.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md) provides camera detection, planning, verified copying, manifests, history, conflict handling, and dry-run semantics.
- [REQ-009: Camera card inventory](009-cameraCardInventory.md) provides durable card and snapshot identity.
- [REQ-020: Removable media discovery and lifecycle](020-removableMediaDiscovery.md) consumes inventory/import evidence for lifecycle state.
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-006: Camera import architecture](../../adr/006-cameraImportArchitecture.md)
- [ADR-007: Persist camera-card inventory in SQLite](../../adr/007-cameraInventoryPersistence.md)

## Verification

- Unit tests using synthetic Canon-style `DCIM/100CANON` trees containing CR3/JPEG pairs, MP4 clips, ignored Canon files, duplicates, and conflicts.
- Metadata tests proving CR3/JPEG/MP4 capture-date routing into numeric `YYYY/MM/DD` directories.
- Mixed-media tests proving photo and video assets from one card are routed to different configured roots.
- CLI integration tests through the canonical camera import/inventory commands.
- Progress-output tests for confirmed large-card import.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/cameraDetect.py`,
  `organiseMyVideo/cameraMetadata.py`, `organiseMyVideo/cameraPlan.py`,
  `organiseMyVideo/cameraImport.py`, `organiseMyVideo/cameraInventory.py`,
  `organiseMyVideo/cameraInventoryList.py`, `organiseMyVideo/mainLegacy.py`,
  `organiseMyVideo/__main__.py`
- Tests: `tests/test_cameraSlrImport.py`, `tests/test_cameraMetadata.py`,
  `tests/cameraFixtures.py`
- Documentation: `documentation/cameraImport.md`,
  `documentation/cameraInventory.md`, `documentation/commandLineInterface.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-17: created — add mixed SLR card support with Canon CR3/JPEG photographs routed to `photo root/By Date/YYYY/MM/DD` and SLR MP4 clips routed to `video root/By Date/YYYY/MM/DD`.
- 2026-09-17: completed — detect Canon-style `DCIM/100CANON` cards, route CR3/JPEG stills to the photo root and MP4 clips to the video root under numeric `By Date/YYYY/MM/DD`, preserve pairs/filenames/conflicts/identity, and report CR3/JPEG/MP4 counts with capture-date provenance.
