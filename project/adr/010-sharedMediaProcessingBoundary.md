# ADR-010: Use organiseMediaStudio as the shared media-processing boundary

## Status

Accepted

## Context

`organiseMyPhotos` and `organiseMyVideo` increasingly require the same
technical media capabilities: media-type detection, metadata/date inference,
hashing and duplicate primitives, image/video probing, frame extraction,
thumbnail generation, OCR, embeddings, and AI-assisted description.

`organiseMyPhotos` already contains generic video behaviour, while
`organiseMyVideo` now needs equivalent capabilities for its Home Video
catalogue and later media-understanding features. Copying those implementations
between applications would create two divergent media engines.

A repository formerly named `organiseAIMediaStudio` is being repurposed as
`organiseMediaStudio` and scaffolded as an OMP 0.8 Python project.

## Decision

Use `organiseMediaStudio` as the shared, headless media-processing package for
both applications.

The dependency direction is:

```text
organiseMyPhotos ----\
                     +--> organiseMediaStudio
organiseMyVideo -----/
```

`organiseMediaStudio` must not depend on either consuming application.

The shared package owns reusable technical processing and neutral result
models. Each consuming application retains its own workflow policy, UI, CLI,
filesystem organisation rules, and catalogue persistence.

Do not place a common SQLite application catalogue in the shared package at
this stage. Shared services return neutral results that applications may store
in their own catalogues.

Do not preserve a monolithic stateful `ClassVideo` architecture as the shared
API. Prefer focused services and small records, with expensive filesystem,
hash, probe, or AI work invoked explicitly rather than implicitly during object
construction.

Generic OCR/frame extraction belongs in the shared package. Domain
interpretation remains application-owned: for example, rugby team and final
score interpretation belongs in `organiseMyVideo`, even if it consumes shared
OCR observations.

## Consequences

- Generic media behaviour can be tested once and reused by both applications.
- `organiseMyVideo` does not gain a dependency on `organiseMyPhotos`.
- `organiseMyPhotos` can progressively retire its local generic video
  implementation without a big-bang rewrite.
- Shared APIs need stable neutral models and explicit dependency boundaries.
- Package/version compatibility between the three repositories becomes part of
  release management.
- Some superficially similar behaviour must remain duplicated at the policy
  level when photo and video application semantics differ.

## Alternatives considered

### Copy `ClassVideo` into organiseMyVideo

Rejected because fixes and enhancements would diverge immediately and the
class currently combines identity, metadata, probing, date inference, and
scanning responsibilities.

### Make organiseMyVideo the shared video provider

Rejected because image/video analysis is not exclusively a video-application
concern and would introduce an incorrect dependency from `organiseMyPhotos` to
`organiseMyVideo`.

### Create a new organiseMyMedia repository

Rejected in favour of repurposing the existing `organiseMediaStudio` project,
which also leaves an appropriate home for OCR, embeddings, keywords, and other
cross-media analysis capabilities.

## Requirements

- [REQ-021: Shared media processing platform](../requirements/features/021-sharedMediaProcessing.md)
- [REQ-014: Home video catalogue](../requirements/features/014-homeVideoCatalogue.md)
