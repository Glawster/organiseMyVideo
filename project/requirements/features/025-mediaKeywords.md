# 025: Media keywords and tagging

## Status

ToDo

## Outcome

As a media-library operator, I need to add descriptive keywords to one media file or a selected set of files so that footage can be found later by event, subject, person, place, or other useful descriptors without relying on filenames or folder names.

The motivating case is the latest card 2 camera import: all files belong to one concert and should be taggable with a keyword such as `concert` across the whole selected import/session.

## Context

Keywords are descriptive metadata, not filesystem organisation policy. A file may remain under its date-based archive path while carrying one or more descriptive terms such as:

```text
concert
live music
artist name
venue name
Belfast
family
walking football
```

The media system should use established metadata conventions where practical:

- still-image keywords map to IPTC/XMP keyword metadata, including XMP `dc:subject`;
- video keywords map to an interoperable video/QuickTime keyword field where the container supports it, including `com.apple.quicktime.keywords` or an equivalent standards-compatible XMP representation;
- catalogue keywords mirror the embedded values so files remain searchable without reopening and reparsing media every time.

Keyword metadata must be additive and must not alter the encoded image/video essence. Embedded metadata writing must therefore use a safe writer that preserves the media payload and verifies the result before replacing the original file.

## Scope

- Add manual keyword tagging for one file, multiple selected files, an import, a snapshot/session, or another explicitly bounded file set.
- Support one or more free-text keywords per file.
- Normalise surrounding whitespace while preserving meaningful keyword text.
- Avoid silently creating duplicate keywords that differ only by trivial case/spacing rules according to a documented normalisation policy.
- Preserve existing embedded keywords by default; new keywords are additive unless the operator explicitly requests replacement/removal.
- Store keywords in the OMV catalogue so they can be searched, filtered, displayed, and bulk-edited without reparsing each media file.
- Where supported safely, embed the same keyword values in the media file using standards-compatible metadata.
- For JPEG/photo media, prefer interoperable IPTC/XMP keyword storage such as XMP `dc:subject` / IPTC Keywords.
- For MP4/MOV/QuickTime media, prefer an interoperable QuickTime/video keyword field such as `com.apple.quicktime.keywords`, or a standards-compatible XMP representation when that is the supported writer path.
- If a format cannot be updated safely in-place, do not silently mutate or transcode it. Report that embedded tagging is unavailable for that file and retain the catalogue keyword; an optional sidecar fallback may be added later.
- Keep keyword assignment dry-run-first for any operation that rewrites media files.
- Provide a confirmed mode (`-y` / `--confirm`) before embedded metadata is changed.
- Show a concise plan containing file count, keywords to add/remove, formats involved, files that can be embedded safely, and catalogue-only fallbacks.
- For bulk operations, show progress so large imports do not appear stalled.
- Verify the rewritten file before replacing the original. At minimum, verify that the file remains readable and that the expected keyword metadata can be read back.
- Preserve original timestamps and unrelated metadata unless the chosen metadata library necessarily changes a container-level metadata timestamp; any such behaviour must be documented and tested.
- Record keyword changes in an auditable operation log/manifest with old keyword set, new keyword set, file identity, result, and failure reason.
- Support removal of one selected keyword without removing unrelated keywords.
- Support listing/searching media by keyword from the catalogue.
- Keep manually supplied keywords distinct from any future automatically inferred/AI-generated keywords by recording provenance.

## Card 2 reference case

The first production use case is the latest applicable card 2 import.

The operator should be able to select that import/session and apply:

```text
concert
```

or a richer set such as:

```text
concert
live music
<artist>
<venue>
```

The selected keywords should be applied consistently to every media asset in the selected card-2 import/session without affecting earlier or later uses of physical card 2.

The selection must therefore be based on durable import/snapshot/session identity rather than merely `cardId=2`.

## Shared architecture

### `organiseMediaStudio`

Owns reusable technical primitives for:

- reading keyword metadata from supported image/video formats;
- writing standards-compatible keyword metadata without application-specific policy;
- neutral keyword records/results;
- keyword normalisation helpers;
- metadata write verification;
- future automatic keyword-generation interfaces.

Suggested neutral records include:

```text
MediaKeyword
KeywordReadResult
KeywordWritePlan
KeywordWriteResult
```

A keyword record should be able to retain at least:

```text
value
source
provenance
confidence (where applicable)
```

Manual keywords have explicit manual/user provenance and do not require an inferred-confidence value.

### `organiseMyVideo`

Owns:

- CLI/UI selection of files/imports/sessions;
- catalogue persistence and keyword search;
- dry-run/confirmation policy;
- bulk operation planning;
- audit history;
- deciding whether an unsupported embedded format falls back to catalogue-only metadata;
- camera/import/session scoping.

## CLI direction

Exact syntax may evolve with the CLI architecture, but the intended capability is equivalent to:

```text
organiseMyVideo media keywords FILE --add concert
organiseMyVideo media keywords FILE1 FILE2 --add concert --add "live music"
organiseMyVideo camera keywords --import IMPORT_ID --add concert
organiseMyVideo media keywords --keyword concert --list
```

Mutating embedded metadata remains dry-run by default and requires `-y` / `--confirm`.

## Out of scope

- Automatic AI keyword generation in the first implementation slice.
- Face recognition or automatic person naming.
- Renaming files/folders based on keywords.
- Transcoding media merely to add keywords.
- Treating folder names as authoritative keywords without explicit operator approval.
- Applying one import/session keyword set automatically to every historical/future use of the same physical card.
- Replacing all existing metadata with a new metadata block.

## Acceptance criteria

1. Given one supported media file, when a keyword is added in dry-run mode, then the planned old/new keyword sets are shown and neither the file nor catalogue is changed.
2. Given `--confirm`, when a supported media file is tagged, then the keyword is written using the supported standards-compatible metadata representation and is readable after the write.
3. Given existing keywords, when a new keyword is added, then unrelated existing keywords are preserved.
4. Adding an already-present keyword does not create a duplicate value after normalisation.
5. Given multiple selected files, when one or more keywords are applied, then the same requested keyword change is planned for each file and progress is visible during confirmation.
6. Given the latest applicable card-2 import/session, when `concert` is applied, then every asset in that selected import/session receives the keyword while other uses of card 2 remain unchanged.
7. Keyword selection by card-derived content uses durable import/snapshot/session identity rather than applying permanently to `cardId`.
8. Given a JPEG with supported embedded metadata, the system can read and write interoperable IPTC/XMP keyword metadata and verify the result.
9. Given an MP4/MOV with supported embedded metadata, the system can read and write an interoperable video/QuickTime keyword representation and verify the result.
10. Given a format for which safe embedded keyword writing is unavailable, the file is not rewritten; the limitation is reported and the catalogue keyword may still be stored according to application policy.
11. Confirmed metadata rewriting never transcodes the audio/video/image essence merely to add keywords.
12. A failed metadata write does not leave a partially rewritten final file; the original remains recoverable/intact.
13. Catalogue keyword rows are searchable without reparsing every source media file.
14. Removing one keyword preserves all unrelated keywords.
15. Keyword operation history records file identity, previous keywords, requested changes, resulting keywords, provenance, and outcome.
16. Manual keyword provenance is distinguishable from any future imported, inferred, or AI-generated keyword provenance.
17. Tests cover add, duplicate-add, remove, bulk tagging, card/import scope isolation, unsupported formats, write failure, and metadata read-back verification.

## Dependencies and decisions

- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-022: Shared media processing platform](022-sharedMediaProcessing.md)
- [REQ-024: Camera capture-time correction](024-cameraCaptureTimeCorrection.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-010: Use organiseMediaStudio as the shared media-processing boundary](../../adr/010-sharedMediaProcessingBoundary.md)

## Verification

- Shared `organiseMediaStudio` unit tests using small generated JPEG and MP4/MOV fixtures where practical.
- OMV catalogue tests for keyword persistence/search and provenance.
- Bulk-operation tests with temporary files and synthetic import/session identities.
- Read-back verification after confirmed embedded writes.
- Failure-injection tests proving originals are not lost on metadata-write failure.
- Card-2 regression test applying `concert` only to the selected latest import/session.
- `pytest`
- `git diff --check`

## Traceability

- Shared keyword metadata implementation: pending in `organiseMediaStudio`.
- OMV keyword catalogue/UI/CLI implementation: pending.
- Card 2 production tagging: pending implementation and dry-run review.
- Pull request: pending.

## Change history

- 2026-09-17: created — define manual and bulk media keyword tagging, embedded standards-compatible metadata where safe, catalogue indexing, provenance, and card-2 `concert` use case.
