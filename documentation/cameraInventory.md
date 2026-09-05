# Camera card inventory

## Status

Implemented behaviour for
[REQ-009](../project/requirements/features/009-cameraCardInventory.md), following
[ADR-007](../project/adr/007-cameraInventoryPersistence.md).

## Outcome

`organiseMyVideo` catalogues a mounted camera SD card or a copied card
directory against an operator-assigned numeric card ID. Each confirmed run
stores a snapshot: date range, sold size, free space, file counts, camera
kinds, and a short description of the footage. GoPro, DJI, and dash-cam
layouts are recognised. Snapshots are written into the shared
[media catalogue](mediaCatalogue.md). USB thumb drives will use the same
numbered inventory
([REQ-015](../project/requirements/features/015-usbVolumeInventory.md))
and are not imported as camera media.

Inventory never copies, moves, or deletes camera media. Confirmed inventory
does write `organiseMyVideo.001` (zero-padded card ID) at the card root so
the volume itself records its numeric ID and the latest inventory summary. Archive import remains the separate
`camera import` action described in
[Camera media import](cameraImport.md).

## Command-line interface

```bash
$ python -m organiseMyVideo camera inventory /media/andy/7000-8000 --card 12
$ python -m organiseMyVideo camera inventory /media/andy/7000-8000 --card 12 --confirm
$ python -m organiseMyVideo camera inventory /media/andy/7000-8000
$ python -m organiseMyVideo camera inventory --card 12
```

The first form scans and prints a dry-run report. The second form writes
SQLite and `organiseMyVideo.NNN` on the card, where `NNN` is the zero-padded
card ID (`organiseMyVideo.001`). After that file exists, a scan can omit
`--card` and read the ID from the volume. The file contains the same summary
shown in the console, including free space. The last form prints
the latest stored snapshot for that card ID.

`--card` is required on the first scan of an unlabelled card. Dry-run remains
the default. `--confirm` is the only way to persist a snapshot, write the
card ID file, or call the vision API. A later `--card` that disagrees with
the on-card file is refused unless `--reassign` is also given:

```bash
$ python -m organiseMyVideo camera inventory /media/andy/7000-8000 --card 5 --reassign
$ python -m organiseMyVideo camera inventory /media/andy/7000-8000 --card 5 --reassign --confirm
```

`--reassign` replaces `organiseMyVideo.001` with `organiseMyVideo.005` (for a
change from 1 to 5) and stores the new snapshot under the new ID. Earlier
SQLite snapshots for the old ID are kept.

## What is recorded

Each snapshot includes:

- operator card ID
- source path and volume label
- volume capacity, free space, and summed content size
- earliest and latest capture time, with filesystem time as fallback
- detected camera kinds (`gopro`, `dji`, `dashcam`, or a mixture)
- camera manufacturer, model, serial, and firmware when on-card files
  provide them (GoPro `MISC/version.txt`, Transcend `DP250` folders)
- derived card size (32, 64, 128, or 256 GB) and free space, which the UI
  should show from `catalogueCardsList()`; USB-reader brand is not used
- counts of video, photo, thumbnail, preview, sidecar, and other files
- a content summary from sampled `.THM` files, or JPEGs when no `.THM` exists

Re-inventorying the same card ID appends a new snapshot. Show returns the
latest row; earlier rows stay in the database.

## Thumbnail recognition

GoPro `.THM` files are JPEG thumbnails. Confirmed inventory samples up to
eight of them, evenly spaced across the capture timeline, and sends them to
xAI image understanding (`grok-4.6`) using `XAI_API_KEY`. When the card has
no `.THM` files, JPEG stills are sampled instead. When neither exists, or the
API key is missing, the snapshot is still stored and the missing summary is
reported.

Tests inject a vision function and do not require a network or API key.

## Storage

Card snapshots are stored in the shared media catalogue:

```text
$XDG_STATE_HOME/organiseMyVideo/mediaCatalogue.sqlite
```

When `XDG_STATE_HOME` is unset the default is
`~/.local/state/organiseMyVideo/mediaCatalogue.sqlite`. Tables, columns, and
indexes use camelCase identifiers.

Dash-cam capture times are read from MP4 headers when present, then from
dated filenames such as `YYYYMMDD_HHMMSS_NF.mp4`,
`YYYY_MMDD_HHMMSS_*F.MP4`, compact `YYYYMMDDHHMMSS.MOV`, or Transcend
`TSYYYYMMDDHHMMSS.MOV`, then from filesystem mtime.

Transcend DrivePro 250 cards use a model folder and underscore video
directories, with sequence-numbered MP4 names:

```text
DP250/N_VIDEO/2026_0513_120237_012.mp4
```

That filename is `YYYY_MMDD_HHMMSS_sequence.mp4`. Older DrivePro cards may
use `N-Video` / `P-Video`, `.MOV`, and `.NMEA` GPS sidecars. The `SYSTEM`
firmware folder is ignored.

## Python module boundary

Inventory is a pure Python application feature. Scanning, metadata reading,
and persistence are callable without argparse or console parsing. The CLI
adapter constructs `CameraInventory` and prints the result.

Capture times come from JPEG EXIF and the MP4 movie header through
`cameraMetadata.py`. Filesystem modification time is the documented fallback.

Ignored clutter matches the camera-import rules: `._*` files, `_gsdata_`,
`MISC`, `LOST.DIR`, `System Volume Information`, and desktop metadata files.

## Verification

Tests use temporary directories and synthetic JPEG, MP4, `.THM`, DJI, and
ignored-file fixtures. They cover dry-run immutability, confirmed snapshots,
repeat card IDs, capture-time precedence, vision injection, missing API keys,
invalid card IDs, show-without-source, and execution through
`python -m organiseMyVideo camera inventory`.
