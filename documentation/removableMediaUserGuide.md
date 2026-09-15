# Removable media user guide

This guide covers numbered removable-media handling in `organiseMyVideo`, including
camera SD cards and USB storage. A numeric card ID is durable for the life of the
physical medium. Inventory snapshots describe what was on the medium at a point in
time; import manifests record what was copied into the archive.

## Canonical query commands

The normal read-only commands are deliberately small in number:

```bash
organiseMyVideo camera inventory --list
organiseMyVideo camera inventory --card 18
organiseMyVideo camera import --list
organiseMyVideo camera import --card 18
```

They mean:

- `camera inventory --list` — compact register of all known cards;
- `camera inventory --card ID` — all useful current and historical details for one card;
- `camera import --list` — summary of all recorded import runs;
- `camera import --card ID` — full per-file import manifest history for one card.

`--full` is no longer part of the normal user workflow. Older combined forms remain
accepted where practical for compatibility, but should not be used in new examples.

## Basic lifecycle

```text
new/unregistered
    -> inventory and assign card ID
    -> in use
    -> removed from device
    -> to archive
    -> camera import
    -> available
    -> format/recycle
    -> empty
    -> in use again
```

`missing` is an exceptional state for a known card whose whereabouts are not known.

## Register or inventory a card

Inventory is non-destructive. Preview a scan:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4
```

Persist the inventory and durable identity:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4 --confirm
```

The medium receives an identity file such as `organiseMyVideo.004`. Once labelled,
that numeric ID remains the identity of the physical medium.

Inventory options such as `--brand`, `--reassign`, `--location`, `--set-location`,
and `--format` are metadata/action overrides. They do not create alternative report
formats. A source plus `--card` means scan/import that physical card; `--card` by
itself means show the stored details/history for that card.

## List all cards

```bash
organiseMyVideo camera inventory --list
```

The compact register contains Card, Status, Archived, Type, Size, Camera, Location,
and Last inventory. Displayed timestamps use `yyyy/mm/dd hh:mm`.

`Archived` in this compact register answers whether the **latest inventory snapshot**
has successful archive evidence. It is not a permanent property of the card.

## Show one card

```bash
organiseMyVideo camera inventory --card 18
```

The one-card view is the authoritative human-readable card report. It includes
lifecycle state and archive history followed by the useful latest inventory data.
Transient mount details such as source mount path and current filesystem volume name
are intentionally omitted.

Example shape:

```text
CAMERA CARD 018
  Status:             available
  Location:           unknown
  Snapshots:          1
  Last archived:      2026/09/15 18:05
  Previous archives:  2026/08/21 14:32, 2026/07/04 09:17
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
card, newest first. This archive history remains visible even after a later format or
new inventory snapshot. `Status`, by contrast, describes the current/latest known
state of the card.

`Keywords` are derived from stored content-analysis text when useful analysis exists;
otherwise the field is `-`.

## Status meanings

| Status | Meaning |
| --- | --- |
| `in use` | A normal current location is set, for example a car, camera, drawer, or kit bag. |
| `missing` | Location is explicitly `missing`. |
| `empty` | No active location is set and the latest inventory contains no content. |
| `to archive` | No active location is set, content exists, and the latest inventory snapshot has not yet been successfully imported. |
| `available` | No active location is set and the latest inventoried content has been successfully archived. The card is safe to wipe/reuse. |

A card can therefore be `available` while still physically containing the old files.
Formatting is the explicit transition from `available` to `empty`.

## Location and metadata overrides

Show the stored location:

```bash
organiseMyVideo camera inventory --card 4 --location
```

Set it, previewing first and then confirming:

```bash
organiseMyVideo camera inventory --card 4 --set-location "Car JSZ5017"
organiseMyVideo camera inventory --card 4 --set-location "Car JSZ5017" --confirm
```

Mark a card missing:

```bash
organiseMyVideo camera inventory --card 4 --set-location missing --confirm
```

When scanning a card, metadata overrides such as brand remain source-scoped, for
example:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4 --brand Transcend --confirm
```

## Preview and run an import

Preview:

```bash
organiseMyVideo camera import -s /media/andy/CARD --card 4
```

Confirm:

```bash
organiseMyVideo camera import -s /media/andy/CARD --card 4 --confirm
```

With a source present, `--card 4` is an identity assertion. It does not assign an ID
to an unlabelled medium.

The importer preserves the source, verifies copied files, avoids overwriting different
content, writes a JSON manifest, and links the import to the relevant inventory
snapshot where possible.

## View import history

All imports, summary form:

```bash
organiseMyVideo camera import --list
```

Full manifest history for one card:

```bash
organiseMyVideo camera import --card 4
```

The per-card view emits one logical line per asset:

```text
copied          /source/file.MP4 -> /archive/file.MP4
already present /source/file.MP4 -> /archive/file.MP4
failed          /source/file.MP4 -> /archive/file.MP4 | error: ...
```

The underlying manifests are stored under:

```text
~/.local/state/organiseMyVideo/cameraImports/
```

## Format an archived card for reuse

A card whose latest content has been safely archived becomes `available`. Preview the
wipe first:

```bash
organiseMyVideo camera inventory --format card18
```

Then confirm the destructive operation:

```bash
organiseMyVideo camera inventory --format card18 -y
```

The format workflow verifies archive evidence and removable-device identity, preserves
the supported filesystem family, labels the filesystem `Card18`, recreates
`organiseMyVideo.018`, and writes a new empty inventory snapshot.

After formatting, the current state becomes `empty`. The latest snapshot itself has no
archive requirement, while `Last archived` and `Previous archives` continue to show
successful historical imports of previous content.

## Re-inventory after reuse

OMV cannot know that a card has acquired new content until it is inventoried again.
After reuse, run:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4 --confirm
```

A new non-empty snapshot without matching successful archive evidence changes the
current status to `to archive` (unless a current location makes it `in use`). Previous
archive dates remain historical evidence only and do not make the new content safe to
wipe.

## USB sticks

USB storage uses the same numbered removable-media register and ID space. Its Type is
`usb` rather than `sd`. USB inventory does not make a USB stick a camera import source;
camera import remains restricted to recognised camera-media layouts.
