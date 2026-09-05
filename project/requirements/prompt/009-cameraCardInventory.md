# Requirement: 009 — project/requirements/features/009-cameraCardInventory.md

Role: implement and verify

Read the authoritative requirement, `documentation/cameraInventory.md`,
ADR-006, ADR-007, and repository instructions before changing code. Deliver
camera-card inventory as importable Python services with a thin
`camera inventory` adapter. Do not import, move, delete, or format card media.

Keep every new module, function, test, documentation file, and SQLite
identifier in camelCase. Do not add snake_case camera filenames such as
`camera_inventory.py`.

Wire the command as:

```text
python -m organiseMyVideo camera inventory SOURCE --card ID
python -m organiseMyVideo camera inventory SOURCE --card ID --confirm
python -m organiseMyVideo camera inventory --card ID
```

Persist SQLite under the application local-state directory. Use xAI image
understanding for `.THM` (or JPEG fallback) summaries, with an injectable
vision function so tests never require a network or API key.

Use temporary paths and synthetic fixtures; never depend on a real removable
drive. Verify with:

- `pytest`
- `git diff --check`

Handoff with files changed, acceptance-criterion-to-evidence mapping, commands
run, and unresolved items.
