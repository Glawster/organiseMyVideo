# Camera media import

## Status

Agreed development plan, recorded on 2026-09-02. The camera importer described
here is not yet implemented. Delivery is governed by
[REQ-004](../project/requirements/features/004-cameraMediaImport.md) and
[ADR-006](../project/adr/006-cameraImportArchitecture.md).

## Outcome

`organiseMyVideo` will import original GoPro and DJI camera media from an SD
card or copied card directory into the existing video archive. The feature
will be implemented as importable Python modules and exposed through the
package's object/action command-line interface.

The initial archive destinations are:

```text
/mnt/myVideo/Video/GoPro/YYYY/MM/DD/
/mnt/myVideo/Video/Drone/YYYY/MM/DD/
/mnt/myVideo/Video/Dashcam/YYYY/MM/DD/
```

New GoPro and DJI imports use the same nested capture-date convention. For
example, media captured on 20 April 2024 is stored beneath
`Drone/2024/04/20/`. Existing GoPro date-named directories and files in the
flat `Drone` directory will be brought into the same structure through the
separate, audited `camera migrate` action described below.

## Observed media layouts

The current GoPro archive is mostly organised into `YYYY-MM-DD` directories.
Some older directories contain an additional camera-model directory, while
the archive root also contains legacy AVI and unrelated project/audio files.
The importer must not reorganise this legacy content as part of ingestion.

The inspected removable drive contains both supported camera layouts:

```text
DCIM/
├── 100GOPRO/
│   ├── GH010111.MP4
│   ├── GL010111.LRV
│   └── GH010111.THM
├── 101MEDIA/
│   ├── DJI_0021.MP4
│   └── DJI_0021.SRT
└── Movie/
    ├── 2024_0418_090000_0001F.MP4
    └── Parking/
        └── 2024_0418_100000_0002F.MP4
```

Dash-cam cards also appear as BlackVue-style `Record/YYYYMMDD_HHMMSS_NF.mp4`
trees, Garmin-style `DCIM/100EVENT` folders, and Transcend DrivePro 250 cards:

```text
DP250/
├── N_VIDEO/
│   └── 2026_0513_120237_012.mp4
├── P_VIDEO/
├── EVENT/
└── SYSTEM/
```

The clip name is `YYYY_MMDD_HHMMSS_sequence.mp4`. Older DrivePro cards may
use hyphenated `N-Video` folders and `.MOV` / `.NMEA` files.

Inventory classifies those as `dashcam` and skips `SYSTEM`. Import stores
originals under `Dashcam/YYYY/MM/DD/`.

GoPro `.LRV` files are low-resolution previews and `.THM` files are
thumbnails. They are not archive originals and will not be imported by
default. An explicit option may retain them when an exact card copy is wanted.
DJI `.SRT` files contain telemetry/subtitle information associated with the
same-stem MP4 and will be retained beside that MP4.

The importer ignores operating-system, synchronization, and camera database
content such as `._*`, `_gsdata_`, `MISC`, `LOST.DIR`, `System Volume
Information`, database files, and log files.

## Python module boundary

Camera import is a pure Python application feature. Planning, metadata
interpretation, companion grouping, duplicate detection, copying, verification,
and manifest generation must be callable through Python APIs without parsing
console output or starting the CLI.

The production runtime must not require the `exiftool` or `ffprobe` executables
and must not invoke shell commands. JPEG EXIF data will be read through a
Python library. The limited ISO Base Media File Format fields needed from MP4
files, including creation time, will be read through a Python dependency or a
small internal parser with focused tests. Filesystem modification time is a
documented last-resort fallback.

A proposed package decomposition is:

```text
organiseMyVideo/
├── camera.py
├── cameraDetect.py
├── cameraMetadata.py
├── cameraPlan.py
└── cameraImport.py
```

The public Python surface should use typed records such as `CameraAsset`,
`CameraAssetGroup`, `ImportOperation`, `ImportPlan`, and `ImportResult`.
Detection and planning must not mutate the filesystem. File mutations must be
routed through the project's central filesystem-safety boundary when that
boundary is delivered.

## Command-line interface

Card cataloguing against a numeric SD-card ID is a separate action,
`camera inventory`, described in
[Camera card inventory](cameraInventory.md) and
[REQ-009](../project/requirements/features/009-cameraCardInventory.md). Import
does not write that catalogue, and inventory does not copy archive files.

The canonical interface uses nested object/action subcommands:

```bash
$ python -m organiseMyVideo camera import /media/andy/7000-8000
$ python -m organiseMyVideo camera import /media/andy/7000-8000 --confirm
```

The first form builds and displays a dry-run plan. The second form copies and
verifies the planned media.

Existing archives use a separate action:

```bash
$ python -m organiseMyVideo camera migrate
$ python -m organiseMyVideo camera migrate --confirm
```

Migration defaults to a dry-run plan covering the configured GoPro and Drone
roots. `--confirm` authorizes only the conflict-free operations shown by the
plan. Import never triggers archive migration implicitly.

The `camera` parser owns camera-related actions, and `import` owns the source
argument and import-specific flags. Its handler constructs and calls the same
Python application service available to library users; domain behaviour must
not be implemented in `__main__.py`.

The sibling `migrate` action calls a Python archive-migration service using the
same metadata, planning, collision, verification, and manifest components.

Candidate import flags are:

```text
--camera auto|gopro|dji
--gopro-destination PATH
--drone-destination PATH
--include-gopro-companions
--verify sha256|size
--manifest PATH
```

Automatic detection is the default. Dry-run remains the default and
`--confirm` remains the only way to authorize archive changes. The public help
and root README must be updated when the command is implemented.

## Import rules

The importer will:

1. Accept the card root, `DCIM`, or an individual supported camera directory.
2. Recognise `*GOPRO` directories, DJI-named media in `*MEDIA` directories,
   and dash-cam trees such as `Movie`, `Record`, and `100EVENT`.
3. Identify capture date from embedded metadata, with a clearly reported
   fallback to filesystem time.
4. Preserve original camera filenames.
5. Put GoPro originals into the matching `GoPro/YYYY/MM/DD/` directory.
6. Put DJI originals and same-stem SRT files into the matching
   `Drone/YYYY/MM/DD/` directory.
7. Put dash-cam originals into the matching `Dashcam/YYYY/MM/DD/` directory.
8. Group GoPro chapters without joining or renaming the original MP4 files.
9. Exclude LRV and THM helpers unless `--include-gopro-companions` is supplied.
10. Report unrecognised files without importing or deleting them.

An asset with no trustworthy date is not imported or migrated automatically.
It remains at its source and is reported for manual review. This preserves the
required `YYYY/MM/DD` archive structure without inventing a capture date.

## Duplicate and collision policy

Filenames alone are not proof of identity. Planning distinguishes:

- missing destination: plan a copy;
- identical existing content: report and skip;
- same destination name with different content: report a conflict and do not
  copy; and
- incomplete companion group: retain the original and report the missing
  companion.

The initial implementation must not create names such as `DJI_0021 (2).MP4`
automatically because camera sequence names and companion relationships are
meaningful. Content verification defaults to SHA-256, with size-only checking
available only as an explicit faster policy.

## Safe copy workflow

Camera ingestion copies rather than moves. For each planned file, confirmed
execution will:

1. validate the resolved source and destination paths;
2. check that the destination has sufficient free space;
3. copy to a temporary file in the destination directory;
4. preserve applicable timestamps;
5. verify the completed copy using the selected policy;
6. atomically rename the verified temporary file to its final name; and
7. record the result in an import manifest.

The source card is never modified by the import command. Card cleanup or
formatting is out of scope and would require a separate command, requirement,
and explicit confirmation model.

## Import manifest

Each confirmed run records a JSON manifest under the application configuration
directory by default. It includes the import identifier, source volume,
detected camera and model, original relative path, metadata-derived capture
time, destination, file size, SHA-256 digest, companions, and result.

Results distinguish copied, already present, conflict, ignored, and error.
Manifests make repeated imports auditable and provide evidence that originals
were verified before the operator formats a card.

## Existing archive migration

Migration brings supported existing media beneath both archive roots into the
canonical hierarchy:

```text
GoPro/2023-10-06/GH010045.MP4
    -> GoPro/2023/10/06/GH010045.MP4

Drone/DJI_0004.MP4
    -> Drone/YYYY/MM/DD/DJI_0004.MP4
```

For a valid existing GoPro `YYYY-MM-DD` directory, the directory name is a
planning hint but embedded capture metadata remains the authority for each
asset. Flat DJI files are dated from embedded metadata. Matching DJI SRT files
move with their MP4, and any deliberately retained GoPro LRV/THM files move
with their original.

Migration does not guess when the date cannot be established, does not move
unrelated files from the GoPro root, and does not overwrite collisions. Such
items are reported for manual review. Empty legacy directories may be removed
only after every contained supported asset has been successfully moved and
verified; non-empty directories are retained.

Each confirmed migration writes a manifest containing the old and new paths,
metadata source, digest, verification result, and any conflicts. A manifest
must contain enough information to construct a checked rollback plan. Rollback
is not performed automatically and must not overwrite files created after the
migration.

## Configuration

The existing application configuration may be extended as follows:

```json
{
  "storage_locations": {
    "gopro": "/mnt/myVideo/Video/GoPro",
    "drone": "/mnt/myVideo/Video/Drone",
    "dashcam": "/mnt/myVideo/Video/Dashcam"
  },
  "camera_import": {
    "include_gopro_companions": false,
    "verification": "sha256"
  }
}
```

Defaults may reflect the current archive, but Python domain logic and tests
must not depend on these real mounted paths.

## Delivery plan

### Increment 1: inventory and planning

- Add camera/card detection.
- Add pure Python JPEG and MP4 capture-time readers.
- Group original and companion files.
- Produce an `ImportPlan` and dry-run CLI report.
- Make no archive or card changes.

### Increment 2: verified import

- Add configuration-backed destinations.
- Add duplicate and conflict analysis.
- Add temporary-copy, verification, and atomic-finalization behaviour.
- Add JSON manifests and confirmed-run summaries.

### Increment 3: archive migration

- Reuse detection and metadata services to inventory existing GoPro and Drone
  archives.
- Report misplaced, duplicated, undated, or incomplete assets.
- Add a separately planned and confirmed `camera migrate` action.
- Move conflict-free assets into `YYYY/MM/DD`, preserve companions, verify
  results, and write a rollback-capable manifest.
- Leave ambiguous and unrelated legacy content untouched for manual review.

## Verification

Tests use temporary directories and small synthetic fixtures rather than the
real card or `/mnt/myVideo`. They cover card-root and direct-directory
detection, mixed GoPro/DJI input, date precedence and timezone handling,
GoPro chapter and helper association, DJI SRT association, ignored artifacts,
duplicate content, conflicting content, dry-run immutability, successful
verified copy, interrupted-copy cleanup, manifest output, and execution through
`python -m organiseMyVideo camera import`.

Migration tests additionally cover conversion from `YYYY-MM-DD`, dating flat
DJI media, mixed-date legacy directories, companion moves, ambiguous dates,
non-media root files, collisions, empty-directory cleanup, rollback-plan data,
and execution through `python -m organiseMyVideo camera migrate`.

The Python application service must also be tested directly to demonstrate
that camera import works independently of the command-line adapter.
