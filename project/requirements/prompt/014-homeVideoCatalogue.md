# Requirement: 014 — project/requirements/features/014-homeVideoCatalogue.md

Role: implement and verify

Read the requirement, REQ-002, REQ-004, REQ-010, REQ-016, REQ-021,
ADR-008, `documentation/homeVideo.md`, and `documentation/mediaCatalogue.md`.

Implement Home Video catalogue support for `/mnt/myVideo/Video` using an
injected path in tests. The catalogue must present a logical timeline based
on best-known capture date rather than assuming the physical historical
folder structure is correct. Preserve physical path and date evidence so the
system can report mismatches and uncertainty.

Cover historical folder variants such as `08 - Aug`, `1985-08`, and plain
`08`; phone/iOS, GoPro/DJI/Dashcam and topic folders; date provenance and
precedence; duplicate candidates; `.AAE`/sidecar association; unknown dates;
and issue/audit queries. Filename similarity alone must never prove a
duplicate.

Imported camera footage is Home Video library content. Card, inventory
snapshot, and import identities are provenance attached to a Home Video item,
not the primary UI object.

Do not move, rename, delete, or deduplicate files. Do not implement AI
keyword generation, OCR, sports-score extraction, final event grouping, or
Qt presentation in this increment. The data/service model must nevertheless
allow later enrichment to attach to stable Home Video identities.

Keep services independent of Qt and argparse. Keep names in camelCase. Use
temporary filesystem fixtures only; tests must never access the real
`/mnt/myVideo/Video` tree.

Verify with `pytest` and `git diff --check`.
