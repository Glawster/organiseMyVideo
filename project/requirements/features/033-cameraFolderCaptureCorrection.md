# 033: Camera folder capture-time correction

## Status

Completed

## Outcome

As an archive operator, I need to correct capture chronology in an existing
folder that has no import history, using the same safe preview and verified
relocation workflow as import-based camera corrections.

## Context

REQ-024 provides correction from a confirmed import manifest. Historical camera
folders may never have passed through OMV import. They still contain raw camera
timestamp evidence from which an operator can establish a trusted fixed offset.
This extension records observed folder evidence without inventing an import.

## Scope

- Add `camera correct-time --source FOLDER` as an alternative to
  `--import-manifest`; require exactly one of these selectors.
- Retain `--root`, `--reference`, `--actual`, `--reason`, repeatable
  `--file` and default preview with confirmed execution via `-y/--confirm`.
- Scan supported original media recursively using shared existing metadata and
  precise filename readers; never use filesystem timestamps as clock evidence.
- Resolve reference/selected filenames relative to the source folder, include
  same-stem companions, and show retained unsupported/unselected paths.
- Permit source folders outside the destination root. Require existing roots,
  reject symlinks and path traversal, and reject a destination root within or
  equal to the source so the output tree cannot become the input scope.
- Record an explicit folder scope, selected files, SHA-256 hashes, raw timestamp
  evidence/source and correction provenance in the existing catalogue/journal.
  Do not add fictitious import/card/snapshot records.
- Freeze the scope on confirmation. Retries use its saved evidence; newly added
  files cannot silently inherit an unfinished correction. After completion,
  a fresh preview may select current or newly added media without reserving the
  old source path. Only unfinished overlapping transformations block new work;
  completed records remain immutable provenance under REQ-024.
- Reuse exact shared offset arithmetic, corrected `YYYY/MM/DD` destinations,
  hash conflict checks, no-overwrite copy publication, all-destination
  verification before source removal, per-file checkpoints and interruption
  recovery from REQ-024.
- Correct embedded capture metadata on verified copies using REQ-024's
  copy/write/readback/dual-hash checkpoints; preserve originals on any
  metadata-write or verification failure.
  Remove only empty source subdirectories; retain the selected source root.
- Persist effective timestamps for subsequent organisation and preserve the
  existing import-based CLI and data contract.

## Companion policy

MP4, MOV, JPEG and CR3 files are originals. Same-stem SRT, NMEA, XML, THM and LRV
helpers and PNG/WebP artwork follow an unambiguous original timestamp. Their independently observed
timestamps and sources, when available, are retained separately from the
inherited correction basis. An orphan or ambiguously dated helper blocks the
selected scope. The reference must be an original. Unknown files remain in place.

Original JPEG/MP4/MOV and JPEG THM/MP4 LRV metadata is rewritten on copies.
SRT/NMEA/XML sidecars and PNG/WebP artwork follow the original's corrected
location and mtime without reinterpreting their contents. Formats without a safe
writer (currently CR3) block confirmation rather than claiming a catalogue-only
correction. Original and corrected embedded values and both
SHA-256 identities remain in the folder journal. If original mtime is earlier
than corrected capture time, shift it by the correction offset; otherwise retain
it. Journal original/resulting mtime only when changed. Do not explicitly set
atime or ctime.

## Out of scope

- Shell Tab completion (REQ-032).
- Guessing actual times or transcoding.
- Automated rollback or changing an already-recorded correction rule.
- Automatically applying offsets to future contents of a folder or reused card.

## Acceptance criteria

1. The user's folder-based command previews original/corrected dates, paths,
   offset, affected count and retained files without any archive/state writes.
2. A real MP4 reference dated 2015 maps to a trusted 2018 time; elapsed intervals
   are preserved across multiple files and day boundaries.
3. Confirmed execution outside or within the archive root relocates verified
   files into `YYYY/MM/DD` with independently readable corrected embedded
   timestamps, unchanged media essence and both hashes journalled.
4. Catalogue/journal evidence distinguishes folder scopes from imports and
   retains exact selected filenames, hashes, timestamp sources and reference.
5. Identical destinations are verified; different-content or intra-plan
   collisions block the whole scope without overwriting.
6. Missing timestamps, invalid anchors, unsafe paths, orphan/ambiguous helpers
   and unreadable or changing files fail safely with clear diagnostics.
7. Partial-copy and finalisation interruptions retain usable copies and allow
   the same command to resume. Completed repeats do not compound the offset.
8. Files added after preview or confirmation cannot be silently incorporated;
   explicit subsets include their companions but exclude unrelated files.
9. Corrected timestamps remain authoritative for later camera organisation.
10. Existing import correction, catalogue/history, CLI and metadata tests pass;
    help and user documentation explain both scope modes.

## Dependencies and decisions

- [REQ-024](024-cameraCaptureTimeCorrection.md)
- [ADR-006](../../adr/006-cameraImportArchitecture.md)
- [ADR-011](../../adr/011-cameraCaptureCorrectionJournal.md), extended to explicit
  folder evidence and separate source/destination safety boundaries.

## Verification

| Behaviour | Unit | Integration | Golden | CLI |
| --- | --- | --- | --- | --- |
| Folder metadata through verified relocation | | Yes | Real generated MP4/JPEG | Yes |
| Selection, provenance and later organisation | Yes | Yes | Raw byte/timestamp evidence | Yes |
| Conflicts, changed scope and interruption recovery | Yes | Yes | | Yes |

Run focused folder/import correction tests, the full pytest suite, formatting,
linting, markup checks, `git diff --check` and `manageProject --check`.

## Change history

- 2026-09-28: created — operator requested `camera correct-time --source` for
  existing media folders without prior import history.

## Correction CLI contract

The correction interface uses `-s/--source`, `-r/--root`, `-R/--reference`,
`-a/--actual`, repeatable `-f/--file`, `--reason` and `--import-manifest`.
Exactly one scope selector is required. Keep `--reason` explicit and required
for the correction audit record. Reject obsolete `--reference-file` and
`--actual-at` options; they are not aliases.

Help describes `-R, --reference FILE` as “file whose recorded capture time
provides the correction anchor” and `-a, --actual DATETIME` as “actual capture
date/time of the reference file”. Existing preview and confirmation rules apply.
