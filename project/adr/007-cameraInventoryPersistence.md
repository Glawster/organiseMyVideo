# ADR-007: Persist camera-card inventory in SQLite under local state

## Status

Accepted — 2026-09-04; clarified 2026-09-12 for durable snapshot identity and card reuse.

## Context

Operators label physical SD cards with numeric IDs and need a catalogue of what
each card contains: capture-date range, capacity, a short description of the
footage, and eventually the complete relative filename inventory. JSON manifests
used by camera import are per-run audit files, not a queryable card catalogue.
Thumbnail description needs an image model, and the application already
authenticates to xAI with `XAI_API_KEY`.

A physical card is reusable. Card 6 may contain one set of files in June, be
fully imported and reformatted, and contain an entirely different set of files
in September. The database must therefore distinguish the durable identity of
the physical card from the identity of each observed inventory state.

Linux mount paths are not durable identifiers. The same physical card can
appear at different paths over time, and a path can later refer to another card.

The operator asked for SQLite under the local/state folder. Application logs
already use the XDG state directory `~/.local/state/organiseMyVideo`.

## Options considered

1. Append JSON inventory documents beside camera-import manifests.
2. Store a SQLite database in the application XDG local-state directory and
   describe sampled `.THM` or JPEG files through the xAI vision API.
3. Store SQLite relative to the process working directory as `./local/state`.

## Decision

Use option 2. Camera-card inventory is an importable Python service exposed as
`python -m organiseMyVideo camera inventory`. Snapshots persist in SQLite under
the application XDG local-state directory.

The persistence model separates four identities:

- `cardId`: durable identity of the physical numbered card.
- `snapshotId`: durable identity of one confirmed inventory observation of that
  card.
- relative file path: location of a file within one snapshot's observed card
  tree.
- `importId`: durable identity of one confirmed camera-import run owned by
  REQ-004.

Re-inventorying a reused card creates a new `snapshotId` under the same
`cardId`. Earlier snapshots and their file inventories are immutable historical
evidence and are not replaced by the new observation. The latest confirmed
snapshot is the current known contents for lifecycle calculations.

A source/mount path may be retained as diagnostic context for one operation, but
it is not part of durable identity and must never be used to decide whether a
card is archived, safe to recycle, or the same physical card as an earlier run.

Camera import may link a confirmed `importId` to the applicable `cardId` and
`snapshotId`. That relationship allows lifecycle services to determine whether
the archive-worthy files observed in a specific snapshot have verified archive
copies. A previously archived snapshot does not make a later reused-card
snapshot archived.

Content summaries are produced from sampled GoPro `.THM` thumbnails, or JPEG
stills when no thumbnail exists, using xAI image understanding (`grok-4.6`)
authenticated with `XAI_API_KEY`. Vision is injectable for tests. Dry-run scans
and reports but does not write SQLite or call the vision API.

A working-directory relative `./local/state` database is rejected because the
installed CLI is invoked from arbitrary directories and card identity must not
depend on the caller's cwd.

## Rationale

SQLite gives a single queryable store for card identity, historical snapshots,
file inventories, import relationships, and future lifecycle state without
adding a server. XDG local-state matches the existing application state
convention. xAI is already a packaged dependency and can read the JPEG bytes
inside `.THM` files. Keeping inventory on the `camera` object follows ADR-006 so
GoPro, DJI, dash-cam, and general numbered removable volumes share one command
family.

The explicit `cardId`/`snapshotId` distinction is required because physical
media are routinely reused. It prevents old verified imports from being
mistaken as proof that the card's current contents are archived.

## Consequences

- `__main__.py` remains an adapter and must not own inventory rules or SQL.
- Tests inject a vision function and a temporary database path.
- Missing `XAI_API_KEY` does not block storing dates, sizes, file counts, or
  snapshot identity.
- Every persisted inventory observation has a durable `snapshotId` associated
  with a durable `cardId`.
- Historical snapshots and their file inventories are retained when a card is
  reused.
- Camera import/manifests may reference `cardId`, `snapshotId`, and `importId`
  so verified archive evidence is attributable to the correct card use.
- Mount paths remain diagnostic-only and must not be treated as durable keys.
- Camera import and migration remain REQ-004; inventory never copies media.
- New Python, test, documentation, and SQLite names use camelCase.

## Related requirements

- [REQ-009: Camera card inventory](../requirements/features/009-cameraCardInventory.md)
- [REQ-004: Camera media import](../requirements/features/004-cameraMediaImport.md)
- [REQ-020: Removable media discovery and lifecycle](../requirements/features/020-removableMediaDiscovery.md)
