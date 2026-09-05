# 014: Home video catalogue

## Status

ToDo

## Outcome

As a media-library operator, I need original and personal video under
`/mnt/myVideo/Video` indexed in the SQLite catalogue so that the UI can
browse home video, including GoPro and Drone archives, without treating
those folders as movie or TV releases.

## Context

Movies live under `/mnt/movie<n>/Title (Year)/`. TV lives under
`/mnt/video<n>/TV/` and `/mnt/myVideo/TV`. Personal footage is a third
library: `/mnt/myVideo/Video`. Inspected first-level folders include
`GoPro`, `Drone`, `Home Video` (Video8/VideoDV tape transfers), `By Date`,
`Extension`, `Evelyn`, `Cycling`, `Rugby`, `Footy`, `Music`, and a nested
`Video/Video` dump.

REQ-004 already stores new camera imports as:

```text
/mnt/myVideo/Video/GoPro/YYYY/MM/DD/
/mnt/myVideo/Video/Drone/YYYY/MM/DD/
/mnt/myVideo/Video/Dashcam/YYYY/MM/DD/
```

GoPro and Drone are part of home video, not a separate product library.
Rugby, Footy, and Music sit in the same tree and are personal recordings,
not the TV organiser.

The tree does not need a wholesale re-parenting (no new `Camera/` or
`Recorded/` wrapper that would move a terabyte for navigation). Camera
dated-folder migration stays REQ-004. Nested duplicates and empty leftover
folders are cleanup candidates, not this increment's mutations.

## Scope

- Treat `/mnt/myVideo/Video` as the default home-video root (configurable;
  tests must not require the real mount).
- On library rescan, replace home-video catalogue rows from that tree.
- Store each media file (or tape-transfer folder item) with first-level
  kind (`gopro`, `drone`, `dashcam`, `homeVideo`, `byDate`, or the folder
  name), relative path, size, and available date.
- Expose `catalogueHomeVideoList()` for the UI Home video collection.
- Keep GoPro, Drone, and Dashcam as first-level folders under the home-video
  root.
- Document cleanup that is out of scope here: nested `Video/Video` GOPR
  dumps, empty `Home Video/GoPro`, loose AVIs at the GoPro root.

## Out of scope

- Moving, renaming, or deleting files under `/mnt/myVideo/Video`.
- Implementing REQ-004 `camera import` / `camera migrate`.
- Classifying home video as movies or TV episodes.
- Artwork scraping or playback.

## Acceptance criteria

1. Given a temporary home-video tree with `GoPro`, `Drone`, and a topic
   folder each containing a video, when catalogue refresh runs, then those
   files are stored as home-video rows and not as `movieItem` or
   `tvEpisode`.
2. Given a GoPro file under `GoPro/2023/10/06/`, when listed, then its kind
   is `gopro` and the path is preserved.
3. Given a second scan after a file is removed, when it completes, then that
   row disappears because home-video tables are replaced, not merged.
4. Given `library rescan`, when it indexes storage, then home-video rows
   update even in dry-run because that is application state.
5. Given the catalogue service is used directly, when it lists home video,
   then it does not import Qt or argparse.
6. Given the real `/mnt/myVideo/Video` path, when tests run, then they do
   not read or write that mount.

## Dependencies and decisions

- [REQ-002: Qt media-library browser](002-qtMediaLibraryBrowser.md)
- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)
- [Home video archive](../../../documentation/homeVideo.md)

## Verification

- Temporary directory fixtures with GoPro, Drone, and topic folders.
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
