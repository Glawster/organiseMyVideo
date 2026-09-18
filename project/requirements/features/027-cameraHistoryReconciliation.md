# 027: Camera history reconciliation

## Status

Planned

## Outcome

As a media-library operator, I need recorded camera-import history to be checked against the current archive so that files moved after import remain traceable without losing the original import evidence.

## Context

Camera import manifests currently record the destination path used at import time. Later maintenance, such as REQ-025 archive normalisation or a manual move, may relocate the same verified media to a different path. The historical manifest must remain auditable, but normal history output should also be able to resolve the file's current location.

A history check must therefore distinguish between the immutable historical destination and the current reconciled destination. It must never silently rewrite history, guess between ambiguous matches, or treat filename similarity alone as proof of identity.

## Scope

- Add a read-only history verification mode:
  `organiseMyVideo camera history --check`.
- Support scoping by card:
  `organiseMyVideo camera history --card <id> --check`.
- For each manifest asset, verify whether the recorded destination still exists and still matches the recorded content identity.
- Prefer the recorded cryptographic digest, currently SHA-256, as the primary identity when locating a moved file.
- Use filename, file size, import/card provenance, and plausible archive roots only as supporting evidence, never as sufficient proof when a digest is available.
- Report a per-asset reconciliation state:
  - `ok` — recorded path exists and identity matches.
  - `moved` — recorded path is absent but exactly one matching file is found elsewhere.
  - `missing` — no matching file is found.
  - `ambiguous` — more than one plausible identity match is found.
  - `changed` — the recorded path exists but its current content no longer matches the recorded identity.
- Dry-run/read-only check is the default and must not alter manifests.
- A future confirmed reconciliation mode may persist an unambiguous current path while retaining the original historical destination.
- Preserve the original destination as immutable historical evidence.
- Persist relocation metadata only for unambiguous matches, for example:
  - original destination path,
  - current destination path,
  - reconciliation timestamp,
  - reconciliation reason/source.
- Do not rewrite or hide a prior import path merely because the canonical archive layout changed later.
- Allow REQ-025 camera archive normalisation to reuse the same reconciliation service after successful moves so history and archive maintenance share one identity model.
- History display should prefer the reconciled current path for operational use while still making the original import destination available for audit.
- Reconciliation must be safe when manifests predate fields introduced by later schema versions.

## Command behaviour

Examples:

```bash
organiseMyVideo camera history --check
organiseMyVideo camera history --card 18 --check
```

Illustrative output:

```text
CAMERA HISTORY CHECK — CARD 018

Status      Recorded destination                              Current destination
------      --------------------                              -------------------
ok          /mnt/.../2025/03/27/IMG_0323.CR3                 same
moved       /mnt/.../2026/05-May/13/file.MP4                 /mnt/.../2026/05/13/file.MP4
missing     /mnt/.../2024/09/09/MVI_0221.MP4                 -
ambiguous   /mnt/.../2024/09/09/IMG_0215.JPG                 2 matches
changed     /mnt/.../2025/02/21/IMG_0250.CR3                 digest differs
```

The exact presentation may change, but the status semantics are required.

## Persistence model

A reconciled record must retain both historical and current-path evidence. A future manifest schema may use fields such as:

```json
{
  "destinationPath": "/mnt/myVideo/Video/Dashcam/2026/05/13/file.MP4",
  "originalDestinationPath": "/mnt/myVideo/Video/Dashcam/2026/05-May/13/file.MP4",
  "relocatedAt": "2026-09-18T08:00:00+00:00",
  "relocationReason": "history-check"
}
```

Existing manifests where `destinationPath` is the original imported path must remain readable. Migration to any newer manifest schema must preserve that original value before replacing the operational/current path.

## Out of scope

- Automatically moving archive files during `camera history --check`.
- Guessing a moved file from filename alone.
- Resolving ambiguous matches automatically.
- Deleting stale history.
- Rewriting import timestamps, card identity, source paths, or original digests.
- Implementing REQ-025 archive normalisation itself.

## Acceptance criteria

1. Given a recorded destination that still exists with matching digest, when history check runs, then the asset is reported `ok`.
2. Given a recorded destination is absent and exactly one digest-identical archive file is found, when history check runs, then the asset is reported `moved` with both paths.
3. Given no digest-identical file is found, when history check runs, then the asset is reported `missing`.
4. Given more than one candidate matches the recorded identity, when history check runs, then the asset is reported `ambiguous` and no path is chosen.
5. Given the recorded path exists but its digest differs, when history check runs, then the asset is reported `changed`.
6. Given no confirmation is supplied, when history check runs, then no manifest or archive file is modified.
7. Given a future confirmed reconciliation of an unambiguous moved asset, when the current path is persisted, then the original imported destination remains recorded.
8. Given a legacy manifest without relocation fields, when history check runs, then it remains readable and can be checked.
9. Given REQ-025 moves a verified camera archive file, when it invokes the shared reconciliation service, then history can record the new current path without losing original import evidence.
10. Given history is displayed after reconciliation, then the current location is available for operational use and the original destination remains available for audit.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md) provides manifests and verified import identities.
- [REQ-025: Camera archive normalisation](025-cameraArchiveNormalisation.md) may relocate already-imported media and should reuse this reconciliation service.
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-006: Camera import architecture](../../adr/006-cameraImportArchitecture.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)

## Verification

- Unit tests for ok, moved, missing, ambiguous, and changed states.
- Tests proving digest identity takes precedence over filename similarity.
- Tests proving dry-run is non-mutating.
- Tests proving original destination evidence survives a persisted reconciliation.
- Legacy-manifest compatibility tests.
- Integration tests with REQ-025-style `MM-MMM` to `MM` archive moves.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: deferred
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-18: created — define history verification and moved-file reconciliation while preserving immutable original import destinations.
