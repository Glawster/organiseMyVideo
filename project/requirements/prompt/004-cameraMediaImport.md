# Requirement: 004 — project/requirements/features/004-cameraMediaImport.md

Role: implement and verify

Read the authoritative requirement, `documentation/cameraImport.md`, ADR-001,
ADR-002, ADR-003, ADR-006, ADR-007, and repository instructions before changing
code. Deliver the requirement in the documented increments. Keep legacy archive
migration as an explicit action separate from card ingestion; do not include
card cleanup.

Implement camera detection, metadata reading, planning, verified copying, and
manifest generation as typed Python services that can be used without the CLI.
Do not invoke ExifTool, ffprobe, shell commands, or other external executables.
Wire the thin command adapter as:

```text
python -m organiseMyVideo camera import -s SOURCE
python -m organiseMyVideo camera import -s SOURCE --confirm
python -m organiseMyVideo camera migrate
python -m organiseMyVideo camera migrate --confirm
```

For canonical `camera import`, `-s/--source` is required and positional source
syntax is rejected. The CLI adapter must call the same importable application
service used by direct Python callers; do not duplicate planning or import
behaviour in `__main__.py`.

Add durable card/import identity propagation:

- Resolve `cardId` from the existing `organiseMyVideo.NNN` label on a numbered
  removable card.
- Treat the Linux mount/source path as transient runtime context, never as card
  identity or the basis for archive/lifecycle state.
- Carry `cardId` through planning/results and confirmed import evidence.
- When a confirmed inventory snapshot can be matched, record its `snapshotId`
  with the import.
- Give each confirmed import a durable `importId`.
- Reconcile imported assets to the relevant inventory snapshot using relative
  path and verification evidence such as size/digest.
- Dry-run may inspect unidentified media but must report that it is not linked
  to a known card; confirmed import from a numbered removable source requires a
  resolvable `cardId`.
- Never infer that a reused card is archived merely because a previous snapshot
  for the same `cardId` was fully imported. The latest confirmed snapshot is the
  current known contents.

Keep dry-run as the default. Preserve the source card, original filenames, and
DJI SRT companions. Store new GoPro and DJI imports beneath their respective
`YYYY/MM/DD` directories. Exclude LRV and THM files unless explicitly
requested. Migrate supported existing archive media only through the separate
dry-run-first action, preserve companions, verify moves, leave ambiguous files
in place, and write a rollback-capable migration manifest.

Use temporary paths and synthetic fixtures in tests; never depend on the real
removable drive or `/mnt/myVideo`. Add tests for on-card card-ID discovery,
changed mount paths, unidentified dry-run/confirmed behaviour, multiple
snapshots for one reused card, import-to-snapshot linkage, and the rule that an
older archived snapshot must not make a newer reused-card snapshot appear
archived.

Verify with:

- `pytest`
- `git diff --check`

Handoff with files changed, acceptance-criterion-to-evidence mapping, commands
run, and unresolved items.
