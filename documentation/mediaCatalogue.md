# Media catalogue

## Status

Implemented behaviour for
[REQ-010](../project/requirements/features/010-sqliteMediaCatalogue.md),
following [ADR-008](../project/adr/008-sqliteMediaCatalogue.md).

## Outcome

`organiseMyVideo` keeps one SQLite catalogue as the record the UI should
query. Library scans refresh movie and TV rows. Confirmed camera inventory
appends card snapshots, including dash-cam cards. Home-video rows
([REQ-014](../project/requirements/features/014-homeVideoCatalogue.md))
and USB volume snapshots
([REQ-015](../project/requirements/features/015-usbVolumeInventory.md))
use the same file once implemented.

## File

```text
$XDG_STATE_HOME/organiseMyVideo/mediaCatalogue.sqlite
```

Default: `~/.local/state/organiseMyVideo/mediaCatalogue.sqlite`.

Tables use camelCase names: `cardInventory`, `cardInventoryFile`,
`movieItem`, `tvSeries`, `tvEpisode`. Home video will add `homeVideoItem`.

## How rows are updated

- `camera inventory SOURCE --card ID --confirm` appends a card snapshot.
- `library rescan` (and a metadata rebuild from storage) replaces movie and
  TV tables from the current archive folders.
- `metadataLibrary.json` remains a move-time lookup cache. It is not the UI
  catalogue.

## Movie and TV rows

A movie row is one library folder. Title, year, and identifiers come from
known metadata in this order: MCM `movie.xml`, the `metadataLibrary.json`
cache, then the folder or video filename. The catalogue does not scrape
or re-identify movies.

A TV series row is a show folder. It stores `tvdbId`, `tmdbId`, and
`imdbId` when those are already known so two programmes with the same
name stay distinct. Episode rows are media files under that show and
store `tvdbEpisodeId`, `tmdbEpisodeId`, and `imdbId` when known.

Show name, season, episode, title, and provider IDs come from known
metadata in this order: MCM `series.xml` and episode XML, the
metadata-library cache, the organiser's canonical filename parser, then
the show/season folder names. The catalogue records what the organiser
already knows; it does not run a second identifier over the filename.
IDs may be null until a later scan has them.

Removed folders disappear on the next scan because movie and TV tables are
replaced, not merged.

## UI contract

The Qt browser in REQ-002 must read this catalogue. It may refresh by running
the same scan services. It must not treat a live disk walk as the source of
truth while this file exists.

## Camera cards

The UI should list cards from `catalogueCardsList()`, which returns the
latest snapshot per `cardId`. Show sold card size and remaining space from:

- `cardId`
- `cardRatedGigabytes` — derived sold size: 32, 64, 128, or 256 GB
- `freeBytes` — space still available on the volume
- `usedBytes` / `contentBytes` — occupied space
- `cameraKinds`, `dateStart`, `dateEnd`

USB thumb drives will use the same list and numeric IDs, with
`volumeKind` `usb` ([REQ-015](../project/requirements/features/015-usbVolumeInventory.md)).
Do not use USB-reader vendor strings as the card brand. See
[Camera card inventory](cameraInventory.md).

## Home video

The UI Home video collection will list `catalogueHomeVideoList()` rows
from `/mnt/myVideo/Video` ([REQ-014](../project/requirements/features/014-homeVideoCatalogue.md)).
First-level folders are kinds: `GoPro` and `Drone` are part of this
collection. See [Home video archive](homeVideo.md).
