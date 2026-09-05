# Requirement: 013 — project/requirements/features/013-cameraCardIdRetie.md

Role: implement and verify

Add `--reassign` so a confirmed `camera inventory --card NEW --reassign` can
replace an existing on-card ID. Refuse a mismatched `--card` without
`--reassign`. Keep old SQLite snapshots.

Verify with `pytest` and `git diff --check`.
