# 004: Camera media import

## Status

ToDo

## Outcome

As a media-library operator, I need to safely import GoPro and DJI originals
and migrate existing camera media through importable Python services and
discoverable CLI subcommands so that footage is verified and consistently
stored without being treated as a movie or television release.

## Context

The existing organiser classifies staged videos as movies or TV episodes. A
camera card instead contains originals, previews, thumbnails, telemetry, and
device files that require camera-aware grouping and storage rules.

The inspected archive stores GoPro footage beneath
`/mnt/myVideo/Video/GoPro`, mostly in capture-date directories, and DJI footage
directly beneath `/mnt/myVideo/Video/Drone`. The inspected removable drive uses
`DCIM/100GOPRO` and `DCIM/101MEDIA` for GoPro and DJI media respectively.

The agreed behaviour and development sequence are maintained in
[Camera media import](../../../documentation/cameraImport.md).

## Scope

- Provide camera detection, metadata reading, planning, importing,
  verification, and manifest generation as importable Python services.
- Add `python -m organiseMyVideo camera import SOURCE` as the canonical CLI.
- Add `python -m organiseMyVideo camera migrate` as the canonical dry-run-first
  action for bringing existing GoPro and Drone media into the new hierarchy.
- Accept a card root, DCIM directory, or supported camera media directory.
- Detect mixed GoPro, DJI, and dash-cam camera content.
- Preserve original MP4 and JPG filenames.
- Store GoPro originals under `GoPro/YYYY/MM/DD/`.
- Store DJI originals under `Drone/YYYY/MM/DD/`.
- Store dash-cam originals under `Dashcam/YYYY/MM/DD/`.
- Preserve same-stem DJI SRT files beside their MP4.
- Exclude GoPro LRV and THM helper files by default and support an explicit
  option to retain them.
- Ignore known operating-system, synchronisation, and camera-database files.
- Detect identical content and same-name/different-content conflicts.
- Copy and verify media without modifying the source card.
- Produce an auditable JSON import manifest.
- Plan and perform conflict-free migration of supported existing archive media
  into `YYYY/MM/DD`, including companion files.
- Produce a migration manifest containing old and new paths and sufficient
  evidence to construct a checked rollback plan.
- Keep dry-run as the default and require `--confirm` for archive changes.

## Out of scope

- Joining, transcoding, renaming, editing, or playing camera media.
- Deleting, cleaning, ejecting, or formatting a camera card.
- Automatically moving unrelated, ambiguous, or conflicting legacy content.
- Automatically executing a migration rollback.
- Requiring or invoking ExifTool, ffprobe, or shell commands at runtime.
- Classifying camera footage as movies or television episodes.

## Acceptance criteria

1. Given supported camera content, when the Python planning service is called,
   then it returns a typed import plan without changing source or destination.
2. Given a card root, DCIM directory, GoPro directory, DJI directory, or mixed
   card, when detection runs, then all supported camera sources are identified
   and unknown content is reported without being imported.
3. Given JPEG or MP4 originals, when capture metadata is available, then the
   capture date is read using Python code without invoking external programs;
   when it is unavailable, the documented fallback is reported.
4. Given GoPro content, when a plan is built, then MP4 and JPG originals target
   the matching `GoPro/YYYY/MM/DD/` directory while LRV and THM files are
   excluded unless explicitly requested.
5. Given DJI content, when a plan is built, then MP4 and JPG originals target
   the matching `Drone/YYYY/MM/DD/` directory and a same-stem SRT targets the
   same directory.
6. Given an identical destination file, when planning runs, then it is reported
   as already present; given the same destination name with different content,
   then it is reported as a conflict and no alternate filename is invented.
7. Given dry-run, when `camera import` runs, then neither the source, archive,
   application state, nor manifest storage is changed.
8. Given `--confirm`, sufficient space, and a conflict-free plan, when import
   runs, then each file is copied to a temporary destination, verified using
   the configured policy, and atomically finalised while the source remains
   unchanged.
9. Given a copy or verification failure, when import stops handling that file,
   then no incomplete final file remains and the failure is reported without
   deleting the source.
10. Given a confirmed import, when it completes, then a JSON manifest records
    source identity, camera information, paths, capture metadata, size, digest,
    companions, and outcome for every considered asset.
11. Given `python -m organiseMyVideo --help` and `camera --help`, when help is
    displayed, then the camera object and import action are discoverable.
12. Given the application service is used directly, when it performs the same
    operation as the CLI adapter, then it produces equivalent planning and
    import results without depending on argparse or console output.
13. Given existing supported media in a GoPro `YYYY-MM-DD` directory or the
    flat Drone root, when migration planning runs, then each asset targets the
    metadata-derived `YYYY/MM/DD` directory and no file is changed.
14. Given a legacy asset has an ambiguous date, unrelated type, or destination
    conflict, when migration runs, then that asset remains in place and is
    reported for manual review.
15. Given a conflict-free migration plan and `--confirm`, when migration runs,
    then originals and companions are moved together, destination content is
    verified, and source files are removed only after successful verification.
16. Given a confirmed migration, when it completes, then its manifest records
    old and new paths, hashes, metadata sources, results, and sufficient data
    for a checked rollback plan.
17. Given a legacy directory becomes empty after successful migration, when
    cleanup is considered, then only that empty directory may be removed;
    directories containing ignored, ambiguous, or failed items remain.
18. Given `camera --help`, when help is displayed, then both `import` and
    `migrate` actions are discoverable.

## Dependencies and decisions

- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-002: Migrate the CLI with compatibility](../../adr/002-cliCompatibility.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-006: Camera import architecture](../../adr/006-cameraImportArchitecture.md)
- The filesystem mutation portion depends on accepting and delivering the
  relevant ADR-003 safety rules.

## Verification

- Unit tests using temporary directories and synthetic JPEG, MP4, companion,
  ignored-file, duplicate, and conflict fixtures.
- Direct service tests proving independence from the CLI adapter.
- CLI integration tests through `python -m organiseMyVideo camera import` and
  `python -m organiseMyVideo camera migrate`.
- Failure-injection tests covering interrupted copy and failed verification.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: `documentation/cameraImport.md`, `README.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-02: created — record the agreed GoPro and DJI camera-import plan,
  pure Python module boundary, and object/action CLI interface.
- 2026-09-02: changed — use nested `YYYY/MM/DD` destination directories for
  both GoPro and DJI imports.
- 2026-09-02: changed — include a separately planned, confirmed, and verified
  migration of current GoPro and Drone files into the new hierarchy.
- 2026-09-04: changed — include dash-cam originals under `Dashcam/YYYY/MM/DD/`.
