# Camera card inventory

## Status

Implemented behaviour for
[REQ-009](../project/requirements/features/009-cameraCardInventory.md), following
[ADR-007](../project/adr/007-cameraInventoryPersistence.md). Lifecycle and recycle
behaviour is extended by
[REQ-022](../project/requirements/features/022-removableMediaFormat.md).

## Outcome

`organiseMyVideo` catalogues a mounted camera SD card or copied card directory
against an operator-assigned numeric card ID. Each confirmed run stores a snapshot:
date range, sold size, free space, file counts, camera identity and content analysis.
GoPro, DJI, dash-cam, Canon SLR, and numbered USB media use the shared removable-media catalogue.

Inventory never imports archive files. Confirmed inventory writes a durable identity
such as `organiseMyVideo.018` at the card root and appends a SQLite snapshot. Camera
archive import remains the separate `camera import` action.

## Canonical query commands

Use:

```bash
organiseMyVideo camera inventory --list
organiseMyVideo camera inventory --card 18
```

`--list` shows all known cards in the compact register. `--card 18` shows all useful
known details for card 18. A separate `--full` report switch is not required.

The one-card report contains lifecycle state, location, snapshot count, successful
archive history and the latest stored inventory. Timestamps use `yyyy/mm/dd hh:mm`
and date-only capture ranges use `yyyy/mm/dd`.

Transient mount information such as the historical source path and filesystem volume
name is stored for audit purposes but omitted from the normal one-card report.

Example:

```text
CAMERA CARD 018
  Status:             available
  Location:           unknown
  Snapshots:          1
  Last archived:      2026/09/15 18:05
  Previous archives:  -
  Last inventoried:   2026/09/15 14:10

CAMERA CARD INVENTORY
  Card ID:            18
  Brand:              unknown
  Type:               sd
  Card size:          128 GB
  Free space:         104.5 MB
  Content size:       118.8 GB
  Volume size:        119.1 GB
  Date range:         2026/05/13 to 2026/05/16 (capture-metadata)
  Camera:             Transcend DrivePro 250
  Videos:             1573
  Photos:             0
  Thumbnails:         0
  Content:            no-thumbnails
  Keywords:           -
```

`Last archived` and `Previous archives` are successful import dates for that physical
card, newest first. They remain historical evidence after later formats or new
inventory snapshots. The current `Status` is derived only from the latest known card
state.

`Keywords` are generated from stored content-analysis text when useful analysis is
available; otherwise `-` is shown.

## Scanning and persistence

The source may be positional or supplied with `-s/--source`:

```bash
organiseMyVideo camera inventory /media/andy/CARD --card 18
organiseMyVideo camera inventory -s /media/andy/CARD --card 18
organiseMyVideo camera inventory -s /media/andy/CARD --card 18 --confirm
```

The first two forms are dry-run scans. `--confirm` persists the snapshot and writes the
on-card identity file. Once a card is labelled, scanning may omit `--card`; OMV reads
the durable ID from the volume.

On the first scan of an unlabelled card, omitting `--card` never silently allocates an
ID. OMV reports used IDs and suggests the lowest unused positive integer.

A supplied ID that conflicts with an existing on-card identity is refused unless
`--reassign` is explicitly requested and confirmed:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 5 --reassign
organiseMyVideo camera inventory -s /media/andy/CARD --card 5 --reassign --confirm
```

## Metadata and action overrides

Options such as `--brand`, `--location`, `--set-location`, `--reassign`, and
`--format` are metadata/action overrides rather than alternate report formats.

Examples:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 18 --brand Transcend --confirm
organiseMyVideo camera inventory --card 18 --location
organiseMyVideo camera inventory --card 18 --set-location "Car Rufus" --confirm
organiseMyVideo camera inventory --format card18
```

With a source present, `--card 18` means scan that physical card using/asserting ID 18.
Without a source or another action flag, `--card 18` means show the stored detailed
card report.

## Lifecycle status

Status is derived from current location, latest inventory content and successful
archive evidence:

| Status | Meaning |
| --- | --- |
| `in use` | A normal current location is set. |
| `missing` | Location is explicitly `missing`. |
| `empty` | Latest inventory has no content and there is no active location. |
| `to archive` | Latest inventory has content but no successful archive evidence. |
| `available` | Latest inventoried content is fully archived and the card is safe to wipe/reuse. |

The compact list also shows `Archived yes/no` for the latest snapshot. That value does
not permanently belong to the card. Re-inventorying new content creates a new latest
snapshot, so older archive evidence does not make the new content safe to wipe.

The detailed one-card report additionally preserves successful archive dates across
snapshots.

## What is recorded

Each snapshot includes:

- durable numeric card ID;
- source path and volume label for audit/provenance;
- physical volume kind (`sd` or `usb`);
- volume capacity, free space, used space and summed content size;
- earliest/latest capture date and provenance;
- camera kind and manufacturer/model metadata when detectable;
- derived sold capacity (32, 64, 128, or 256 GB where recognisable);
- counts of video, photo, thumbnail, preview, sidecar and other files;
- CR3, JPEG, and MP4 counts on SLR cards, without treating Canon control files
  such as `CANONMSC/*.CTG` or `comstate.to3` as media;
- content summary from sampled thumbnails/JPEGs where available;
- vision-analysis status;
- per-file snapshot rows for audit and later matching.

Re-inventorying the same card ID appends a new snapshot. Earlier snapshots remain in
the database.

## Thumbnail/content recognition

GoPro `.THM` files are JPEG thumbnails. Confirmed inventory samples up to eight of
them, evenly spaced across the capture timeline, and can send them to xAI image
understanding using `XAI_API_KEY`. JPEG stills are sampled when `.THM` files are
absent. When neither exists, or analysis is unavailable, the snapshot is still stored.

The detailed card report derives a short keyword list from useful persisted analysis
text; it does not invent keywords when analysis is unavailable.

## Storage

Snapshots are stored in:

```text
$XDG_STATE_HOME/organiseMyVideo/mediaCatalogue.sqlite
```

or, when `XDG_STATE_HOME` is unset:

```text
~/.local/state/organiseMyVideo/mediaCatalogue.sqlite
```

Tables, columns and indexes use camelCase identifiers.

## Dash-cam handling

Canon-style SLR cards such as `DCIM/100CANON` are inventoried as `slr` without
classifying the whole card as only photos or only video. CR3 and JPEG stills
count as photographs; SLR MP4 clips count as video. Capture dates prefer
embedded CR3/JPEG/MP4 metadata, then filesystem mtime, and the chosen
provenance is shown with the date range.

Dash-cam capture times are read from embedded metadata where available, then from
recognised dated filenames and finally from filesystem mtime. Transcend DrivePro 250
cards commonly use paths such as:

```text
DP250/N_VIDEO/2026_0513_120237_012.mp4
```

`SYSTEM` firmware content is ignored. Older DrivePro layouts, GoPro media and DJI
layouts remain supported through their existing recognisers.

## Python boundary

Scanning, metadata reading, persistence and report data are Python application
services. CLI parsing remains an adapter. Capture-time extraction is handled by the
camera metadata layer, with filesystem mtime as the documented fallback.

## Verification

Tests use temporary directories and synthetic media fixtures. Coverage includes
confirmed/dry-run snapshots, repeated card IDs, ID suggestions, positional and
`-s/--source` scan forms, location-only cards, archive-state derivation, compact list
output, detailed one-card output, date formatting and camera-import linkage.

## Source and permission errors

Select the mounted card itself, not a parent directory containing mounted volumes.
Copied card directories remain supported. Permission failures are reported as CLI
errors with a nonzero exit status rather than a Python traceback.
