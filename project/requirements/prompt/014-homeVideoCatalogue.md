# Requirement: 014 — project/requirements/features/014-homeVideoCatalogue.md

Role: implement and verify

Read the requirement, REQ-010, ADR-008, and `documentation/homeVideo.md`.
Index `/mnt/myVideo/Video` (injected path in tests) into the shared SQLite
catalogue on library rescan. GoPro and Drone folders are home-video kinds,
not movies or TV. Do not move or delete archive files. Do not implement
Qt.

Keep names in camelCase. Verify with `pytest` and `git diff --check`.
