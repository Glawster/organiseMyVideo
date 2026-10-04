# 040: Cross-platform application support

## Status

ToDo

## Outcome

As a media-library operator, I need organiseMyVideo to run on Linux, macOS, and Windows so that movie, TV, Home Video, camera, catalogue, scan and organise workflows are not tied to a Linux host.

## Context

organiseMyVideo has been developed primarily on Linux and currently reflects Linux filesystem conventions in parts of its configuration and operational model. Examples include media roots beneath `/mnt`, POSIX-oriented path assumptions, Linux application-state locations, and filesystem behaviour that may differ on macOS or Windows.

organiseMediaStudio is the shared media-processing layer. Generic portability belongs there; OMV must adopt it while retaining ownership of its catalogue, media roots, CLI and destructive workflow policy.

## Supported platforms

- Linux;
- macOS;
- Windows 11.

## Scope

- Adopt organiseMediaStudio REQ-007 cross-platform media primitives through the existing shared-media boundary.
- Treat Movie, TV, Home Video, incoming/staging, camera archive and removable-media locations as configured roots.
- Preserve current Linux configurations while allowing macOS `/Volumes/...`, Windows drive-letter paths, and safe UNC roots where applicable.
- Replace application code that assumes POSIX separators or fixed Linux mount prefixes.
- Use platform-appropriate application state/config/cache locations rather than hard-coded Linux-only state paths.
- Ensure SQLite catalogue paths and reconciliation logic remain valid with platform-native path forms.
- Apply destination-platform filename safety before planning any rename/move.
- Preserve movie/TV identity semantics separately from filename sanitisation.
- Support Windows filename restrictions, reserved names and trailing-dot/space rules.
- Handle case-insensitive filesystems and case-only rename operations safely.
- Account for Unicode normalisation differences without producing false identity conflicts.
- Prefer Python filesystem operations over Linux shell utilities.
- Discover shared external media tools through organiseMediaStudio/tool-resolution boundaries rather than fixed package paths.
- Keep OMV CLI commands usable in normal terminals on each supported platform.

## Rollout

### Phase A — shared portability

Adopt organiseMediaStudio REQ-007 and remove platform assumptions from shared-media calls.

### Phase B — non-destructive OMV workflows

Support and verify read-only/non-destructive behaviour first, including:

- catalogue open/update;
- `media scan`;
- movie location lookup;
- identity/conflict reporting;
- Home Video inspection;
- dry-run planning.

### Phase C — destructive organise workflows

After Phase B is proven, enable and verify:

- canonical renames;
- moves between configured stores;
- folder reconciliation/merge operations;
- incoming-media organisation;
- storage redistribution.

All existing safety/confirmation boundaries remain authoritative.

### Phase D — removable media

Adapt camera-card/USB discovery and lifecycle operations to platform-native removable-volume discovery. Do not infer a removable device from a Linux mount convention on macOS or Windows.

## Safety rules

- REQ-029 non-destructive `media scan` remains authoritative on every platform.
- Destructive operations remain outside scan and must use the existing filesystem-safety boundary.
- Cross-volume moves must not assume rename semantics are atomic or available.
- Existing targets must never be overwritten merely because filename case/normalisation differs.
- A canonical media identity must not change solely to satisfy destination filesystem punctuation rules.
- Unsupported removable-media operations on a platform must fail explicitly rather than guessing at devices.

## Out of scope

- Native GUI installers or application-store packaging.
- Automatically converting a user's Linux media layout into a Windows/macOS layout.
- Replacing organiseMediaStudio portability primitives with OMV-specific duplicates.
- Guaranteeing every removable-media low-level operation before platform-native discovery has been implemented and tested.

## Acceptance criteria

1. OMV core non-destructive workflows run against configured media roots on Linux, macOS and Windows.
2. No core media-domain workflow requires a path beginning with `/mnt`.
3. Existing Linux media-root configuration continues to work.
4. macOS external-volume roots can be scanned/catalogued.
5. Windows drive-letter roots can be scanned/catalogued.
6. Windows-invalid canonical movie/TV filenames are made safe before a destructive plan is created.
7. Filename sanitisation does not suppress title/year identity-conflict detection from REQ-035.
8. Case-only rename behaviour is safe on case-insensitive filesystems.
9. Unicode-normalisation differences do not create false duplicate/identity findings.
10. `media scan` remains non-destructive on every supported platform.
11. Cross-volume moves use semantics that work when source and destination are on different filesystems/volumes.
12. Application state and persisted plans/reports use platform-appropriate per-user locations.
13. Missing optional external tooling is reported clearly without corrupting catalogue or media state.
14. Shared generic portability code is not duplicated from organiseMediaStudio.
15. Supported OS CI/smoke tests cover the principal non-destructive workflows before destructive Windows/macOS support is considered complete.

## Dependencies and decisions

- [REQ-007: Central filesystem safety](007-filesystemSafety.md)
- [REQ-022: Shared media processing platform](022-sharedMediaProcessing.md)
- [REQ-029: Non-destructive media scan](029-nonDestructiveMediaScan.md)
- [REQ-035: Movie identity conflict detection](035-movieIdentityConflictDetection.md)
- [REQ-036: Incoming media preparation workflow](036-incomingMediaPreparation.md)
- [REQ-037: Media storage redistribution](037-mediaStorageRedistribution.md)
- [ADR-003](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-010](../../adr/010-sharedMediaProcessingBoundary.md)
- organiseMediaStudio REQ-007 cross-platform media portability

## Verification

- Linux/macOS/Windows CI or smoke-test matrix.
- Configured-root tests for POSIX, drive-letter and UNC forms.
- Windows-invalid/reserved filename tests.
- Case-only rename tests.
- Unicode-normalisation tests.
- Cross-volume move tests.
- Non-destructive scan regression suite.
- Catalogue persistence/reconciliation tests using platform-native path forms.
- Removable-media discovery tests using platform adapters/fakes.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: this requirement
- Pull request: pending
- Agent runs: None

## Change history

- 2026-10-04: created — define staged Linux, macOS and Windows support for organiseMyVideo using organiseMediaStudio as the shared portability layer.
