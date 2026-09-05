# 016: Catalogue media identities

## Status

Completed

## Outcome

The SQLite catalogue must represent external movie and TV identities, future
personal media, and removable-volume kinds without changing scan behaviour.

## Context

REQ-010 provides the shared catalogue. Movie and TV identity fields already
exist on this branch; their compatibility contract needs migration coverage.
REQ-014 and REQ-015 remain separate scanning features.

## Scope

- Retain nullable TEXT `tvSeries.tvdbId`, `tmdbId`, `imdbId` and
  `tvEpisode.tvdbEpisodeId`, `tmdbEpisodeId`, `imdbId`; scans need not populate them.
- Retain existing movie identities and catalogue list APIs.
- Create `homeVideoItem` with INTEGER primary key `homeVideoId`, required TEXT
  `kind`, `relativePath`, unique `filePath`, `dateSource`, `scannedAt`, nullable
  TEXT `captureAt`, and required nonnegative INTEGER `sizeBytes`.
- Add TEXT `cardInventory.volumeKind`, defaulting safely to `sd`, with `usb`
  representable for future use. Keep camera kinds independent.
- Represent the fields in Python dataclasses with compatible constructor defaults.
- Upgrade old databases additively through the existing schema-application path.

## Out of scope

- REQ-014 home-video scanning, list services, or UI.
- REQ-015 USB inventory or detection.
- Renaming the cardInventory domain or redesigning catalogue APIs.
- Filename parsing, metadata resolution changes, API scraping, new dependencies.
- Moving, renaming, or deleting media files.

## Acceptance criteria

1. Old catalogue files open through cards, movies, and TV episode list methods;
   all movie, TV, camera snapshot and file rows remain intact.
2. Missing columns and tables are added without destructive recreation of
   unrelated tables or indexes; repeated upgrades are harmless.
3. Fresh and migrated TV tables accept null identities and round-trip all six
   external identity fields as text, including leading zeros.
4. Fresh and migrated catalogues contain `homeVideoItem`; rows can represent
   known or unknown capture dates and enforce path uniqueness and valid sizes.
5. Old and newly scanned camera snapshots use `sd`; persistence and catalogue
   records can round-trip `usb` without implementing USB scanning.
6. Existing camera inventory and media catalogue tests and the full suite pass.
7. REQ-010's completed scope and REQ-014/015's future scope remain accurate.

## Dependencies and decisions

- [REQ-010](010-sqliteMediaCatalogue.md)
- [REQ-014](014-homeVideoCatalogue.md)
- [REQ-015](015-usbVolumeInventory.md)
- [ADR-008](../../adr/008-sqliteMediaCatalogue.md)
- [ADR-009](../../adr/009-numberedRemovableVolumes.md)

## Verification

Use real temporary SQLite files for legacy migration, repeated opens, identity
round trips, home-video constraints, and camera persistence/list integration.
Run `pytest`, `black --check .`, `runLinter .`, `runLinter --markup`, and
`git diff --check`.

## Change history

- 2026-09-05: created — operator requested catalogue model preparation without
  implementing additional scanning features.
