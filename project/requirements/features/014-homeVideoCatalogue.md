# 014: Home video catalogue

## Status

ToDo

## Outcome

As a media-library operator, I need original and personal video under
`/mnt/myVideo/Video` indexed in the shared SQLite catalogue so that the CLI
and Qt UI can present a coherent home-video library independently of the
physical historical folder layout.

The user-facing library must organise personal footage by its best-known
capture date and media metadata, while retaining the physical path and
source provenance for audit and maintenance. GoPro, DJI/Drone, Dashcam,
phone video, tape transfers, sports recordings, and other personal footage
are all Home Video rather than movie or television releases.

## Context

Movies live under `/mnt/movie<n>/Title (Year)/`. TV lives under
`/mnt/video<n>/TV/` and `/mnt/myVideo/TV`. Personal footage is a third
library rooted at `/mnt/myVideo/Video`.

The existing archive is primarily chronological under `By Date`, but its
historical layout is not canonical. Observed month-directory conventions
include, for example:

```text
By Date/2019/08 - Aug/
By Date/1985/1985-08/
By Date/2020/01/
By Date/1986/03 - March/
```

Files may also have an embedded or filename-derived date which disagrees
with the containing directory. The archive contains phone/iOS video,
GoPro/DJI material, generic `.MOV`/`.MP4` files, hash-based names, edited
or paired variants, and Apple `.AAE` sidecars. Duplicate-looking copies
such as `name.ext` and `name (1).ext` also occur.

Consequently the filesystem hierarchy is evidence about a file, not the
user-facing catalogue hierarchy. The catalogue must not require a wholesale
re-parenting of the archive in order to provide a clean timeline.

REQ-004 stores new camera imports under source-specific dated folders such
as:

```text
/mnt/myVideo/Video/GoPro/YYYY/MM-MMM/DD/
/mnt/myVideo/Video/Drone/YYYY/MM-MMM/DD/
/mnt/myVideo/Video/Dashcam/YYYY/MM-MMM/DD/
```

Those files become Home Video catalogue items after import. Camera-card
identity, inventory snapshot identity, and import identity are provenance;
they must not replace the Home Video item as the principal library object.

## User-facing model

The CLI and UI should be able to present a virtual timeline independent of
physical folder spelling:

```text
Home Video
  2020
    January
    February
    March
  2019
    January
    ...
```

Within a month the UI may group items by day or later by derived event. A
physical file remains addressable and auditable through its stored path.
For example, a file may be shown as captured on 16 August 2019 while its
physical path is reported separately if it currently resides in a different
historical folder.

The catalogue must also provide enough information for a maintenance/issues
view, for example:

```text
Possible duplicates
Folder/date mismatch
Unknown capture date
Unrecognised or orphan sidecar
```

These are observations only in this requirement; no file is moved, renamed,
or deleted automatically.

## Scope

- Treat `/mnt/myVideo/Video` as the default home-video root. The root must be
  configurable/injectable and tests must not require the real mount.
- Scan personal video recursively without treating it as movie or TV media.
- Persist one durable catalogue row for each primary Home Video media file.
- Retain at least:
  - physical/relative path;
  - filename and extension;
  - size;
  - media type;
  - first-level/source kind where meaningful;
  - best-known capture date/time;
  - date source/provenance;
  - date confidence or equivalent certainty state;
  - available technical metadata needed by the UI;
  - camera/import provenance when known.
- Resolve a canonical/best-known capture date without assuming the containing
  directory is correct. Candidate evidence may include embedded media
  metadata, camera metadata, filename conventions, import metadata, and the
  historical folder path.
- Preserve conflicting date evidence so that a folder/date mismatch can be
  reported rather than silently hidden.
- Normalise historical month-directory spelling only in the virtual catalogue
  view; do not rename directories as part of scanning.
- Recognise common sidecar/companion files, including `.AAE`, and associate
  them with a primary media item where this can be established safely.
- Record unknown/orphan sidecars as catalogue issues rather than silently
  discarding them.
- Identify duplicate candidates using safe evidence suitable for later
  review. Filename similarity alone must not cause files to be treated as
  identical.
- Detect likely folder/date mismatches and unknown/uncertain capture dates.
- Expose service APIs suitable for both CLI and Qt, including a home-video
  list/timeline query and issue/audit query. These services must not import
  Qt or argparse.
- On library rescan, reconcile Home Video catalogue state with the filesystem
  so removed files no longer appear as active library items while preserving
  any durable provenance/history required elsewhere.
- Keep GoPro, Drone, Dashcam, phone footage, transferred tapes, Rugby, Footy,
  Music, and other personal recordings within the same Home Video product
  library even where their storage folders differ.

## Content enrichment compatibility

The Home Video catalogue must be extensible for later media-understanding
features without requiring the physical files to be renamed or relocated.
Future enrichment may include:

- automatically assigned keywords with confidence and source;
- manual keywords that are never silently overwritten by automatic analysis;
- people, places, activities, objects, and event descriptions;
- OCR/text observations from video frames;
- structured sports-event metadata such as teams, competition, and final
  score;
- logical event grouping across multiple media files.

Implementation of AI/vision/OCR analysis itself is outside this requirement;
this requirement establishes a catalogue identity and query model that those
features can enrich later.

## Out of scope

- Moving, renaming, or deleting files under `/mnt/myVideo/Video`.
- Automatically fixing historical month folder names.
- Automatically deleting or consolidating duplicate candidates.
- Implementing REQ-004 `camera import` / `camera migrate`.
- AI keyword generation, face recognition, OCR, sports-score extraction, or
  other content-understanding engines.
- Final automatic event grouping.
- Classifying home video as movies or TV episodes.
- Artwork scraping.
- Media playback implementation.

## Acceptance criteria

1. Given a temporary Home Video tree containing GoPro, Drone, phone video,
   and a topic folder, when catalogue refresh runs, then supported personal
   media are stored as Home Video items and not as `movieItem` or
   `tvEpisode` rows.
2. Given equivalent month folders such as `08 - Aug`, `1985-08`, or `08`,
   when the catalogue is queried by timeline, then their files can appear
   under the same canonical August view without renaming those directories.
3. Given a media file whose reliable embedded capture date conflicts with
   its containing `By Date` folder, when scanned, then the best-known capture
   date and the folder-derived date evidence are both retained and the item
   is available to the folder/date-mismatch audit query.
4. Given a file with no reliable embedded date but a recognised dated
   filename, when scanned, then the filename date may be used according to a
   documented precedence policy and its source is recorded.
5. Given a file for which no sufficiently reliable capture date can be
   determined, when scanned, then it remains in the Home Video catalogue and
   is returned as an unknown/uncertain-date issue rather than being dropped.
6. Given `clip.MP4` and `clip (1).MP4`, when scanned, then they may be flagged
   as duplicate candidates but are not considered identical solely because
   of their names.
7. Given an `.AAE` or other recognised sidecar that can be associated safely
   with a primary media item, when scanned, then the sidecar relationship is
   retained without creating a misleading standalone playable video item.
8. Given an orphan or unrecognised sidecar, when scanned, then it is
   available through the issue/audit query.
9. Given a GoPro file imported by REQ-004 with known card/import provenance,
   when catalogued, then the Home Video item can retain that provenance while
   remaining the principal library object presented to the user.
10. Given a second scan after a media file is removed, when it completes,
    then the active Home Video catalogue no longer presents the missing file.
11. Given `library rescan`, when it indexes storage, then Home Video catalogue
    application state may update in dry-run because the catalogue is
    application state rather than a mutation of the user's archive.
12. Given the catalogue service is used directly, when it lists Home Video
    or Home Video issues, then it does not import Qt or argparse.
13. Given tests execute, then they use temporary trees and never read from or
    write to the real `/mnt/myVideo/Video` mount.
14. Given Home Video catalogue data is presented by a future UI, then it can
    construct year/month/day timeline views from catalogue fields rather
    than parsing the physical path itself.
15. Given future keyword/OCR/sports enrichment is added, then enrichment can
    attach to stable Home Video item identities without requiring a media
    file rename or move.

## Date precedence policy

The implementation must document and test a deterministic precedence policy
for selecting the best-known capture date. It must prefer higher-quality
media evidence over folder placement and must retain the source used. A
reasonable initial ordering is:

1. reliable embedded capture/original timestamp;
2. trusted camera/import metadata;
3. recognised filename capture timestamp;
4. historical `By Date` path;
5. filesystem modification timestamp only as low-confidence fallback where
   explicitly enabled.

The exact extractor set may evolve, but changing precedence is a behavioural
change and must be covered by tests.

## Dependencies and decisions

- [REQ-002: Qt media-library browser](002-qtMediaLibraryBrowser.md)
- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-016: Catalogue media identities](016-catalogueMediaIdentities.md)
- [REQ-021: Removable media discovery and lifecycle](021-removableMediaDiscovery.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)
- [Home video archive](../../../documentation/homeVideo.md)

## Verification

- Temporary directory fixtures representing historical `By Date` folder
  variants and source/topic folders.
- Fixtures with embedded, filename-derived, path-derived, conflicting, and
  unknown dates.
- Duplicate-candidate and sidecar fixtures.
- Service-level tests for timeline and issue queries.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: [Home video archive](../../../documentation/homeVideo.md),
  [Media catalogue](../../../documentation/mediaCatalogue.md)
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-04: created — operator asked the media inventory to include
  `/mnt/myVideo/Video`, of which GoPro and Drone are part.
- 2026-09-14: expanded after review of the real `By Date` archive. Defined
  virtual timeline presentation, capture-date provenance, historical folder
  inconsistencies, duplicate candidates, sidecars, maintenance issues,
  camera-import provenance, and compatibility with later keyword/OCR/sports
  enrichment.
