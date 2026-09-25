# Requirement: 027 — project/requirements/features/027-slrCardImport.md

Role: implement and verify

Read REQ-027 together with REQ-004, REQ-009, REQ-021, ADR-003, ADR-006, ADR-007, and `documentation/cameraImport.md`.

Implement mixed SLR card support without weakening the existing camera-import safety and identity model. Treat routing as an asset-level decision: CR3/JPEG photographs go to the configured photo root under `By Date/YYYY/MM/DD`; MP4 clips go to the configured video root under `By Date/YYYY/MM/DD`. Preserve filenames and RAW/JPEG pairs, prefer embedded capture metadata, ignore Canon control/catalogue files, preserve duplicate/conflict semantics, and leave the source card unchanged.

Add tests for Canon-style `DCIM/100CANON` trees containing CR3/JPEG pairs, MP4 clips, ignored files, duplicates, conflicts, mixed dates, and large confirmed imports. Confirm that inventory/import summaries expose useful per-type counts and that confirmed import shows visible progress.

Run the relevant unit and CLI integration tests, then `pytest` and `git diff --check`. Update requirement traceability and documentation when implementation is complete.
