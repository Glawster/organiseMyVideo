# 024: Camera capture-time correction

## Status

Completed

## Outcome

As a media-library operator, I need to correct camera capture times when a
camera clock was left at an incorrect default date/time so that archived media
is catalogued and stored under its real capture dates without losing the
original metadata evidence.

## Context

Camera timestamps can be syntactically valid but factually wrong. In the
motivating case, camera card 2 contains GoPro media recorded while the camera
clock had never been set. The files therefore carry dates beginning in January
2015 even though the user-confirmed real recording session began on **Saturday
25 August 2018 at 19:00**.

The clock appears to have advanced normally while recording. The useful
relationship between file timestamps is therefore their elapsed time, not their
absolute 2015 date. A fixed offset derived from a trusted recorded/actual
reference pair can preserve those intervals while deriving corrected capture
times.

A correction must not become a permanent property of `cardId=2`. Removable
cards are reusable and may later contain media from a different camera or from
a correctly configured clock. Correction scope belongs to a particular import,
inventory snapshot, or explicitly selected capture session/range.

The generic arithmetic and provenance model belong in `organiseMediaStudio`
under REQ-022. This requirement defines the `organiseMyVideo` policy and
operator workflow around that shared primitive.

## Scope

- Add a dry-run-first camera capture-time correction workflow.
- Allow an operator to define a correction from one trusted pair:
  - the timestamp recorded by the camera for a known reference point; and
  - the corresponding actual date/time.
- Calculate one signed fixed offset from that pair and apply it consistently to
  all selected files in the bounded correction scope.
- Preserve each file's original/raw capture timestamp and timestamp source.
- Record the corrected capture timestamp separately; never replace the raw
  evidence in historical import/correction records. The effective catalogue
  index may advance to a later transformation.
- Preserve exact elapsed intervals between files when applying a fixed offset.
- Scope a correction to an explicit import, snapshot, session/range, or selected
  file set; do not apply it automatically to every historical/future use of the
  same physical card.
- Use corrected capture time for catalogue date and proposed `YYYY/MM/DD`
  archive placement.
- Before any filesystem change, show a dry-run containing at least:
  - source/current path;
  - raw capture timestamp;
  - corrected capture timestamp;
  - current archive date/path;
  - proposed corrected archive date/path;
  - correction offset and reason;
  - duplicate/conflict outcome where the proposed destination exists.
- Reuse existing hash-based duplicate/conflict rules. Never overwrite a
  different-content destination merely because the corrected date points to the
  same path.
- On confirmation, move/rename only after the correction plan and destination
  checks succeed, verify resulting content, and remove empty source directories
  only when safe.
- Write an auditable correction/migration manifest containing the original and
  corrected timestamps, correction rule/provenance, old/new paths, file hashes,
  results, and enough information for a checked rollback plan.
- Confirmed correction must write corrected embedded capture metadata on a
  verified destination copy. Independent readers must see corrected dates
  without access to the OMV catalogue. Preserve the original embedded values in
  the journal, not as the active capture metadata of the corrected media.
- Provide visible progress for scans/hashing/correction planning so large
  sessions do not appear stalled.

## Card 2 reference case

The first production use case is the latest known import of card 2.

Known facts:

```text
cardId:             2
problem:            camera clock left at default/incorrect date
recorded dates:     beginning 2015-01-01 and advancing normally
actual session:     Saturday 2018-08-25 19:00
correction method:  fixed-offset
scope:              latest applicable card-2 import/session only
```

The exact offset must be calculated from the recorded timestamp of the chosen
reference file and the user-confirmed actual reference time. The implementation
must not assume that `2015-01-01 00:00:00` itself corresponds to 19:00 unless
that is what the selected reference file actually records.

For example, if the selected reference file recorded `2015-01-01 12:34:20` and
that file is confirmed to have been captured at `2018-08-25 19:00:00`, the
system derives the signed offset from those two values and applies that exact
offset to the rest of the selected session.

## Out of scope

- Guessing the actual date/time without a trusted reference.
- Treating a timezone conversion as equivalent to a wrong-camera-clock
  correction.
- Permanently attaching a correction to a physical card ID.
- Applying one correction across unrelated imports/snapshots without explicit
  operator selection.
- Overwriting different-content destination files.
- Transcoding or changing audiovisual/image content to correct timestamps.
- Deleting source media merely because a corrected destination path can be
  calculated.

## Acceptance criteria

1. Given a raw recorded timestamp and a trusted actual reference timestamp,
   when a correction rule is created, then a signed fixed offset is calculated
   exactly and stored with its provenance.
2. Given multiple selected files whose camera clock advanced normally, when the
   fixed offset is applied, then the elapsed interval between every pair of
   files remains unchanged.
3. Given a corrected file, then both `rawCaptureAt` and `correctedCaptureAt` are
   available, along with timestamp source, correction method, signed offset,
   reference timestamps, reason, and correction scope identity.
4. Given card 2's latest applicable import/session, when the operator supplies
   the user-confirmed actual reference time of `2018-08-25 19:00:00`, then the
   dry-run maps the selected 2015 timestamps into the corresponding 2018
   timeline without modifying files.
5. The card 2 correction is associated with the selected import/snapshot/session
   and is not automatically applied to another use of card 2.
6. Given a corrected timestamp changes the archive day, when planning runs,
   then the proposed destination uses the corrected `YYYY/MM/DD` hierarchy.
7. Given a proposed corrected destination already contains identical content,
   the item is reported as a duplicate/already-present case; given differing
   content, it is reported as a conflict and neither file is overwritten.
8. Dry-run is the default and performs no archive, catalogue, manifest, or
   embedded-media mutation.
9. A confirmed correction/migration writes an auditable manifest with raw and
   corrected timestamps, rule/provenance, old/new paths, hashes and outcomes.
10. A confirmed filesystem relocation verifies destination content before the
    previous path is removed.
11. Empty legacy directories may be removed only after all applicable files
    have been successfully handled and the directory is genuinely empty.
12. The correction workflow reports visible progress during potentially long
    scanning and hashing operations.
13. Confirmed execution writes JPEG DateTimeOriginal, CreateDate and ModifyDate,
    and MP4 QuickTime CreateDate/ModifyDate plus every present track/media
    creation/modification timestamp. Independent metadata readback verifies
    absolute corrected values before any source removal.
14. Tests cover positive and negative offsets, leap years, day/month/year
    rollover, multi-day sessions, duplicate destinations, differing-content
    conflicts, and correction-scope isolation across reuse of one `cardId`.

15. Global `--debug` changes logging only; camera help and command dispatch use
    the same public hierarchy with or without the flag.
16. GoPro QuickTime integer clock evidence remains timezone-naive even when
    ffprobe renders it with `Z`. Explicit stored timezone evidence is preserved;
    genuine naive/aware mismatches remain errors and report both reference
    timestamps with their timezone/offset states. Filesystem mtime is not used
    to derive the correction.

## Real-world GoPro acceptance

`GOPR4150.MP4`: raw `2015-01-04T07:42:46`, actual `2018-08-22T18:00:00`,
exact offset **+1326 days, 10:17:14**. QuickTime CreateDate/ModifyDate and all
Track1/2/3 TrackCreateDate, TrackModifyDate, MediaCreateDate and MediaModifyDate
start at that raw value and must read `2018:08:22 18:00:00` after confirmation.
`G0044159.JPG` starts at `2015:01:04 09:48:48`; its three EXIF date fields must
read `2018:08:22 20:06:02`. Media essence must remain unchanged.

Before mutation, persist original embedded timestamps, corrected values,
original SHA-256, offset, reason, anchor and rule ID. Copy the
original, verify byte identity, write metadata on the copy only, read every
expected field back, verify, calculate and journal destination SHA-256, then
publish and remove the original only after all selected destinations verify.
Original and corrected hashes are distinct identities; equality is not required.
A write or verification failure retains originals. Retries distinguish untouched
originals, verified raw copies and metadata-verified corrected copies. Absolute
writes and frozen input evidence prevent an accidental second offset application
when resuming the same operation; later operations use new current evidence.

Filesystem mtime follows the final operator rule: if original mtime is earlier
than corrected capture time, apply the same signed correction offset to mtime;
otherwise preserve it. Record changed original/resulting mtime pairs when
OMV changes it; retain observed before/after filesystem state for transformation
audit and stale-preview validation. This moves an old 2015 camera-clock mtime while retaining a
genuine later 2026 edit. Preserve sub-second filesystem precision and never
replace mtime with capture time. Naive capture times use the host local zone
only when comparing with a POSIX filesystem instant; explicit offsets define
their instant. Do not deliberately set atime or inode ctime. Normal kernel
updates caused by reads/writes are unavoidable and are not camera-time correction
operations.

Tests must independently inspect JPEG and three-track MP4 output, exercise
write/readback failures, copied/verified/published recovery, dual-hash journalling,
repeat idempotency, conditional mtime shifting/preservation and no explicit atime/ctime writes.

## Dependencies and decisions

- [REQ-033: Folder correction without import history](033-cameraFolderCaptureCorrection.md) extends this workflow to observed folder evidence.

- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-022: Shared media processing platform](022-sharedMediaProcessing.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-010: Use organiseMediaStudio as the shared media-processing boundary](../../adr/010-sharedMediaProcessingBoundary.md)

## Verification

- Shared-unit tests for fixed-offset arithmetic and provenance in
  `organiseMediaStudio`.
- OMV integration tests using synthetic import/snapshot records and temporary
  archives.
- A card-2 regression fixture covering a 2015 default-clock sequence corrected
  to a session beginning `2018-08-25 19:00:00`.
- Dry-run tests proving no filesystem/catalogue mutation.
- Confirmed-run tests proving verified relocation, duplicate handling,
  conflict retention, manifest generation, and rollback evidence.
- Progress-reporting tests.
- `pytest`
- `git diff --check`

## Operator contract and acceptance detail

- `camera correct-time --import-manifest PATH --root ROOT --reference RELATIVE_PATH
  --actual ISO_DATETIME --reason TEXT` previews the selected import.
- Repeat `--file RELATIVE_PATH` for a subset, including the reference; recorded
  same-stem companions are included. Unknown companion evidence blocks a move.
- Initial import evidence must match verified media. Later transformations
  follow completed output identities and read the current reference metadata.
  Camera metadata or a precise filename timestamp and verified SHA-256 are required;
  filesystem fallback timestamps are reported as unusable evidence.
- Require a common clock basis (naive wall times or the same fixed UTC offset).
  Do not silently convert timezones or mix naive and aware timestamps.
- Any missing evidence or conflict blocks all selected files. Confirmation
  copies/verifies the entire scope before old paths are removed.
- Repeating an identical completed rule performs no writes. Partial attempts
  can resume; only unfinished overlapping transformations block new corrections.
- Persist provenance and effective timestamps in the existing media catalogue;
  export the correction journal under the existing `cameraImports` directory.
- Automated rollback is out of scope. Subsequent corrections are new transformations
  of current media and do not overwrite earlier audit records.

## Test plan

| Production behaviour | Unit | Integration | Golden | UI | Clean-room |
| --- | --- | --- | --- | --- | --- |
| Exact offset and interval preservation | Yes (shared) | Yes | Card-2 values | | Yes |
| Import evidence through correction and organisation | | Yes | JPEG/MP4 fixtures | CLI | Yes |
| Catalogue, manifests and corrected media | Yes | Yes | Independent ExifTool readback and dual hashes | CLI | Yes |
| Conflicts, companions, interrupted copies and recovery | Yes | Yes | | CLI | Yes |

## Traceability

- Shared implementation: `organiseMediaStudio.metadata.captureCorrection`.
- OMV implementation: `cameraCorrection.py`, `cameraCorrectionExecution.py`,
  `cameraCorrectionFolder.py`, `cameraCorrectionHistory.py`,
  `cameraCorrectionMetadata.py`, `cameraCorrectionStore.py`,
  `cameraCorrectionCli.py`, `cameraHistory.py`, `cameraPlan.py` and
  `cameraImport.py` under the application package.
- Tests: `tests/test_cameraCorrection.py`, `tests/test_cameraCorrectionFolder.py`,
  `tests/test_cameraCorrectionEmbedded.py`, `tests/test_cameraCli.py`,
  `tests/test_cameraHistory.py` and shared `tests/test_captureCorrection.py`.
- User guide: [Camera capture-time correction](../../../documentation/cameraCaptureCorrection.md).
- Decisions: [ADR-006](../../adr/006-cameraImportArchitecture.md),
  [ADR-011](../../adr/011-cameraCaptureCorrectionJournal.md).

## Change history

- 2026-09-17: created — define fixed-offset camera-clock correction and the
  card 2 default-clock use case, preserving raw timestamps and relative timing
  while correcting the session to the user-confirmed 2018 timeline.

- 2026-09-28: clarified the explicit import/subset CLI, matching clock basis,
  SHA-256 evidence requirements and journalled recovery contract.

## Correction CLI contract

The correction interface uses `-s/--source`, `-r/--root`, `-R/--reference`,
`-a/--actual`, repeatable `-f/--file`, `--reason` and `--import-manifest`.
Exactly one scope selector is required. Keep `--reason` explicit and required
for the correction audit record. Reject obsolete `--reference-file` and
`--actual-at` options; they are not aliases.

Help describes `-R, --reference FILE` as “file whose recorded capture time
provides the correction anchor” and `-a, --actual DATETIME` as “actual capture
date/time of the reference file”. Existing preview and confirmation rules apply.

## Repeatable, auditable transformations

Capture-time corrections are repeatable, auditable transformations. A completed
correction SHALL NOT prevent a subsequent correction of the resulting media.
Each correction SHALL operate on the media's current metadata and filesystem
state and SHALL create a new immutable audit record containing sufficient
before-and-after evidence to reconstruct the transformation history. Persistent
correction records SHALL provide provenance and recovery information, not
permanently reserve a source path or prevent future correction.

### Acceptance criteria for subsequent corrections

- After completion, another correction may change the resulting media again,
  including in place, backwards in time, or to another archive day. Calculate
  its offset from current capture metadata, not the first correction's anchor.
- Every new transformation has a distinct operation/rule identity and retains
  input/output paths, hashes, embedded tags, capture times, filesystem evidence,
  offset, reason, reference evidence and links to verified predecessor outputs.
  Earlier completed database records and exported manifests remain unchanged.
- Import-scoped corrections follow recorded transformation identities to current
  media and read that media afresh. Import manifests remain historical evidence.
- Folder scopes may be reused for new media after completion. A fresh preview
  snapshots current files; a path alone neither applies an old offset nor blocks
  a new correction.
- Identical retries with unchanged verified output remain no-ops. Interrupted
  transformations retain frozen evidence and resume the same operation; new
  overlapping operations wait for recovery. Stale previews, changed input state,
  and different-content destination collisions remain blocked.
- Regression tests cover successive folder/import corrections, same-path updates,
  immutable history, reused sources, current effective catalogue values and
  interruption/recovery during a second correction.
