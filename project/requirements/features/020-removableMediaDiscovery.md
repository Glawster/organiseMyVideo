# 020: Removable media discovery and lifecycle

## Status

ToDo

## Outcome

As a media-library operator, I need to search, assess, and select numbered SD
cards and USB volumes from the catalogue so that I can find stored content,
choose an appropriate card before going out, and know when a card is safe to
recycle.

## Context

The camera-card inventory already records numbered removable media, including
size, free space, capture dates, camera/device metadata, file counts, and a
content summary. USB-volume inventory is planned to use the same numbered
volume model. Camera import will add verified archive outcomes.

The catalogue should use those records as operational knowledge rather than
only as historical snapshots. Typical questions include:

- Which card should I take with me?
- Which empty card has gone unused for the longest time?
- Which card has enough free space for the planned recording?
- Where is footage from a particular date or event?
- Which numbered volume contains a named file, software package, document, or
  other non-media content?
- Which cards still contain unique or unimported content?
- Which cards are safe to reuse or format?

## Scope

- Search known removable-volume inventory by card/volume ID, date or date
  range, filename, content-summary text, keywords, camera/device metadata, and
  file type.
- Search non-media inventory as well as camera media so numbered USB volumes
  can locate software installers/packages, documents, archives, and other
  stored files.
- List known removable volumes with current capacity, free space, most recent
  inventory date, content date range, volume kind, and derived lifecycle
  status.
- Show a detailed view of one numbered removable volume with
  `camera show --card ID`.
- Show the complete removable-volume inventory with `camera show --all`.
- Treat `--card` and `--all` as mutually exclusive selectors for `camera show`.
- Recommend cards for use according to free space and lifecycle state.
- Prefer the oldest suitable empty/recyclable card when several equivalent
  cards are available, so physical cards are rotated rather than repeatedly
  using the same one.
- Support a requested minimum free-space threshold.
- When sufficient recording-rate information is available, allow selection by
  expected recording duration; otherwise report that free-space selection is
  the available evidence rather than inventing a duration estimate.
- Derive operational status from catalogue/import evidence rather than storing
  a manually maintained status where possible.
- Distinguish at least the following concepts: ready to use, contains
  unarchived/current content, archived/safe to recycle, needs review, and
  insufficient space.
- Identify content that has not been successfully imported and verified.
- Identify import conflicts, failures, unknown content, or other evidence that
  prevents a safe-to-recycle decision.
- Detect likely duplicate content recorded on more than one removable volume
  where digest/identity evidence permits it.
- Keep historical inventory snapshots; selection/search should normally use
  the latest snapshot while retaining older evidence for audit and lifecycle
  calculations.
- Expose the capability through importable Python catalogue/query services
  before adding CLI or Qt presentation layers.

## Out of scope

- Automatically formatting, erasing, or ejecting cards or USB volumes.
- Declaring a card safe to erase solely because its free space is low or its
  content is old.
- Guessing that content was archived when there is no verification evidence.
- Replacing the camera-import verification/manifest process.
- Requiring every removable volume to contain camera media.

## Candidate operator interface

Removable-media lifecycle and discovery remain under the `camera` command,
while movie/TV organisation remains under `media`.

```bash
organiseMyVideo camera show --card 6
organiseMyVideo camera show --all
organiseMyVideo camera find --date 2026-09-12
organiseMyVideo camera find --keyword hillsborough
organiseMyVideo camera recommend --free 100GB
organiseMyVideo camera status --card 12
```

For `camera show`, exactly one of `--card ID` or `--all` is required. The
service layer must not depend on these exact CLI spellings.

## Lifecycle model

Initial derived states are:

- `READY`: empty or otherwise verified safe for immediate reuse.
- `IN_USE`: contains current content that has not yet been fully archived and
  verified.
- `ARCHIVED`: known content has been imported and verified and no unique
  remaining files prevent reuse.
- `NEEDS_REVIEW`: unknown files, failed imports, conflicts, missing verification,
  or other ambiguity prevents an automatic recycle decision.
- `FULL`: insufficient useful free space for the requested use; this may be a
  query result layered on top of the underlying content lifecycle state rather
  than a permanently stored status.

Names may be refined during implementation, but the safety semantics must be
preserved.

## Acceptance criteria

1. Given multiple inventoried removable volumes, when the operator asks for a
   suitable card without further constraints, then cards not safe for reuse
   are excluded and the oldest suitable empty/recyclable card is preferred.
2. Given a minimum free-space requirement, when recommendation runs, then only
   safe cards meeting that threshold are returned, ordered deterministically.
3. Given no safe card meeting the requested space, when recommendation runs,
   then the result explicitly reports that no suitable card is available and
   does not recommend a card with unverified content.
4. Given a date or date range, when search runs, then matching removable-volume
   snapshots/content are returned with the numbered volume ID and enough
   context to locate the physical card.
5. Given text or keywords, when search runs, then filename, stored content
   summary, relevant metadata, and indexed non-media file information can
   contribute matches.
6. Given a numbered USB volume containing a software installer/package,
   document, archive, or other non-camera file, when searched by identifying
   filename/type/keyword, then the volume can be located without requiring it
   to be classified as camera media.
7. Given a card whose relevant files were imported and verified successfully,
   with no unique unknown/unverified content remaining, when lifecycle status
   is derived, then it can be reported as safe to recycle.
8. Given any failed import, destination conflict, unknown unique file, or
   missing verification affecting content on a card, when lifecycle status is
   derived, then the card is not reported safe to recycle and the blocking
   evidence is shown.
9. Given repeated inventory snapshots for the same numbered volume, when
   search/recommendation runs, then the latest snapshot supplies current
   capacity/content state while historical snapshots remain available for
   audit and oldest-use/rotation calculations.
10. Given digest or durable identity evidence showing the same content on more
    than one removable volume, when queried, then duplicate locations can be
    reported without deleting either copy.
11. Given `camera show --card ID`, when the ID exists, then the latest detailed
    record for that removable volume is shown; given `camera show --all`, then
    all known removable volumes are shown in a deterministic summary.
12. Given `camera show` with both `--card` and `--all`, or with neither, then
    argument validation fails before a catalogue query is executed.
13. Given the Python query/recommendation services are called directly, then
    they return structured results without depending on argparse, console
    parsing, or the Qt UI.
14. No search, recommendation, listing, show, or status query mutates removable
    media or archive content.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-015: USB volume inventory](015-usbVolumeInventory.md)
- [REQ-016: Catalogue media identities](016-catalogueMediaIdentities.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)
- [ADR-009: Numbered removable volumes](../../adr/009-numberedRemovableVolumes.md)

## Verification

- Unit tests with multiple synthetic card/USB snapshots covering empty,
  archived, unimported, conflicted, nearly full, and unknown-content states.
- Search tests for date ranges, keywords, filenames, camera metadata, and
  non-media file types.
- Recommendation tests proving minimum-space filtering and oldest-suitable-card
  rotation.
- `camera show` tests covering `--card ID`, `--all`, and mutual-exclusion/error
  handling.
- Safety tests proving ambiguous/unverified cards are never labelled safe to
  recycle.
- Direct service tests independent of CLI and Qt layers.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-12: created from operator use cases for choosing cards, locating
  content across numbered removable media, finding non-media files on USB
  volumes, and deriving safe-to-recycle lifecycle state from inventory and
  verified import evidence.
- 2026-09-12: refined CLI direction so removable-media discovery remains under
  `camera`; added `camera show --card ID` and `camera show --all`, with mutually
  exclusive selectors.
