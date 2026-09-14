# Requirement: 009 — project/requirements/features/009-cameraCardInventory.md

Role: implement and verify

Read the authoritative requirement, `documentation/cameraInventory.md`,
ADR-006, ADR-007, and repository instructions before changing code. Deliver
camera-card inventory as importable Python services with a thin
`camera inventory` adapter. Do not import, move, delete, or format card media.

Keep every new module, function, test, documentation file, and SQLite
identifier in camelCase. Do not add snake_case camera filenames such as
`camera_inventory.py`.

Wire the canonical scan command as:

```text
python -m organiseMyVideo camera inventory -s SOURCE --card ID
python -m organiseMyVideo camera inventory -s SOURCE --card ID --confirm
```

Canonical inventory requires explicit `-s/--source` and must fail before
scanning when it is omitted.

Model identity explicitly:

- `cardId` is the durable identity of the physical numbered card.
- Every confirmed inventory run creates a new durable `snapshotId`.
- Reusing the same physical card creates another snapshot under the same
  `cardId`; it must not overwrite earlier snapshots or their file lists.
- The latest confirmed snapshot is the current known card contents; older
  snapshots remain historical audit evidence.
- The Linux mount path is temporary runtime context only and must not be used as
  card identity or lifecycle identity.

Persist SQLite under the application local-state directory. Each confirmed
snapshot must retain the complete set of relative file paths found beneath the
selected source, including non-camera files such as packages, installers,
documents, and archives. Preserve the raw list as observed; presentation
filtering must not destroy historical evidence.

Expose `cardId` and `snapshotId` through the application service so camera import
and removable-media lifecycle services can link verified archive outcomes to
the exact observed card contents they apply to.

Use xAI image understanding for `.THM` (or JPEG fallback) summaries, with an
injectable vision function so tests never require a network or API key.

Use temporary paths and synthetic fixtures; never depend on a real removable
drive. Include tests proving later snapshots do not overwrite prior filename
inventories, arbitrary non-camera filenames are persisted, reuse creates a new
snapshot for the same card, and changing the mount path does not change durable
identity.

Verify with:

- `pytest`
- `git diff --check`

Handoff with files changed, acceptance-criterion-to-evidence mapping, commands
run, and unresolved items.
