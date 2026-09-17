# 021: Shared media processing platform

## Status

In progress

## Outcome

As a media-library developer, I need generic image and video processing to be
provided by the shared `organiseMediaStudio` package so that `organiseMyVideo`
and `organiseMyPhotos` can reuse the same media inspection, identity, date,
frame, OCR, analysis, configuration, date/time-correction, and media-equivalence
patterns without duplicating implementation.

## Context

`organiseMyPhotos` currently contains generic video behaviour such as video-file
recognition, hashing, duration/resolution probing, filename/path/position date
inference, perceived-date selection, and recursive video scanning. Much of this
behaviour is not photo-specific and is now also required by the Home Video
catalogue in `organiseMyVideo`.

`organiseMyPhotos` also has an established Tk settings editor with a **Save
Settings** action, path-entry fields, Browse buttons, explanatory tooltips, and
persisted settings. That interaction pattern is suitable for configuring media
archive locations in `organiseMyVideo` and should be reused rather than
inventing a separate settings experience.

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
Home Video catalogue persistence, camera-card/import lifecycle, UI, CLI,
storage paths, event and sports-specific interpretation. `organiseMyPhotos`
remains responsible for photo/iCloud workflows and its own UI/catalogue policy.

A media timestamp can be technically readable but factually wrong. A common
camera failure mode is a device left at its factory/default clock: embedded
metadata then advances consistently from the wrong epoch. The shared media
layer must therefore distinguish raw timestamp discovery from an explicitly
approved timestamp correction. The motivating current case is camera card 2:
the GoPro recorded dates beginning in January 2015 because its clock was never
set, while the user-confirmed real session began on 2018-08-25 at 19:00. The
relative timing between files is useful evidence and must be preserved while a
fixed offset is applied to derive corrected capture times.

A second recurring media problem is that two files can represent the same
recording without being byte-for-byte identical. An original camera file may
coexist with lower-resolution or lower-bitrate transcodes. SHA-256 is still the
authority for exact identity, but a shared media layer also needs a neutral way
to compare recording equivalence using duration, dimensions, frame rate,
stream metadata, and optional perceptual/video fingerprints.

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
  - capture-time correction by an explicit fixed offset derived from a
    recorded/actual reference pair;
  - video duration/resolution and later richer stream probing;
  - cryptographic hashing and exact-duplicate primitives;
  - media-equivalence/derivative comparison primitives that do not depend on
    filename equality;
  - recursive media scanning;
  - video frame extraction and thumbnail generation;
  - generic OCR and image/video analysis interfaces.
- Preserve the raw/original timestamp and its provenance whenever a correction
  is applied. A corrected timestamp must supplement, not overwrite, the raw
  evidence.
- Represent a correction with enough neutral data to audit it, including at
  least the raw/reference timestamp, user-confirmed actual reference timestamp,
  signed offset, correction method, reason, and resulting corrected timestamp.
- Support a fixed-offset correction where a camera clock advanced normally from
  the wrong date/time; applying the correction must preserve the elapsed time
  between files.
- Keep correction scope explicit. The shared layer provides the correction
  primitive; consuming applications decide whether it applies to one file, one
  import, one inventory snapshot, or another bounded session/range.
- Do not make a correction a permanent property of a reusable physical card.
  A later use of the same card may come from a different camera or a correctly
  set clock.
- Distinguish exact duplication from media equivalence:
  - exact identity is established by cryptographic hash/content equality;
  - media equivalence means different encoded files may represent the same
    underlying recording.
- Provide neutral comparison evidence for media equivalence, including where
  available capture/start time, duration, dimensions, frame rate, codecs,
  bitrate/stream information, and sampled/perceptual fingerprint observations.
- Keep any equivalence score/confidence separate from destructive policy. The
  shared package may return evidence/confidence; the consuming application
  decides whether to retain, link, relocate, or remove a derivative.
- Allow an application to rank related representations by technical quality
  using neutral evidence such as resolution and bitrate, while keeping
  application-specific preference policy outside the shared package.
- Keep expensive operations, especially full-file hashing, video probing, and
  perceptual fingerprinting, explicit/lazy where practical rather than
  performing them as constructor side effects.
- Allow shared services to be used headlessly from tests, CLIs, and desktop
  applications.
- Preserve enough provenance in returned results for the consuming catalogue
  to explain how metadata or equivalence conclusions were derived.
- Integrate REQ-014 Home Video catalogue scanning with shared services once
  the required `organiseMediaStudio` primitives are available.
- Reuse the `organiseMyPhotos` settings-editor interaction pattern in the
  media system: editable path fields, Browse controls, concise tooltips,
  explicit **Save Settings**, validation/status feedback, and persisted values.
- Keep the settings UI in the consuming application rather than moving Tkinter
  into `organiseMediaStudio`; reuse the pattern and, where practical, shared
  non-UI configuration helpers rather than creating an application dependency
  on `organiseMyPhotos`.
- Provide configurable archive/storage roots in `organiseMyVideo` for at least:
  - GoPro media;
  - Drone/DJI media;
  - Dashcam media;
  - Home Video / general video archive locations;
  - photo archive locations where the media-system workflow needs to hand off
    to or coordinate with `organiseMyPhotos`.
- Commands and services that currently rely on default paths such as
  `/mnt/myVideo/Video/GoPro` must obtain their normal runtime root from saved
  configuration. CLI path overrides may remain available and take precedence
  over the saved setting for that invocation.

## Shared model direction

The shared package should expose neutral records such as:

```text
MediaAsset
MediaProbeResult
CaptureDateCandidate
CaptureDateResult
CaptureDateCorrection
MediaHashResult
MediaEquivalenceResult
MediaFingerprintResult
FrameSample
KeywordResult
OcrResult
```

The names are architectural guidance rather than a mandate for one large
class hierarchy. Prefer small immutable records and focused services over a
stateful object that performs filesystem I/O, hashing, and probing merely by
being constructed.

Common metadata includes path, media type, size, raw capture date and
provenance, corrected capture date where applicable, identity/fingerprint
information, device metadata where available, and sidecar relationships.
Video-specific results include duration, resolution, frame rate, codec/stream
metadata, sampled frames, and equivalence/fingerprint evidence. Image-specific
results include image dimensions and embedded image metadata.

A neutral correction record should be capable of representing values such as:

```text
rawCaptureAt
correctedCaptureAt
correctionOffsetSeconds
correctionMethod = "fixed-offset"
referenceRecordedAt
referenceActualAt
correctionReason
```

A neutral equivalence result should be capable of representing evidence such as:

```text
sameRecordingCandidate
confidence
captureTimeDelta
durationDelta
resolutionA / resolutionB
bitrateA / bitrateB
fingerprintSimilarity
evidence
```

## Ownership boundaries

### `organiseMediaStudio`

Owns reusable technical media-processing capabilities, including metadata
reading, capture-date candidate/resolution logic, fixed-offset timestamp
correction primitives, hashing/fingerprinting, exact-duplicate primitives,
media-equivalence evidence, image/video probing, frame extraction, thumbnails,
OCR, embeddings, keyword-generation interfaces, and generic scan utilities. It
may own neutral configuration models/helpers that contain no application UI or
application-specific path policy.

### `organiseMyVideo`

Owns the movie/TV/Home Video catalogue, camera-card and import lifecycle,
filesystem organisation policy, user-facing CLI/UI, storage paths and their
settings editor, the scope/approval of camera-session time corrections,
derivative retention/removal policy, event and sports-domain interpretation,
and persistence of results in its SQLite catalogue.

### `organiseMyPhotos`

Owns photo/iCloud ingestion, photo organisation policy, photo-specific UI and
catalogue persistence. It may consume the same shared date/time correction,
media-equivalence, and analysis services and may pass encountered videos through
shared inspection rather than maintaining a separate video-processing
implementation. Its existing settings editor is the reference interaction
pattern for the media-system settings UI.

## Out of scope

- A shared catalogue database between `organiseMyVideo` and
  `organiseMyPhotos`.
- Moving either application's UI into `organiseMediaStudio`.
- Adding a direct runtime dependency from `organiseMyVideo` to
  `organiseMyPhotos` merely to reuse the settings dialog.
- Automatically guessing a real-world capture time when no reliable reference
  has been supplied or derived from trustworthy evidence.
- Permanently attaching a timestamp correction to a reusable physical card ID.
- Rewriting embedded EXIF/MP4 metadata merely because the application uses a
  corrected timestamp; embedded-metadata rewriting requires a separate
  explicit requirement and safety policy.
- Automatically deleting media merely because an equivalence primitive reports
  that it may represent the same recording as another file.
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
13. `organiseMyVideo` provides a settings editor following the established
    `organiseMyPhotos` Save Settings pattern, with editable path fields, Browse
    controls, useful tooltips, explicit save action, and visible validation or
    success feedback.
14. The settings editor allows the GoPro, Drone/DJI, Dashcam, and Home Video
    archive roots to be viewed and changed without editing source code or a
    configuration file manually.
15. Saved media-root settings persist across application runs and are used by
    camera import/migrate and relevant catalogue operations as their normal
    defaults.
16. A command-line destination/root override, when supplied, overrides the
    persisted value for that invocation without silently replacing the saved
    setting.
17. Invalid or unusable configured paths are reported clearly before a
    mutating operation begins; saving a setting does not itself move media.
18. Reusing the settings experience does not introduce a runtime import from
    `organiseMyVideo` to `organiseMyPhotos` or move Tkinter into
    `organiseMediaStudio`.
19. Given a raw capture timestamp and one trusted recorded/actual reference
    pair, the shared date/time service can calculate a signed fixed offset and
    apply it to another timestamp while preserving the original raw value.
20. Given multiple files from a camera whose clock advanced normally from an
    incorrect epoch, applying one fixed offset preserves the elapsed intervals
    between those files exactly.
21. A correction result exposes the raw timestamp, corrected timestamp,
    correction offset, method, reference timestamps, and reason/provenance.
22. A consuming application can persist and later reproduce the correction
    without altering the original media metadata.
23. The shared API does not infer correction scope from `cardId`; scope is
    supplied by the consuming application.
24. Tests cover positive and negative offsets, date rollovers, leap years, and
    a multi-day sequence whose corrected timestamps cross calendar-day/month
    boundaries.
25. A regression fixture representing card 2 can map an incorrectly dated 2015
    recording sequence to a session whose user-confirmed real start is
    2018-08-25 19:00 while preserving all relative intervals in the sequence.
26. Given byte-identical files, the shared identity service can establish exact
    duplication independently of media-equivalence analysis.
27. Given different encodes of the same recording, a shared equivalence service
    can return neutral evidence including duration, resolution, stream metadata
    and optional fingerprint similarity without declaring a destructive action.
28. Media-equivalence confidence/evidence is exposed to callers separately from
    cryptographic identity.
29. Expensive perceptual/video fingerprint work is opt-in/lazy and can be
    skipped during a fast planning pass.
30. Tests cover one high-quality/original representation and at least two
    lower-resolution encodes of the same recording, plus a visually unrelated
    file with similar duration to guard against false equivalence.

## Migration sequence

1. Establish the `organiseMediaStudio` package boundaries, neutral models,
   tests, and packaging.
2. Port media-type recognition and generic video probing.
3. Port capture-date candidate/resolution logic and its tests.
4. Add neutral fixed-offset capture-time correction primitives and provenance
   records, then cover them with cross-date/month regression tests.
5. Port hashing/fingerprint and generic scanning primitives.
6. Add neutral media-equivalence comparison using cheap probe evidence first,
   with optional sampled/perceptual fingerprinting as a later confidence layer.
7. Integrate these services into REQ-014 Home Video catalogue.
8. Replace matching `organiseMyPhotos` video internals with shared calls while
   preserving behaviour.
9. Define the shared persisted media-root configuration model and add the
   `organiseMyVideo` settings editor using the `organiseMyPhotos` Save Settings
   interaction pattern.
10. Move camera import/migrate and relevant catalogue defaults from hard-coded
    archive paths to the persisted media-root configuration.
11. Integrate camera/import-scoped capture-time correction in `organiseMyVideo`
    using the shared correction primitive, beginning with a dry-run of the
    latest card 2 import.
12. Migrate additional genuinely shared duplicate/sidecar/media-analysis
    services only after their application policies have been separated.
13. Add AI keyword/OCR/embedding capabilities as later requirements.

## Dependencies and decisions

- [REQ-014: Home video catalogue](014-homeVideoCatalogue.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [ADR-010: Use organiseMediaStudio as the shared media-processing boundary](../../adr/010-sharedMediaProcessingBoundary.md)

## Verification

- Shared-package unit tests using temporary files/directories and generated
  test media where required.
- `organiseMyVideo` integration tests with shared services mocked or injected
  where appropriate.
- Settings tests covering save/load persistence, configured-root use,
  validation, Browse-field behaviour where practical, and CLI override
  precedence.
- Date/time correction tests covering raw/corrected provenance, exact interval
  preservation, positive/negative offsets, rollover cases, and the card 2
  default-clock scenario.
- Media-equivalence tests covering exact duplicates, alternate encodes,
  quality differences, unrelated same-duration media, and lazy fingerprinting.
- Existing `organiseMyPhotos` video-support tests retained or ported before
  removal of old behaviour.
- `pytest`
- `git diff --check`

## Traceability

- Reference UI:
  - `organiseMyPhotos/ui/settingsFrame.py` — `SettingsFrame`, including
    **Save Settings**, path fields, Browse controls, tooltips and persisted
    settings.
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

- 2026-09-17: added shared media-equivalence requirements to distinguish exact
  cryptographic duplicates from alternate encodes of the same recording and to
  expose neutral quality/fingerprint evidence without embedding deletion policy
  in `organiseMediaStudio`.
- 2026-09-17: added shared fixed-offset capture-time correction requirements,
  preserving raw timestamp provenance and using the latest card 2 import as the
  motivating regression case: GoPro default-clock dates in 2015 corrected to a
  user-confirmed session start of 2018-08-25 19:00 without losing relative file
  timing.
- 2026-09-17: added media-system settings requirements using the established
  `organiseMyPhotos` Save Settings interaction pattern; require persisted GoPro,
  Drone/DJI, Dashcam, Home Video and relevant photo roots, while keeping UI in
  the consuming application and avoiding a direct application dependency.
- 2026-09-15: adopted shared video probing for MP4/QuickTime creation metadata;
  removed the application-local MP4 `mvhd` parser while preserving filename
  fallback behaviour.
- 2026-09-14: created — establish `organiseMediaStudio` as the shared media
  processing platform for `organiseMyVideo` and `organiseMyPhotos`.
