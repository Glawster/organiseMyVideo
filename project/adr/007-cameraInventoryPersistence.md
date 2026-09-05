# ADR-007: Persist camera-card inventory in SQLite under local state

## Status

Accepted — 2026-09-04

## Context

Operators label physical SD cards with numeric IDs and need a catalogue of
what each card contains: capture-date range, capacity, and a short description
of the footage. JSON manifests used by camera import are per-run audit files,
not a queryable card catalogue. Thumbnail description needs an image model,
and the application already authenticates to xAI with `XAI_API_KEY`.

The operator asked for SQLite under the local/state folder. Application logs
already use the XDG state directory `~/.local/state/organiseMyVideo`.

## Options considered

1. Append JSON inventory documents beside camera-import manifests.
2. Store a SQLite database in the application XDG local-state directory and
   describe sampled `.THM` or JPEG files through the xAI vision API.
3. Store SQLite relative to the process working directory as `./local/state`.

## Decision

Use option 2. Camera-card inventory is an importable Python service exposed as
`python -m organiseMyVideo camera inventory`. Snapshots persist in SQLite at
`$XDG_STATE_HOME/organiseMyVideo/cameraInventory.sqlite`, defaulting to
`~/.local/state/organiseMyVideo/cameraInventory.sqlite`.

Content summaries are produced from sampled GoPro `.THM` thumbnails, or JPEG
stills when no thumbnail exists, using xAI image understanding (`grok-4.6`)
authenticated with `XAI_API_KEY`. Vision is injectable for tests. Dry-run
scans and reports but does not write SQLite or call the vision API.

A working-directory relative `./local/state` database is rejected because the
installed CLI is invoked from arbitrary directories and card identity must not
depend on the caller's cwd.

## Rationale

SQLite gives a single file the operator can query by card ID, including
historical snapshots, without adding a server. XDG local-state matches the
existing application state convention. xAI is already a packaged dependency
and can read the JPEG bytes inside `.THM` files. Keeping inventory on the
`camera` object follows ADR-006 so GoPro and mixed DJI cards share one
command family.

## Consequences

- `__main__.py` remains an adapter and must not own inventory rules or SQL.
- Tests inject a vision function and a temporary database path.
- Missing `XAI_API_KEY` does not block storing dates, sizes, and file counts.
- Camera import and migration remain REQ-004; inventory never copies media.
- New Python, test, documentation, and SQLite names use camelCase.

## Related requirements

- [REQ-009: Camera card inventory](../requirements/features/009-cameraCardInventory.md)
- [REQ-004: Camera media import](../requirements/features/004-cameraMediaImport.md)
