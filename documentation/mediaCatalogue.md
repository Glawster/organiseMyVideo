# Media catalogue

## Status

Implemented behaviour for
[REQ-010](../project/requirements/features/010-sqliteMediaCatalogue.md),
model extensions in
[REQ-016](../project/requirements/features/016-catalogueMediaIdentities.md),
and location reconciliation in
[REQ-034](../project/requirements/features/034-catalogueLocationReconciliation.md),
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
`movieItem`, `tvSeries`, `tvEpisode`, `catalogueScanRoot`, and
`homeVideoItem`.

## How rows are updated

- `camera inventory SOURCE --card ID --confirm` appends a card snapshot.
- `library rescan`, legacy `--rescan`, and `media scan --all` reconcile movie
  and TV rows from storage roots that can be listed.
- `media organise --merge` reconciles those rows after its live library scan,
  including a dry-run that changes no media files.
- `metadataLibrary.json` remains a move-time lookup cache. It is not the UI
  catalogue.

## Movie and TV rows

A movie row is one library folder. Title, year, and identifiers come from
known metadata in this order: MCM `movie.xml`, the `metadataLibrary.json`
cache, then the canonical video filename and folder hints. The catalogue does not scrape
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

Each movie and TV location has `locationState`: `current`, `stale`, or
`unverified`. A root that was listed is authoritative for the folders directly
inside it. Folders found there are `current`. A catalogued folder that the
listing no longer contains becomes `stale` and stays in the database. An error
while reading a directory inside a TV show does not retire the episodes under
that directory; those rows stay as they were. A root that is missing,
unmounted, or unlistable is not authoritative, so its existing rows are left
unchanged.
Opening an older catalogue marks existing rows `unverified` until the next
authoritative scan. `catalogueMoviesList()`, `catalogueTvSeriesList()`, and
`catalogueTvEpisodesList()` return current and unverified rows. Pass
`states` to include stale rows.

`media locate` prints every matching folder with that freshness. A path is
printed as `current` only when the catalogue says so and the folder is
present. A missing path that has not been authoritatively retired is
`unverified`. `--show` is optional: with a name it selects matching shows,
and without it locate lists every catalogued show.

## UI contract

The Qt browser in REQ-002 must read this catalogue. It may refresh by running
the same scan services. It must not treat a live disk walk as the source of
truth while this file exists.

## Camera cards

The UI should list cards from `catalogueCardsList()`, which returns the
latest snapshot per `cardId`. Show sold card size and remaining space from:

- `cardId`
- `volumeKind` — `sd` by default; `usb` reserved for future inventory
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

## Model and upgrades

External provider IDs use nullable TEXT, preserving prefixes and leading zeros.
They are separate from SQLite primary keys and have no uniqueness constraint:
multiple local files or folders may refer to the same external identity.
Before replacement, existing provider IDs are read in the same transaction:
movies and series match by `folderPath`, episodes by `filePath`. Missing IDs
fall back individually to these stored values. Current MCM and metadata-library
IDs always win when supplied. Descriptions are rebuilt from current evidence;
SQLite titles, show names, season numbers and episode titles are never reused.
Show and movie folders absent from an authoritatively listed root are marked
stale and kept. Episode rows under a TV directory that could not be read stay
as they were. Paths whose root was not listed stay as they were. When organiseMyVideo itself
moves a catalogued folder or file, the destination becomes current and receives
provider IDs that the destination does not already have; the old path remains
as stale. A path renamed outside organiseMyVideo does not inherit the old
path's IDs. Those IDs remain on the stale row.

[REQ-019](../project/requirements/features/019-catalogueMetadataResolution.md)
uses the existing local MCM readers, library lookup and canonical filename
parsers through a catalogue-only source, without constructing an organiser or
calling enrichment, provider, authentication, artwork or scraping workflows.
Its effective descriptive priority is MCM, metadataLibrary, canonical filename,
then path inference; provider priority is MCM, metadataLibrary, then persisted
catalogue IDs as fallback. The existing schema has no separate provenance fields.
Series provider IDs never stand in for episode IDs. The evidence-only TV reader
keeps path-derived seasons below canonical filenames and preserves season zero.
Movie XML can also describe a folder with no video file.

Independent replacement flags leave the other collection untouched. Provider
conflicts, provenance modelling, and ambiguous matches remain
canonical-media-identification concerns.

`homeVideoItem` is schema preparation only; no home-video scan or list service
is provided yet. `HomeVideoCatalogueRecord` represents its fields:

| Field | SQLite contract |
| --- | --- |
| `homeVideoId` | INTEGER PRIMARY KEY |
| `kind` | TEXT NOT NULL; collection kind such as GoPro or Drone |
| `relativePath` | TEXT NOT NULL; relative to the future collection root |
| `filePath` | TEXT NOT NULL UNIQUE; full media path |
| `captureAt` | Nullable TEXT ISO timestamp; unknown dates remain null |
| `dateSource` | TEXT NOT NULL; provenance, including unknown |
| `sizeBytes` | INTEGER NOT NULL, nonnegative |
| `scannedAt` | TEXT NOT NULL; ISO scan timestamp |

Opening an existing catalogue applies `CREATE TABLE IF NOT EXISTS` and inspects
columns with `PRAGMA table_info` before `ALTER TABLE ADD COLUMN`. No existing
rows or unrelated tables/indexes are recreated. Missing TV identity columns
start as null. `volumeKind` is TEXT NOT NULL DEFAULT 'sd', so legacy camera
snapshots and inserts omitting the field retain camera-card semantics. The
initial values are `sd` and `usb`; no closed SQL enum prevents future kinds.
Camera snapshot and catalogue dataclasses expose this value independently of
`cameraKinds`. No USB detection is added by this schema extension.

Camera snapshots also retain nullable TEXT `manufacturer`, `cameraModel`,
`cameraSerial`, `firmwareVersion`, `cameraWifiMac`, `goproCardId`, and `cardBrand`.
These columns use the same additive migration mechanism. The camera inventory
service restores them when showing a saved snapshot; the GoPro card token does
not replace the numeric card ID. See [Camera card inventory](cameraInventory.md).

## Camera capture corrections

`cameraCaptureCorrection` stores the import-scoped correction journal as JSON,
including the trusted reference pair, exact integer offset in microseconds,
selected files, attempts and per-file outcomes. `cameraCaptureTime` stores raw
and effective capture timestamps, their original source, rule ID, archive path
and SHA-256. Both are additive tables; inventory and import evidence is retained.
Read-only correction planning does not initialise or migrate the database.

Effective timestamps require matching archive path and content; card ID alone
never selects a correction. Existing Home Video rows follow verified corrected
paths and dates. See [Camera capture-time correction](cameraCaptureCorrection.md)
and [ADR-011](../project/adr/011-cameraCaptureCorrectionJournal.md).

Folder corrections from `camera correct-time --source` reuse these tables. Their
journal declares `scopeType=folder` and a namespaced `scopeId`; no import history
is invented. The legacy SQL `importId` column stores that scope key for folder
rows, while public payloads and timestamp lookup expose a null import identity.
The saved `folderEvidence` is the frozen observed selection used for safe retry.
