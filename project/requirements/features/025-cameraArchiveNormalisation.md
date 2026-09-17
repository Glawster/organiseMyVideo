# 025: Camera archive normalisation

## Status

Planned

## Outcome

As a media-library operator, I need `camera migrate` to recognise and normalise
legacy GoPro/Drone/Dashcam archive layouts so that historical camera media is
brought into the same canonical numeric date hierarchy used by current imports,
without losing files, overwriting conflicts, or requiring manual folder cleanup.

## Context

The existing GoPro archive contains several historical layouts created by older
workflows. Examples include:

```text
GoPro/2015/01-Jan/01/...
GoPro/2018/07-Jul/14/...
GoPro/2016-06-04/HERO4 Silver/GOPR0022.MP4
GoPro/2016-06-04/HERO4 Silver/GOPR0022-0001.mp4
GoPro/2016-06-04/HERO4 Silver/GOPR0022-0001_2.mp4
```

The `GOPR0022` example also demonstrates a second historical issue: multiple
files can represent the same recording while not being byte-for-byte identical.
The original camera file may be preserved alongside one or more lower-resolution
or lower-bitrate derivatives created by later software. SHA-256 correctly proves
that such files differ, but treating them as unrelated conflicts loses useful
media identity information.

The current canonical archive layout is numeric:

```text
GoPro/YYYY/MM/DD/<original filename>
Drone/YYYY/MM/DD/<original filename>
Dashcam/YYYY/MM/DD/<original filename>
```

Legacy camera/model folders such as `HERO4 Silver` describe provenance but are
not part of the canonical path. Where useful, camera/model identity should be
retained in metadata/catalogue records rather than encoded as an extra archive
folder level.

This requirement extends `camera migrate`; it is not a separate manual cleanup
command.

## Scope

`camera migrate` shall recognise and plan normalisation for at least these
legacy structures:

- `YYYY-MM-DD/<files>`;
- `YYYY-MM-DD/<camera-or-model-folder>/<files>`;
- `YYYY/MM-MMM/DD/<files>` such as `2018/07-Jul/14`;
- already canonical `YYYY/MM/DD/<files>`, which must be left unchanged;
- flat or partially structured supported camera archives already covered by
  REQ-004.

For each supported media file:

- prefer embedded/precise capture metadata when it is reliable;
- otherwise allow an unambiguous legacy date-folder value to provide the date
  fallback;
- if embedded metadata and the legacy path disagree materially, retain the file
  and report it for review rather than silently choosing one;
- preserve the original filename exactly;
- flatten legacy camera/model subfolders when targeting the canonical date
  directory;
- preserve companion-file relationships where applicable;
- never overwrite a different-content destination.

Migration shall distinguish two different forms of duplication:

- **Exact duplicate**: two files are byte-for-byte identical. Confirmed
  deduplication requires content verification and may safely remove the redundant
  legacy copy after verification.
- **Media-equivalent derivative**: two files appear to represent the same
  recording but differ because one has been transcoded, resized, recompressed,
  or otherwise re-encoded. These are not exact duplicates and must not be
  automatically deleted merely because their filenames are similar.

Derivative detection may use non-destructive technical evidence such as:

- capture/start time and duration;
- video dimensions/resolution;
- frame rate;
- codec and bitrate/stream information;
- filename lineage such as `GOPR0022.MP4`, `GOPR0022-0001.mp4`, and
  `GOPR0022-0001_2.mp4`;
- sampled-frame or perceptual/video fingerprints when a shared primitive is
  available.

Where strong evidence indicates that multiple files are the same recording,
`camera migrate` should identify one preferred/original asset and report the
others as derivative candidates. Preference should normally favour the file
with the strongest original-camera provenance and, secondarily, the highest
quality evidence such as resolution/bitrate, rather than simply choosing the
largest filename or newest filesystem timestamp.

Derivative relationships should be retained in catalogue/manifest evidence,
for example with an `originalAssetId`/`derivedFrom`-style relationship. Initial
migration must not automatically discard a derivative solely because it is
lower quality. A later explicit policy may allow confirmed derivative removal
or relocation once equivalence confidence and operator intent are sufficient.

Dry-run planning shall be fast. It may use path, filename, metadata, resolution,
duration, stream information and file size to identify candidate operations but
shall not calculate full-file SHA-256 hashes merely to preview the plan. Full
content verification is required only for confirmed operations where exact
content identity must be proven before removing a legacy path.

After successful confirmed moves/deduplication, migration may remove directories
only when they are genuinely empty. Empty legacy date and camera/model folders
should therefore disappear naturally after their contents are safely handled.
Directories containing unsupported, ambiguous, conflicting, ignored, retained
derivative, or failed items must remain.

Migration must provide visible progress for long scans, probing, fingerprinting,
and verification phases.

## Examples

### Legacy dated camera-model folder

```text
before:
GoPro/2016-06-04/HERO4 Silver/GOPR0022.MP4

canonical target:
GoPro/2016/06/04/GOPR0022.MP4
```

After a successful confirmed move, if `HERO4 Silver` and `2016-06-04` are empty,
both legacy directories may be removed.

### Same recording with lower-resolution derivatives

```text
GOPR0022.MP4        -> preferred/original
GOPR0022-0001.mp4   -> derivative candidate
GOPR0022-0001_2.mp4 -> derivative candidate
```

If the latter two have matching recording duration/start evidence but lower
resolution, they should be reported as media-equivalent derivatives rather than
ordinary same-name conflicts. They remain retained unless a later explicit
confirmed policy says otherwise.

### Legacy named-month folder

```text
before:
GoPro/2018/07-Jul/14/GOPR1234.MP4

canonical target:
GoPro/2018/07/14/GOPR1234.MP4
```

### Existing canonical path

```text
GoPro/2018/08/25/GOPR5678.MP4
```

No migration is required unless another operation, such as capture-time
correction, explicitly changes the authoritative date.

## Acceptance criteria

1. Given a legacy `YYYY-MM-DD` GoPro directory, when `camera migrate` plans the
   archive, then supported media is targeted to the canonical `YYYY/MM/DD`
   directory without changing filenames.
2. Given a legacy `YYYY-MM-DD/<camera-model>` directory, when migration plans
   supported media, then the camera/model folder is flattened and the file is
   targeted directly beneath canonical `YYYY/MM/DD`.
3. Given a legacy `YYYY/MM-MMM/DD` directory, when migration plans supported
   media, then the target month directory is numeric `MM` only.
4. Given media already beneath canonical `YYYY/MM/DD`, migration leaves that
   path unchanged unless another explicit correction rule requires relocation.
5. Given reliable embedded capture metadata, the metadata-derived date is used
   for the canonical target and its provenance is recorded.
6. Given no reliable embedded date but an unambiguous legacy date directory,
   that directory date may be used as a documented fallback.
7. Given embedded metadata and the legacy folder date conflict materially, the
   file is retained and reported for review rather than moved automatically.
8. Given a dry-run, migration performs no full-file SHA-256 calculation solely
   to preview candidate moves or duplicates and makes no filesystem changes.
9. Given `--confirm`, when a destination already exists with matching path and
   size, content identity is proven with SHA-256 before a legacy copy may be
   removed; a digest mismatch is retained as a conflict unless derivative
   analysis identifies a media-equivalent relationship.
10. Given a normal move to a previously absent destination, confirmed migration
    verifies the resulting destination before removing the old path.
11. Given a successful migration leaves `HERO4 Silver`, `2016-06-04`, `07-Jul`,
    or other recognised legacy directories empty, they may be removed from the
    deepest level upward.
12. Given a legacy directory still contains any unsupported, ambiguous,
    conflicting, ignored, retained derivative, or failed item, that directory is
    not removed.
13. Original media filenames are preserved exactly, including mixed-case
    extensions and names such as `GOPR0022-0001.mp4`.
14. Companion files are moved together according to the existing camera-import
    policy.
15. Dry-run and confirmed migration display visible progress so scans, probing,
    fingerprinting and verification do not appear hung.
16. Confirmed migration records old path, canonical path, date source, outcome,
    verification evidence, and any derivative relationship in the migration
    manifest.
17. Tests cover `YYYY-MM-DD`, optional camera/model subfolders,
    `YYYY/MM-MMM/DD`, already-canonical paths, empty-directory cleanup,
    metadata/path disagreement, identical destinations, and conflicts.
18. Given byte-identical files, migration classifies them as exact duplicates
    only after content verification and may remove the redundant confirmed copy.
19. Given files with different hashes but matching recording evidence and
    different resolution/bitrate, migration can classify them as
    media-equivalent derivative candidates rather than ordinary conflicts.
20. Given several media-equivalent versions, preference selection favours
    original-camera provenance and then higher-quality evidence such as
    resolution/bitrate; the decision and evidence are exposed in dry-run output.
21. A derivative candidate is not automatically deleted by the initial
    normalisation feature solely because it is lower quality.
22. Catalogue/manifest evidence can preserve a relationship from a derivative
    to its preferred/original media asset.
23. Regression tests cover a family equivalent to `GOPR0022.MP4`,
    `GOPR0022-0001.mp4`, and `GOPR0022-0001_2.mp4`, with the latter two lower
    resolution representations of the same recording.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-007: Filesystem safety](007-filesystemSafety.md)
- [REQ-021: Shared media processing](021-sharedMediaProcessing.md)
- [REQ-023: Camera capture-time correction](023-cameraCaptureTimeCorrection.md)

The canonical camera archive date hierarchy is `YYYY/MM/DD`. Named-month
folders such as `01-Jan` and `07-Jul` are legacy inputs to migration, not
canonical destinations.

Exact duplication and media equivalence are intentionally separate concepts:
SHA-256 is authoritative for exact identity, while derivative/equivalence
analysis uses media characteristics and, where available, shared perceptual or
video-fingerprint primitives.

## Verification

- Synthetic temporary-directory fixtures for every supported legacy layout.
- Dry-run tests proving no filesystem mutation and no full-file hashing.
- Confirmed tests proving move verification, exact-duplicate verification,
  conflict retention, derivative retention, and deepest-first empty-directory
  cleanup.
- Regression fixture matching a structure equivalent to
  `2016-06-04/HERO4 Silver`.
- Media-equivalence fixtures with one original/high-quality video and one or
  more lower-resolution derivatives representing the same recording.
- `pytest`
- `git diff --check`

## Traceability

- Migration implementation: `organiseMyVideo/cameraMigration.py` and related
  camera migration services.
- Existing duplicate-month reconciliation is an initial subset of this
  requirement.
- Shared derivative/fingerprint support: pending in `organiseMediaStudio`.
- Pull request: pending.

## Change history

- 2026-09-17: added exact-duplicate versus media-equivalent derivative handling,
  including higher-quality/original preference, derivative relationships, and a
  regression case for `GOPR0022.MP4` plus lower-resolution alternate encodes.
- 2026-09-17: created — extend `camera migrate` to normalise historical
  `YYYY-MM-DD`, camera/model subfolders, and `MM-MMM` month folders into the
  canonical numeric `YYYY/MM/DD` archive hierarchy with safe cleanup.
