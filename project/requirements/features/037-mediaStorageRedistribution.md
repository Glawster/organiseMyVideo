# 037: Media storage redistribution

## Status

ToDo

## Outcome

As a media-library operator, I need OMV to rebalance movie and TV storage
across eligible library stores so that one disk does not run critically low on
free space while comparable stores still have available capacity.

The public command is:

```bash
organiseMyVideo media organise --redistribute
```

Dry-run is the default. `--confirm` executes the most recent compatible saved
redistribution plan rather than rescanning the full library.

## Context

OMV can discover multiple movie and TV storage locations, but media remains on
whichever store received it originally. Over time one store can become much
fuller than the others. The operator needs a safe way to move complete movie
or TV-show folders to another compatible store.

Redistribution is an organisation operation, not a scan or clean operation.
Therefore it belongs under `media organise` and must use the established
filesystem-safety and catalogue-reconciliation boundaries.

## Balancing model

Balance stores by filesystem utilisation percentage rather than by equal free
bytes. This allows differently sized disks to participate sensibly.

For each eligible filesystem:

```text
utilisation = used bytes / total bytes
```

The planner should reduce the spread between the most-used and least-used
eligible filesystems without creating a destination-space risk.

Movie stores and TV stores are separate balancing pools:

- movie folders may move only between configured/discovered movie stores;
- TV show folders may move only between configured/discovered TV stores;
- a movie must never be moved into a TV root or vice versa.

If multiple roots reside on the same underlying filesystem, treat that
filesystem as one capacity target and do not create pointless same-device moves.

## Redistribution unit

The atomic planning unit is the complete top-level media folder:

- one movie folder, e.g. `Title (Year)`;
- one TV-show folder, including all seasons, metadata and artwork.

Measure the recursive size of the complete folder before planning a move. Do not
split a TV show by season and do not split a movie's feature, metadata, artwork
or extras across stores.

## Dry-run planning

`media organise --redistribute` must build a complete dry-run plan and make no
media filesystem changes.

The plan must show:

- each eligible store;
- total, used and free space;
- utilisation percentage before redistribution;
- each proposed folder move;
- folder size;
- source root;
- destination root;
- projected source/destination utilisation after each move;
- final projected utilisation/free space for every store;
- total bytes and number of folders to be moved.

The planner should choose moves that improve balance while avoiding unnecessary
movement. Prefer a small number of complete folders whose sizes move stores
toward the target utilisation. Do not move a folder if it makes the overall
utilisation spread worse.

## Persisted redistribution plan

Every successful dry run must persist the exact proposed redistribution plan in
OMV application state, under `applicationStateDirectory()` /
`~/.local/state/organiseMyVideo/` (or `XDG_STATE_HOME`).

The persisted plan should be machine-readable (for example JSON) and contain at
least:

- plan ID and creation timestamp;
- planner/version/schema version;
- movie and TV storage roots included in the plan;
- filesystem/device identity where available;
- capacity snapshot for each participating store;
- every selected source folder;
- recorded recursive folder size;
- destination path;
- source/destination media type;
- projected before/after utilisation;
- total planned bytes and move count.

The dry-run text summary should identify the saved plan ID/path.

`media organise --redistribute --confirm` must load and execute the latest
compatible saved redistribution plan rather than performing the full folder-size
scan and balancing calculation again.

If no compatible saved plan exists, `--confirm` must refuse to redistribute and
instruct the operator to run a dry run first.

A later dry run supersedes the earlier active plan. Historical plans may be kept
as run-state/audit records according to the existing application-state policy.

## Confirm-time revalidation

Reusing the plan must not mean blindly trusting stale filesystem state.
`--confirm` should avoid the expensive full rescan, but before each planned move
it must perform lightweight safety checks:

- source folder still exists;
- destination path still does not exist;
- source folder is still on the expected source root/device;
- source folder size has not materially changed from the saved plan;
- destination filesystem is mounted/available and writable;
- current destination free space is sufficient for the saved folder size plus
  the required reserve margin;
- source/destination still belong to the same media pool (movie or TV);
- no newly known unresolved collision/identity block makes the move unsafe.

If these checks fail, do not recompute a new plan automatically during
`--confirm`. Skip/refuse the affected move and report that a new dry run is
required.

## Capacity and safety

Before planning or executing a move:

- verify the destination filesystem is available and writable;
- verify the complete folder will fit;
- preserve a configurable/reserved free-space margin after the move;
- reject a destination path that already exists unless a separately defined
  merge workflow has established that the collision is safe;
- do not use redistribution as an implicit duplicate merge operation.

Cross-filesystem moves must go through OMV's `FilesystemOperations` boundary.
Do not shell out directly to `mv` or bypass dry-run/recovery behaviour merely
because the operation is conceptually an OS move.

## Execution

With `--confirm`:

1. load the saved redistribution plan;
2. validate plan compatibility/schema and participating roots;
3. re-check only the safety facts needed for each planned move;
4. move the complete folder through the central filesystem operation layer;
5. verify destination exists and source no longer exists;
6. update/reconcile catalogue location state;
7. record the move in the run summary/log and plan execution state;
8. continue only when the previous move completed safely.

Do not repeat the full recursive library scan, folder-size inventory or balancing
selection during confirm.

## Selection constraints

Do not redistribute:

- incoming/staging media;
- sample-only or quarantine content;
- a folder already involved in an unresolved identity conflict;
- a folder involved in an unresolved duplicate/collision investigation;
- folders on unavailable/offline roots;
- folders whose destination would collide with an existing path.

Prefer catalogued/current library folders where catalogue identity/location state
is available, but filesystem discovery remains authoritative for actual capacity
and existence checks.

## CLI

Canonical forms:

```bash
organiseMyVideo media organise --redistribute
organiseMyVideo media organise --redistribute --confirm
```

The first command scans, sizes and plans. The second executes the saved plan.

## Acceptance criteria

1. A dry run reports current capacity/utilisation for every eligible movie and TV store.
2. Differently sized disks are balanced by utilisation percentage, not equal free bytes.
3. Movies and TV shows are balanced independently and never cross media-type roots.
4. The recursive size of each candidate movie/show folder is known before selection.
5. Proposed moves reduce utilisation imbalance and do not exceed destination capacity.
6. Dry-run performs no media mutation.
7. Every successful dry run stores a machine-readable redistribution plan in application state.
8. The saved plan contains folder sizes, source/destination paths, capacity snapshot and projected utilisation.
9. `--redistribute --confirm` uses the saved plan and does not repeat the full folder-size/library scan.
10. Confirm refuses to run if there is no compatible saved dry-run plan.
11. Confirm revalidates source existence, destination collision and current free space before each move.
12. A stale/unsafe planned move is not silently replanned; it is refused/skipped and a new dry run is required.
13. All actual folder moves pass through `FilesystemOperations`.
14. A TV show moves as one complete folder; seasons are never split.
15. A movie moves as one complete folder including metadata/artwork/extras.
16. Destination collisions are never resolved implicitly by redistribution.
17. After a confirmed move, source/destination existence is verified and catalogue location state is reconciled.
18. Summary/log output records planned and completed redistribution moves and the plan ID.
19. Tests cover same-size and different-size stores, insufficient space, stale plans, destination collisions, offline roots and confirm-without-plan.

## Dependencies

- [REQ-007](007-filesystemSafety.md)
- [REQ-010](010-sqliteMediaCatalogue.md)
- [REQ-017](017-mergeDuplicateTvFolders.md)
- [REQ-030](030-operationalRunAudit.md)
- [REQ-034](034-catalogueLocationReconciliation.md)
- [REQ-036](036-incomingMediaPreparation.md)

## Change history

- 2026-10-02: created - add movie/TV store redistribution by utilisation percentage.
- 2026-10-02: require dry-run plans to be persisted and reused by `--confirm`,
  with lightweight safety revalidation instead of a second full rescan.
