# 021: Shared media processing platform

## Status

In progress

## Outcome

As a media-library developer, I need generic image and video processing to be
provided by the shared `organiseMediaStudio` package so that `organiseMyVideo`
and `organiseMyPhotos` can reuse the same media inspection, identity, date,
frame, OCR, and analysis services without duplicating implementation.

## Context

`organiseMyPhotos` currently contains generic video behaviour such as video-file
recognition, hashing, duration/resolution probing, filename/path/position date
inference, perceived-date selection, and recursive video scanning. Much of this
behaviour is not photo-specific and is now also required by the Home Video
catalogue in `organiseMyVideo`.

A local repository named `organiseAIMediaStudio` has been repurposed as
`organiseMediaStudio` and scaffolded with the OMP 0.8 project structure. It is
the intended shared processing dependency for both applications.

The dependency direction is one-way:

```text
organiseMyPhotos ----\
                     +--> organiseMediaStudio
organiseMyVideo -----/
```

`organiseMediaStudio` must not import either application.

`organiseMyVideo` remains responsible for application policy: movies, TV,
Home Video catalogue persistence, camera-card/import lifecycle, UI, CLI, and
sports-specific interpretation. `organiseMyPhotos` remains responsible for
photo/iCloud workflows and its own UI/catalogue policy.

## Scope

- Adopt `organiseMediaStudio` as the shared Python package for generic media
  processing used by `organiseMyVideo`.
- Define neutral shared data/results that do not depend on the consuming UI,
  CLI, or catalogue database.
- Migrate generic video-processing behaviour from `organiseMyPhotos` into
  `organiseMediaStudio` incrementally rather than copying `ClassVideo` into
  `organiseMyVideo`.
- Provide shared primitives for:
  - media-type recognition;
  - media-file inspection;
  - capture-date candidates, chosen date, source, and confidence;
  - video duration/resolution and later richer stream probing;
  - cryptographic hashing and duplicate-candidate primitives;
  - recursive media scanning;
  - video frame extraction and thumbnail generation;
  - generic OCR and image/video analysis interfaces.
- Keep expensive operations, especially full-file hashing and video probing,
  explicit/lazy where practical rather than performing them as constructor
  side effects.
- Allow shared services to be used headlessly from tests, CLIs, and desktop
  applications.
- Preserve enough provenance in returned results for the consuming catalogue
  to explain how metadata was derived.
- Integrate REQ-014 Home Video catalogue scanning with shared services once
  the required `organiseMediaStudio` primitives are available.

## Shared model direction

The shared package should expose neutral records such as:

```text
MediaAsset
MediaProbeResult
CaptureDateCandidate
CaptureDateResult
MediaHashResult
FrameSample
KeywordResult
OcrResult
```

The names are architectural guidance rather than a mandate for one large
class hierarchy. Prefer small immutable records and focused services over a
stateful object that performs filesystem I/O, hashing, and probing merely by
being constructed.

Common metadata includes path, media type, size, capture date and provenance,
identity/fingerprint information, device metadata where available, and
sidecar relationships. Video-specific results include duration, resolution,
frame rate, codec/stream metadata, and sampled frames. Image-specific results
include image dimensions and embedded image metadata.

## Ownership boundaries

### `organiseMediaStudio`

Owns reusable technical media-processing capabilities, including metadata
reading, hashing/fingerprinting, duplicate primitives, image/video probing,
frame extraction, thumbnails, OCR, embeddings, keyword-generation interfaces,
and generic scan utilities.

### `organiseMyVideo`

Owns the movie/TV/Home Video catalogue, camera-card and import lifecycle,
filesystem organisation policy, user-facing CLI/UI, storage paths, event and
sports-domain interpretation, and persistence of results in its SQLite
catalogue.

### `organiseMyPhotos`

Owns photo/iCloud ingestion, photo organisation policy, photo-specific UI and
catalogue persistence. It may consume the same shared analysis services and
may pass encountered videos through shared inspection rather than maintaining
a separate video-processing implementation.

## Out of scope

- A shared catalogue database between `organiseMyVideo` and
  `organiseMyPhotos`.
- Moving either application's UI into `organiseMediaStudio`.
- Moving movie/TV metadata-provider logic into the shared package.
- Moving camera-card/import lifecycle policy into the shared package.
- Implementing rugby/team/final-score interpretation in the shared package;
  shared OCR/frame extraction may support that later in `organiseMyVideo`.
- A big-bang replacement of all current `organiseMyPhotos` media code.
- AI keyword assignment itself; that should be a subsequent requirement built
  on the shared analysis interfaces.

## Acceptance criteria

1. `organiseMyVideo` documents `organiseMediaStudio` as its shared generic
   media-processing dependency and no direct dependency on
   `organiseMyPhotos` is introduced.
2. Shared package APIs do not import Qt, Tkinter, `argparse`, or application
   catalogue modules.
3. Generic video inspection can return file type, size, duration, and
   resolution without depending on `organiseMyPhotos.ClassVideo`.
4. Capture-date resolution returns the selected value together with its source
   and preserves candidate evidence sufficiently for audit/debugging.
5. Filename/path date rules migrated from `organiseMyPhotos` are covered by
   shared-package tests before callers switch to them.
6. Full-file hashing is callable independently and is not an unavoidable
   constructor side effect of creating a media record.
7. Recursive media scanning accepts an injected root and filtering policy and
   can be tested entirely with temporary directories.
8. Shared video probing is behind a package API so its backend can change
   (for example from MoviePy to `ffprobe`) without caller changes.
9. Shared frame extraction returns neutral frame/sample records usable by both
   applications and by later OCR/AI processing.
10. `organiseMyVideo` remains responsible for writing shared results into its
    SQLite catalogue; `organiseMediaStudio` does not own that database.
11. Sports-domain interpretation such as team names and final score remains in
    `organiseMyVideo`, even when OCR observations come from the shared package.
12. The migration can be performed in small verified slices, with existing
    callers remaining functional until each slice is adopted.

## Migration sequence

1. Establish the `organiseMediaStudio` package boundaries, neutral models,
   tests, and packaging.
2. Port media-type recognition and generic video probing.
3. Port capture-date candidate/resolution logic and its tests.
4. Port hashing/fingerprint and generic scanning primitives.
5. Integrate these services into REQ-014 Home Video catalogue.
6. Replace matching `organiseMyPhotos` video internals with shared calls while
   preserving behaviour.
7. Migrate additional genuinely shared duplicate/sidecar/media-analysis
   services only after their application policies have been separated.
8. Add AI keyword/OCR/embedding capabilities as later requirements.

## Dependencies and decisions

- [REQ-014: Home video catalogue](014-homeVideoCatalogue.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [ADR-010: Use organiseMediaStudio as the shared media-processing boundary](../../adr/010-sharedMediaProcessingBoundary.md)

## Verification

- Shared-package unit tests using temporary files/directories and generated
  test media where required.
- `organiseMyVideo` integration tests with shared services mocked or injected
  where appropriate.
- Existing `organiseMyPhotos` video-support tests retained or ported before
  removal of old behaviour.
- `pytest`
- `git diff --check`

## Traceability

- Implementation:
  - `organiseMyVideo/cameraPlan.py` and `cameraImport.py` use shared SHA-256
    hashing while preserving import conflict and manifest semantics.
  - `organiseMyVideo/cameraMetadata.py` uses shared precise filename parsing
    and delegates MP4/QuickTime embedded creation-time probing to
    `organiseMediaStudio.video.probe.videoProbe`.
  - Dashcam-specific filename parsing and JPEG/THM EXIF remain application
    behaviour until corresponding generic shared services are adopted.
- Tests:
  - `tests/test_mediaStudioAdoption.py`
  - `tests/test_cameraMetadata.py`
  - `tests/test_cameraPlan.py`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-15: adopted shared video probing for MP4/QuickTime creation metadata;
  removed the application-local MP4 `mvhd` parser while preserving filename
  fallback behaviour.
- 2026-09-14: created — establish `organiseMediaStudio` as the shared media
  processing platform for `organiseMyVideo` and `organiseMyPhotos`.
