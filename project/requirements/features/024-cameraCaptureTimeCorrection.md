# 023: Camera capture-time correction

## Status

Planned

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
under REQ-021. This requirement defines the `organiseMyVideo` policy and
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
  evidence in application history/catalogue records.
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
- Keep embedded EXIF/MP4 metadata unchanged initially. The application-level
  corrected timestamp is authoritative for catalogue/path policy, while media
  metadata rewriting remains a separate future decision.
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
- Rewriting embedded EXIF, QuickTime, or MP4 timestamps in this requirement.
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
13. Embedded EXIF/MP4 timestamps remain unchanged by this requirement.
14. Tests cover positive and negative offsets, leap years, day/month/year
    rollover, multi-day sessions, duplicate destinations, differing-content
    conflicts, and correction-scope isolation across reuse of one `cardId`.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-021: Shared media processing platform](021-sharedMediaProcessing.md)
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

## Traceability

- Shared implementation: pending in `organiseMediaStudio`.
- OMV correction planning/execution: pending.
- Card 2 production correction: pending implementation and dry-run review.
- Pull request: pending.

## Change history

- 2026-09-17: created — define fixed-offset camera-clock correction and the
  card 2 default-clock use case, preserving raw timestamps and relative timing
  while correcting the session to the user-confirmed 2018 timeline.
