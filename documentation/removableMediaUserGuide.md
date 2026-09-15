# Removable media user guide

This guide covers numbered removable-media handling in `organiseMyVideo`, including
camera SD cards and USB storage.

The same numeric card ID is retained for the life of the physical medium. Inventory
records describe what was on the medium at a point in time; import manifests record
what was copied into the archive.

## Basic workflow

A typical camera-card lifecycle is:

```text
new/unregistered
    -> inventory and assign card ID
    -> in use
    -> removed from device
    -> to archive
    -> camera import
    -> available
    -> in use again
```

`missing` is an exceptional state for a known card whose whereabouts are not known.

## 1. Register or inventory a card

Inventory is non-destructive. It scans the removable medium and records its identity,
capacity, current content, date range, and detected camera information.

Dry-run first:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4
```

Confirm the inventory and write the numbered label to the card:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4 --confirm
```

The card receives a label such as:

```text
organiseMyVideo.004
```

Once a card is labelled, its numeric ID is its durable identity. Do not silently
assign a different ID to a labelled card.

## 2. List known cards

Show the compact removable-media register:

```bash
organiseMyVideo camera inventory --list
```

Restrict the register to one card:

```bash
organiseMyVideo camera inventory --list --card 4
```

Show the detailed latest inventory for one card:

```bash
organiseMyVideo camera inventory --list --full --card 4
```

The compact register includes:

- `Card` — durable numeric card ID.
- `Status` — current derived lifecycle state.
- `Type` — physical media type, for example `sd` or `usb`.
- `Size` — marketed capacity where known.
- `Camera` — latest known camera identity where it is meaningful to display it.
- `Location` — current stored physical/use location.
- `Last inventory` — most recent stored inventory snapshot time.

For a card marked `missing`, the compact list does not present the previous camera
association as though it were current. The full view still retains the historical
inventory information.

## 3. Card status meanings

Status is derived from location, latest inventory content, and successful import
history.

| Status | Meaning |
| --- | --- |
| `in use` | A normal current location is set, for example a car, camera, drawer, or kit bag. |
| `missing` | Location is explicitly `missing`. |
| `empty` | No active location is set and the latest inventory contains no content. |
| `to archive` | No active location is set, content exists, and the latest inventory snapshot has not yet been successfully imported. |
| `available` | No active location is set and the latest inventoried content has already been successfully archived/imported. The card is available for reuse. |

`available` does not mean that the card has never contained files. It means its latest
known content has already been dealt with and the medium may be reused.

## 4. Set or inspect a card location

Show the current location:

```bash
organiseMyVideo camera inventory --card 4 --location
```

Set a location in dry-run mode:

```bash
organiseMyVideo camera inventory --card 4 --set-location "Car JSZ5017"
```

Persist it:

```bash
organiseMyVideo camera inventory --card 4 --set-location "Car JSZ5017" --confirm
```

Mark a card as missing:

```bash
organiseMyVideo camera inventory --card 4 --set-location missing --confirm
```

A normal location implies `in use`. `missing` is treated specially.

When a card is removed from its device and no longer has a current location, its
status should be based on its content/import state: `empty`, `to archive`, or
`available`.

## 5. Preview a camera import

Camera import is separate from inventory. Inventory identifies and describes the
medium; import copies supported camera media into the archive.

Preview an import:

```bash
organiseMyVideo camera import -s /media/andy/CARD --card 4
```

`--card 4` is an identity assertion. It does not assign card 4 to an unlabelled
medium. Register the card with `camera inventory` first.

The dry-run shows how many files would be copied, excluded, or are already present.

## 6. Archive/import the media

Run the confirmed import:

```bash
organiseMyVideo camera import -s /media/andy/CARD --card 4 --confirm
```

The importer:

- preserves source files on the card;
- copies supported media to the configured archive destinations;
- verifies copied files;
- handles filename collisions without overwriting different content;
- records every considered asset in a JSON import manifest;
- links the successful import to the relevant card inventory snapshot where possible.

A successful import of the latest inventory snapshot allows a card with no active
location to become `available`.

## 7. View import history for a card

Show all confirmed camera imports:

```bash
organiseMyVideo camera import --list
```

Show imports associated with card 4:

```bash
organiseMyVideo camera import --list --card 4
```

This gives the per-import summary, including date, copied count, already-present
count, failures, and source.

## 8. See the actual files archived for a card

Use the full history view for one numbered card:

```bash
organiseMyVideo camera import --list --card 4 --full
```

The full view reads the recorded import manifests and shows each import followed by
its per-file audit. For every asset it displays the archive destination, original
source path, and result such as `copied`, `already present`, or `failed`. Failed
records also display their recorded error.

`copied` and `already present` both count as successfully archived content:

- `copied` means the importer copied and verified the file;
- `already present` means identical content was already at the chosen archive
  destination, so another copy was unnecessary.

The underlying JSON manifests remain under:

```text
~/.local/state/organiseMyVideo/cameraImports/
```

For advanced inspection, the same records can still be queried directly. For
example, to print source, destination, and outcome for card 4:

```bash
jq -r '
  select(.source.cardId == 4)
  | .assets[]
  | [.sourcePath, .destinationPath, .outcome]
  | @tsv
' ~/.local/state/organiseMyVideo/cameraImports/camera-import-*.json
```

The manifest audit is authoritative for what an import attempted and where each
asset was intended to go.

## 9. Re-inventory after clearing or reusing a card

After files have been removed from a card, inventory it again so the catalogue knows
its current content state:

```bash
organiseMyVideo camera inventory -s /media/andy/CARD --card 4 --confirm
```

If the latest inventory now contains no content and the card has no current location,
its status becomes `empty`.

If the card is assigned to a device/location again, set that location and its status
becomes `in use`.

## 10. USB sticks

USB storage uses the same numbered removable-media register and ID space. Its
physical media `Type` is `usb` rather than `sd`.

USB inventory does not make a USB stick a camera source and does not cause camera
import to run. Camera import remains restricted to recognised camera-media layouts.
