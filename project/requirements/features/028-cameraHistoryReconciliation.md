# 028: Camera history reconciliation

## Status

Completed

## Outcome

As a media-library operator, I need recorded camera-import history to be checked against the current archive so that files moved after import remain traceable without losing the original import evidence.

## Context

Camera import manifests currently record the destination path used at import time. Later maintenance, such as REQ-026 archive normalisation or a manual move, may relocate the same verified media to a different path. The historical manifest must remain auditable, but normal history output should also be able to resolve the file's current location.

A history check must therefore distinguish between the immutable historical destination and the current reconciled destination. It must never silently rewrite history, guess between ambiguous matches, or treat filename similarity alone as proof of identity.

Production verification on 2026-09-27 checked 1,426 historical assets and demonstrated all important archive-reconciliation behaviours needed for the current read-only implementation. The archive contains genuine long-standing relocations: for example, history records `GoPro/2015/01-Jan/01/G0014077.JPG`, that recorded path no longer exists, and the same digest is currently found at `GoPro/2018-08-22/HERO4 Silver 2/Time Lapse 1/G0014077.JPG`. The current path predates this reconciliation work; `moved` therefore means "historical destination absent, same content now located elsewhere", not that the history command moved the file.

The same production run also exposed missing assets and ambiguous digest matches. These findings are useful inputs to REQ-024 capture-time correction and REQ-026 archive normalisation, but this requirement remains read-only and does not infer that a historical 2015 timestamp is wrong merely because matching content is now grouped beneath a 2018 folder.

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
  - `unreadable` — destination verification or archive search could not complete safely.
  - `changed` — the recorded path exists but its current content no longer matches the recorded identity.
- Dry-run/read-only check is the default and must not alter manifests.
- Preserve the original destination as immutable historical evidence.
- Do not rewrite or hide a prior import path merely because the canonical archive layout changed later.
- Allow REQ-026 camera archive normalisation to reuse the same reconciliation service after successful moves so history and archive maintenance share one identity model.
- Reconciliation must be safe when manifests predate fields introduced by later schema versions.
- Display visible progress while checking history and while building a digest index of the archive.
- Cache the file count from a successfully completed archive-index pass as an estimate for subsequent runs; the first run may show an unknown total because no estimate yet exists. The cached count is progress state only and is not archive evidence.

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

The implemented check is read-only. A future confirmed reconciliation mode may persist an unambiguous current path while retaining the original historical destination. Any such future schema must retain both historical and current-path evidence, for example:

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
- Deciding that camera capture metadata is wrong solely from a historical/current path disagreement; REQ-024 owns explicit time correction.
- Implementing REQ-026 archive normalisation itself.
- Persisting reconciled paths in the current read-only implementation.

## Acceptance criteria

1. Given a recorded destination that still exists with matching digest, when history check runs, then the asset is reported `ok`.
2. Given a recorded destination is absent and exactly one digest-identical archive file is found, when history check runs, then the asset is reported `moved` with both paths.
3. Given no digest-identical file is found, when history check runs, then the asset is reported `missing`.
4. Given more than one candidate matches the recorded identity, when history check runs, then the asset is reported `ambiguous` and no path is chosen.
5. Given the recorded path exists but its digest differs, when history check runs, then the asset is reported `changed`.
6. Given no confirmation is supplied, when history check runs, then no manifest or archive file is modified.
7. Given a legacy manifest without relocation fields, when history check runs, then it remains readable and can be checked.
8. Given REQ-026 later moves a verified camera archive file, then the same digest identity model can locate it without losing original import evidence.
9. Given a long-running check, visible progress is reported for history checking and archive indexing.
10. Given no prior archive-index count exists, the index progress may show an unknown total; after a successful completed index, the observed count is stored and used only as an approximate progress total on the next run.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md) provides manifests and verified import identities.
- [REQ-024: Camera capture-time correction](024-cameraCaptureTimeCorrection.md) owns explicit correction where camera timestamps are factually wrong.
- [REQ-026: Camera archive normalisation](026-cameraArchiveNormalisation.md) may relocate already-imported media and should reuse this reconciliation identity model.
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-006: Camera import architecture](../../adr/006-cameraImportArchitecture.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)

## Verification

- Unit tests for `ok`, `moved`, `missing`, `ambiguous`, and `changed` states.
- Tests proving digest identity takes precedence over filename similarity.
- Tests proving the check is non-mutating.
- Legacy-manifest compatibility tests.
- Production read-only run over 1,426 historical assets.
- Production run confirmed long-standing `moved` results, missing assets, and ambiguous digest-identical matches; `changed` remains covered synthetically.
- Progress exercised during the production archive index; subsequent runs use the cached completed file count as an estimate.
- Regression coverage for filesystem races, unreadable files/directories, cache failures, legacy digests without size, and real CLI dispatch.
- Current verification results are recorded in `project/currentIncrement.md`.

## Traceability

- Implementation: `organiseMyVideo/cameraHistory.py`, `organiseMyVideo/cameraCli.py`, and command dispatch integration.
- Tests: `tests/test_cameraHistory.py` and `tests/test_cameraCli.py`.
- Production verification: completed 2026-09-27 against the current camera archive.
- Agent runs: None.

## Change history

- 2026-09-27: production verification checked 1,426 historical assets and confirmed genuine long-standing relocations, missing assets, and ambiguous duplicate matches; documented that `moved` is a reconciliation state, not an action performed by the command.
- 2026-09-27: added visible history/archive-index progress and cached prior completed archive file count for subsequent progress estimation.
- 2026-09-18: created — define history verification and moved-file reconciliation while preserving immutable original import destinations.
- 2026-09-25: restored from Git history as REQ-028 to resolve the merged REQ-027 collision with SLR card import.
