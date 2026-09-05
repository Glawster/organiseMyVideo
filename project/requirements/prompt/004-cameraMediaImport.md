# Requirement: 004 — project/requirements/features/004-cameraMediaImport.md

Role: implement and verify

Read the authoritative requirement, `documentation/cameraImport.md`, ADR-001,
ADR-002, ADR-003, ADR-006, and repository instructions before changing code.
Deliver the requirement in the documented increments. Keep legacy archive
migration as an explicit action separate from card ingestion; do not include
card cleanup.

Implement camera detection, metadata reading, planning, verified copying, and
manifest generation as typed Python services that can be used without the CLI.
Do not invoke ExifTool, ffprobe, shell commands, or other external executables.
Wire the thin command adapter as:

```text
python -m organiseMyVideo camera import SOURCE
python -m organiseMyVideo camera import SOURCE --confirm
python -m organiseMyVideo camera migrate
python -m organiseMyVideo camera migrate --confirm
```

Keep dry-run as the default. Preserve the source card, original filenames, and
DJI SRT companions. Store new GoPro and DJI imports beneath their respective
`YYYY/MM/DD` directories. Exclude LRV and THM files unless explicitly
requested. Migrate supported existing archive media only through the separate
dry-run-first action, preserve companions, verify moves, leave ambiguous files
in place, and write a rollback-capable migration manifest.

Use temporary paths and synthetic fixtures in tests; never depend on the real
removable drive or `/mnt/myVideo`. Verify with:

- `pytest`
- `git diff --check`

Handoff with files changed, acceptance-criterion-to-evidence mapping, commands
run, and unresolved items.
