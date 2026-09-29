# Camera capture-time correction

## Review the evidence

Use `organiseMyVideo camera history --card 2` to find the relevant confirmed
import manifest and inspect its asset `relativePath`, `captureAt`, `dateSource`
and destination paths. `camera show --card 2` and `camera history --check` help
identify suspicious dates and missing or moved archive files. OMV does not guess
whether a syntactically valid timestamp is historically wrong.

Choose a known reference file and independent evidence of its actual capture
time. The correction applies one precise signed offset to the selected import,
retaining intervals across leap years and day/month/year boundaries. It never
becomes a permanent setting on the card.

## CLI options

Use `-s/--source`, `-r/--root`, `-R/--reference`, `-a/--actual` and
repeatable `-f/--file`. `--import-manifest` selects an import instead of a folder.
`--reason` is required and explicit because it forms part of the correction audit
record. Reference and selected file paths are relative to the source or manifest.

## Preview

For a reference JPEG with a naive recorded timestamp of
`2015-01-01T12:34:20`, whose event evidence establishes
`2018-08-25T19:00:00`:

```bash
organiseMyVideo camera correct-time \
  --import-manifest /path/to/camera-import-session.json \
  -r /mnt/myVideo/Video/GoPro \
  -R DCIM/100GOPRO/G0010001.JPG \
  -a 2018-08-25T19:00:00 \
  --reason 'Event photograph confirms this reference frame at 19:00'
```

Use the exact `relativePath` from the chosen manifest. A manifest imported from
inside `100GOPRO` may use just `G0010001.JPG`. The command reads the recorded
anchor from that verified record for the first correction; subsequent corrections
follow the transformation history and read the current media. It does not assume
the camera started at midnight.
QuickTime movie-header timestamps are integer clock values with no stored
UTC offset. Although ffprobe renders these with `Z`, the shared metadata reader
preserves the stored clock as timezone-naive evidence, matching
[ExifTool's default QuickTime policy](https://exiftool.org/TagNames/QuickTime.html).
Use a naive `--actual` for that evidence. Explicit timezone-bearing text tags
remain aware and require the same fixed offset on `--actual`. OMV performs no
implicit timezone conversion; genuinely mixed naive/aware evidence is rejected.
Mismatch errors show both reference timestamps and their timezone/offset states.
Existing import manifests remain the recorded evidence for manifest-scoped work.

The preview lists the reference pair, signed offset, reason, affected count,
raw and corrected times, current and proposed paths, duplicates and conflicts.
Corrected dates use `YYYY/MM/DD`, for example `2018/08/25/G0010001.JPG`.
No archive, catalogue or manifest writes occur during preview.

By default the scope is the entire selected import. Repeat `--file RELATIVE_PATH`
to select a bounded subset; the reference must be included. Recorded same-stem
companions are included automatically. Every selected archive path must be under
`--root`, which is the camera-specific directory immediately above the date
hierarchy (for SLR media, the appropriate `By Date` root). For a mixed-camera
import, select the files belonging to one archive root explicitly.

## Correct a folder without import history

Use `--source` instead of `--import-manifest` for an existing media folder:

```bash
organiseMyVideo camera correct-time \
  -s /tmp/omv-024-test2/04 \
  -r /tmp/omv-024-archive2 \
  -R GOPR4150.MP4 \
  -a 2018-08-22T18:00:00 \
  --reason "Correct for GoPro incorrect clock at time of recording"
```

This is a preview. Add `-y` to the same command after reviewing it. Both source
and destination root must exist. The source may be outside or inside the archive
root; the destination root must not equal or lie beneath the source, so the
output tree cannot become the scanned input.

The folder is scanned recursively for MP4, MOV, JPEG and CR3 originals. Reference
and repeatable `--file` arguments are paths relative to that folder, for example
`session/GH010001.MP4`. An explicit subset includes same-stem originals/helpers.
SRT, NMEA, XML, THM, LRV and PNG/WebP artwork follow an unambiguous same-stem
original timestamp. Any independently observed helper timestamp is retained
separately as `observedCaptureAt`, alongside `timestampEvidencePath` identifying
the original used as its correction basis. An orphan or ambiguously dated helper
blocks correction. Unsupported/unselected files are listed and remain in place.

Timestamp extraction and SHA-256 hashing establish the evidence directly from
these files. Modification times are never substituted for missing capture times.
The reference must be original media with usable capture evidence. Original JPEG
and MP4 timestamps must share the same clock basis; use explicit subsets for
mixed naive and timezone-aware originals instead of assuming a conversion.

On confirmation, the journal freezes this folder selection's filenames, hashes
and timestamp evidence. It records `scopeType="folder"`, a `scopeId`, and null
import/card/snapshot identities; it does not create an import history record.
The existing correction executor verifies all destination copies before removing
old paths. Empty source subdirectories may be removed; the selected source
folder remains available for retry commands.

Re-run the same command to review/resume an unfinished frozen selection. New
files or changed content cannot silently join that operation. Once it completes,
the folder is available for fresh corrections, including replacement media and
new additions. Every new preview reads current metadata and filesystem state;
old records do not reserve paths or apply offsets to future contents.
Requirements are in [REQ-033](../project/requirements/features/033-cameraFolderCaptureCorrection.md).

## Correct media again

To refine an earlier correction, select the resulting media with `-s` and give
its current relative reference filename with `-R`, the revised actual time with
`-a`, and a new `--reason`. Review the new preview before adding `-y`. For example:

```bash
organiseMyVideo camera correct-time \
  -s /tmp/omv-024-archive2/2018/08/22 \
  -r /tmp/omv-024-archive2 \
  -R GOPR4150.MP4 \
  -a 2018-08-22T18:05:00 \
  --reason "Refined event evidence places the reference five minutes later"
```

The new offset is five minutes from the current 18:00 capture time. A change
within the same archive day safely replaces the file at its existing path using
a verified copy. Import-scoped corrections similarly follow recorded output
identities and read the resulting media, preserving the original import manifest.
Each transformation creates a distinct audit record with before/after metadata,
paths, hashes and filesystem state, and links to verified predecessor outputs.
Completed records and their JSON manifests remain unchanged. Effective catalogue
entries describe the latest verified media; they do not restrict future changes.

## Apply and recover

Repeat the reviewed command with `-y` or `--confirm`. The full plan is displayed
before execution. Both scope modes use the same execution and recovery rules. All issues block
the selected scope, including unusable
capture timestamps, missing/changed files, unrecorded known companions, symlinks,
and different-content destinations. No alternate filename is invented for a
conflict. Filesystem modification time is not accepted as camera-clock evidence.

The command persists provenance in the existing media catalogue and writes
`cameraImports/camera-correction-<rule-id>.json` under the application state
directory. It copies and verifies all corrected destinations before deleting
old paths. Exact duplicates are verified before consolidation; unrelated files
and non-empty directories remain. Allow enough free space for this copy-first
process. The destination filesystem must support hard links for atomic,
no-overwrite publication; unsupported filesystems fail while retaining originals.
Confirmed correction writes embedded JPEG and MP4/MOV capture timestamps on
private verified copies. ExifTool or another independent reader sees the
corrected dates without OMV. Original import manifests and unselected card
contents remain unchanged. No transcoding occurs. CR3 correction currently
blocks because there is no supported safe writer; it is not silently relocated
with erroneous active metadata.

Ctrl-C exits with status 130. A copy failure retains original paths; interruption
during finalisation retains verified destination copies and journal evidence.
Re-run exactly the same command to preview and resume. An exact completed repeat
with unchanged verified outputs makes no changes and never applies the offset
twice. A different operation overlapping an unfinished correction is blocked
until recovery; completed transformations permit subsequent corrections.

The SQLite journal is authoritative if manifest export fails. Back up
`mediaCatalogue.sqlite` and `cameraImports` together. The manifest includes raw
and effective times, original source, corrected destination, original and corrected SHA-256, whether the
destination pre-existed, reference evidence, execution attempts and outcomes.
Rollback would require restoring original embedded fields as well as paths and
catalogue policy; a simple path move cannot restore original file bytes. Automated rollback is not provided by this command.

Subsequent camera organisation prefers a verified catalogue correction over raw
metadata; corrected archive copies carry that provenance forward. Original
snapshot/import timestamps stay historical evidence. Existing uncorrected media
continues to follow the normal metadata/filename/fallback rules. History checking
can report the original import destination as moved and locate its verified
corrected copy.

## Embedded timestamps, hashes and filesystem times

For the acceptance reference `GOPR4150.MP4`, the raw `2015-01-04T07:42:46`
becomes `2018-08-22T18:00:00`: an offset of +1326 days, 10:17:14. Movie
CreateDate/ModifyDate and every present track/media creation/modification date
are corrected. The same offset changes `G0044159.JPG` from `2015:01:04 09:48:48`
to `2018:08:22 20:06:02` in DateTimeOriginal, CreateDate and ModifyDate.

Confirmation journals original tags and SHA-256 before copying. It verifies
copied bytes, writes absolute corrected tags on the copy, reads them back,
verifies every expected value and journals the corrected SHA-256 before source
removal. Changed metadata intentionally changes file hashes. A failure at any
metadata-writing or verification step retains the source. Retrying reuses
verified raw/corrected copies, or rebuilds from the original if an interrupted
writer left unverified bytes. Such uncertain `.omvwork` files are retained for
inspection and listed in the journal; they are not camera media inputs.

Filesystem **mtime shifts by the same correction offset only if its original
value is earlier than corrected capture time**. Otherwise it is preserved. Thus
an old 2015 camera mtime moves with the correction, but a genuine 2026 crop/edit
mtime stays in 2026. Changed mtime pairs and observed before/after filesystem state are journalled;
mtime is never replaced with the embedded capture time. Sub-second precision
is retained.

Naive capture timestamps use the machine's local timezone only for comparing
with filesystem time; explicit offsets specify an instant. Choose the intended
local timezone before previewing. OMV does not deliberately set atime or inode
ctime. Reads and writes may still cause normal kernel updates, and ctime cannot
be preserved across file changes.

JPEG THM and MP4 LRV helpers have their embedded date fields shifted; text
sidecars and artwork retain their contents and follow the corrected location
and mtime. Preview remains read-only.

## Dependency and verification

This workflow requires ExifTool on PATH and the shared `metadata.captureTags`
and `metadata.captureCorrection` services pinned in `pyproject.toml` and its
compatibility export. ExifTool and ffmpeg are declared in the Conda environment. For development with the two sibling checkouts:

```bash
conda activate mediaStudio
python -m pip install --no-deps -e ../organiseMediaStudio
python -m pip install --no-deps -e .
pytest tests/test_cameraCli.py tests/test_cameraCorrection.py tests/test_cameraCorrectionFolder.py tests/test_cameraCorrectionEmbedded.py tests/test_cameraHistory.py
pytest
runLinter .
runLinter --markup
manageProject --check
```

The pinned shared-package commit must be published before installing that Git
dependency from a fresh machine. The local editable setup can validate both
feature branches before publication.

The governing requirement is [REQ-024](../project/requirements/features/024-cameraCaptureTimeCorrection.md).
The persistence/recovery decision is [ADR-011](../project/adr/011-cameraCaptureCorrectionJournal.md).

## Diagnostic logging

`organiseMyVideo --debug camera ...` uses the same public camera parser and
commands as `organiseMyVideo camera ...`. Debug enables diagnostic logging only.
Folder correction manifests retain the stored timestamp source and the backend
representation separately in `timestampEvidence`; filesystem mtime is not
capture-time evidence.
