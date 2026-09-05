# Requirement: 011 — project/requirements/features/011-dashcamCardSupport.md

Role: implement and verify

Read the requirement, REQ-009, and camera inventory/import guides. Detect
common dash-cam directories and dated filenames in `camera inventory`, store
`dashcam` as a camera kind, and use filename timestamps when MP4/EXIF times
are missing. Do not implement dash-cam import copying in this increment.

Keep names in camelCase. Verify with `pytest` and `git diff --check`.
