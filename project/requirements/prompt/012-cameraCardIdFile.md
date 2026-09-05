# Requirement: 012 — project/requirements/features/012-cameraCardIdFile.md

Role: implement and verify

Write `organiseMyVideo.NNN` at the card volume root on confirmed
`camera inventory`. Store the card summary including free space. Read it on
later scans. Refuse a mismatched `--card`. Do not write the file in dry-run.
Ignore it when counting media.

Verify with `pytest` and `git diff --check`.
