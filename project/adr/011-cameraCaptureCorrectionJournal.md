# ADR-011: Journal bounded capture corrections in the media catalogue

## Status

Accepted — 2026-09-28

## Context

A confirmed camera clock correction changes embedded capture metadata,
application chronology and archive paths. Historical import/snapshot records
and the correction journal retain the original evidence.
SQLite and filesystem operations cannot share a single atomic transaction.
Failures must remain explainable and safely resumable.

## Decision

Use the neutral `organiseMediaStudio.metadata.captureCorrection` primitive for
exact arithmetic. OMV selects one confirmed import manifest, optionally narrowed
by manifest-relative filenames, with recorded same-stem companions included.
A reference file supplies the recorded anchor; the operator supplies the actual
time and reason. A physical card ID never selects future correction scope.

Persist the full correction journal in `cameraCaptureCorrection` in the existing
media catalogue. Schema version 4 identities include a unique operation token,
current input evidence, verified predecessor rule IDs, import/folder identity,
selected filenames, archive root, reference pair and reason. Retries recover the
same token. Only unfinished overlapping operations block new transformations;
completed records are immutable history, not path reservations. Preserve original manifests and card
inventory rows; capture embedded originals before rewriting destination copies.

`cameraCaptureTime` stores effective timestamps separately from raw timestamps,
keyed by import identity and relative filename. Resolve overrides only when the
archive path and SHA-256 content both match. This prevents a reused card or a
replacement file inheriting an earlier correction. Confirmed imports of corrected
archive files propagate their provenance and effective timestamps to verified
new archive paths. Existing Home Video catalogue rows are updated on correction.

Execution takes an advisory lock on the archive root, rechecks the preview,
persists the initial journal and exports a JSON manifest in the existing
`cameraImports` state directory. It then copies and verifies **all** destinations
before removing any old path. The filesystem boundary's explicit exclusive
publication option uses a hard link to publish correction copies without
replacing a destination created concurrently. A verified checkpoint precedes
source removal; every removal gets a further checkpoint. Exact duplicates can
be consolidated only after digest verification; different-content collisions
block the whole selected scope. Recorded companions remain together; unrecorded
known companions block relocation.

On failure, original files or fully verified destination copies remain usable.
The journal and manifest record old/new paths, hashes, raw/effective timestamps,
provenance, whether destinations pre-existed, execution attempts and outcomes.
Re-running the identical command resumes from this evidence without compounding
the offset. Completed repeats perform no writes. SQLite is the authoritative
journal if the JSON export fails; source removal requires the verified JSON
checkpoint as well. Both catalogue and manifests should be backed up together.

## Embedded correction checkpoints

Schema version 3 adds original/corrected embedded fields, conditional mtime
change provenance, `originalSha256` and `destinationSha256`. The historical `sha256`
field remains the original identity; catalogue path/content lookups bind to the
corrected identity. Import history reconciliation can follow the exported
original-to-corrected hash relation without rewriting import evidence.

The shared ExifTool service reads/writes grouped timestamp instances, including
all movie tracks, with QuickTimeUTC disabled. OMV owns selection, immutable
provenance, copying, filesystem times, publication and recovery. All tag writes
use absolute planned values. Missing JPEG canonical date fields are created;
unsupported formats fail closed. No transcoding occurs.

Persist provenance before copying. Copy to a private `.omvwork` path without
copying filesystem timestamps, verify original SHA-256, checkpoint `copied`,
write and read back all expected tags, set mtime, hash the corrected bytes and
checkpoint `metadata-verified`. Only after every selected copy is verified may
publication start. A pre-existing byte-identical original (including same-path
correction) is linked to a journalled recovery path before vacating its name.
Exclusive publication then installs the corrected copy. Retain original recovery
copies until final destination verification and the verified journal/JSON
checkpoint succeed. Remove originals last, checkpointing each removal.

Retries reuse a corrected copy only when its journalled corrected hash and
metadata verify; raw copies must match the original hash. An interrupted writer
without a durable corrected hash is not trusted: retain its uncertain work copy
for diagnosis and rebuild from verified original evidence. These `.omvwork`
files are not eligible camera media. Completed media is never shifted again.
Pre-existing catalogue-only correction records can be upgraded by correcting
their current output files in a new operation; their original evidence and
historical rule identities remain unchanged.

The filesystem rule compares original mtime to corrected capture time: if
mtime is earlier, apply the same signed offset; otherwise preserve it. Only an
actual change journals `originalMtimeNs` and `resultingMtimeNs`. Preserved mtime
is carried from the original to the copy. Schema version 4 additionally snapshots
before/after filesystem state for audit and stale-preview checks.
Conversion of naive capture time to a POSIX comparison uses the host local
zone; capture evidence itself remains naive. The Linux filesystem boundary uses
`utimensat` with `UTIME_OMIT` for atime. No code sets inode ctime; kernel ctime and
read-related atime updates are inherent effects, not deliberately corrected dates.

## Alternatives

- Catalogue-only correction: rejected after real-world acceptance testing;
  independent tools must read corrected capture timestamps from the media.
- Rewrite source metadata in place: rejected because failure could damage the
  only original copy.
- Attach an offset to a card: rejected because cards are reused.
- Update import history in place: rejected because original verification evidence
  must remain auditable.
- Rename first and journal later: rejected because interruption loses the
  explanation of the move.

## Consequences

- Planning is read-only, including catalogue access without schema migration.
- Corrections require SHA-256 verified import evidence or an observed folder
  snapshot, plus usable camera or filename timestamps. Filesystem fallback dates require manual investigation.
- Timestamps must share a time basis: all naive camera wall times or the same
  explicit fixed UTC offset. Timezone conversion is a separate concern.
- The copy-first approach needs temporary space for the full selected scope and
  a filesystem supporting hard links for atomic, exclusive publication. Existing
  import callers retain their existing publication mode.
- Recovery and rollback evidence is available; automated rollback and changing
  an already-recorded rule remain future work.
- The advisory root lock serialises correction commands on Linux. It cannot
  prevent unrelated external software changing files; content and path checks
  reject observed changes, and publication never overwrites a destination.

## Folder scopes (REQ-033)

`--source` supplies observed folder evidence through a read-only adapter into the
same planner and executor. Source paths are validated against the selected
source root; corrected paths are validated against the separate archive root.
The source root is retained and only empty subdirectories are cleaned up.
Advisory locks cover both explicit roots during execution.

Folder journal payloads originally used schema version 2, `scopeType="folder"`, a namespaced
`scopeId`, and null `importId`, `importManifest`, `cardId` and `snapshotId`. The
scope lookup key derives from the canonical source root and explicit requested
selection. The full immutable observed file set, hashes and timestamp evidence
are included in the rule identity and persisted before media mutation. The key
is a recovery lookup, not permission to correct future contents. New members,
changed content and overlapping operations are rejected during recovery. Once
complete, a fresh snapshot creates a new transformation from current media.
Schema version 4 separates the source/selection lookup (`selectionId`) from its
observed scope (`scopeId`). The operation identity distinguishes repeated work
on identical input bytes, including sidecars and zero-offset transformations.

Reuse the existing correction tables without rebuilding legacy catalogue data.
Their historical SQL column name `importId` holds the namespaced folder scope
key for folder rows; `correctionScopeKey` owns this compatibility detail. Public
folder evidence and timestamp lookup results expose `scopeId` and null import
identity. No import manifest/history row is fabricated. Existing import rows,
rule IDs and manifest contracts remain compatible.

Helpers use an unambiguous original's capture timestamp, preserving their own
observed timestamp/source separately where available. This aligns thumbnails,
telemetry, XML and artwork without pretending that helper metadata necessarily
uses the same clock basis as an original video.

## Related requirements and decisions

- [REQ-024](../requirements/features/024-cameraCaptureTimeCorrection.md)
- [REQ-033](../requirements/features/033-cameraFolderCaptureCorrection.md)
- [ADR-003](003-filesystemSafetyBoundary.md)
- [ADR-006](006-cameraImportArchitecture.md)
- [ADR-008](008-sqliteMediaCatalogue.md)
- [ADR-010](010-sharedMediaProcessingBoundary.md)

## Completion and subsequent corrections

Seal a completed journal with `completedAt` after verified publication, source
removal and cleanup. Reject changes to sealed audit records. Recognise cleaned
legacy completions without requiring a database migration; upgrading old
catalogue-only corrections creates a new transformation of their output files.
Earlier records and JSON exports remain untouched.

Read current embedded metadata, hashes and filesystem state for each new
transformation. Link verified input identities to predecessor outputs. For an
import selection, follow those identities through completed transformations,
then read the terminal files. Ambiguous histories block rather than choosing an
arbitrary path. A verified identical replay is a no-op; recovery of unfinished
work uses its immutable input snapshot and existing absolute target values.

`cameraCaptureTime` is a mutable effective-state index, separate from the audit
journal. Replace stale source/destination entries and all effective values when
a later correction verifies; preserve the full earlier evidence in
`cameraCaptureCorrection`. Recheck overlap and input bytes/mtime under the root
locks so a preview made before another transformation cannot silently proceed.
