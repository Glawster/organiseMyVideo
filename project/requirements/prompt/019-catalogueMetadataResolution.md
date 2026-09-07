# REQ-019 implementation prompt

## Assignment

Implement and verify all acceptance criteria in
[REQ-019](../features/019-catalogueMetadataResolution.md) on
feature/catalogue-metadata-resolution. The requirement is authoritative.

## Boundaries

Update catalogue collection/replacement, minimally refine reusable local metadata
readers, add production-path tests and update documentation/mediaCatalogue.md,
the requirements index and project/currentIncrement.md. Use camelCase identifiers.
Keep public APIs compatible, scans offline and media unchanged. Follow the
requirement exclusions; do not introduce another identification engine.

## Verification and handoff

Run pytest, black --check ., ./tests/runLinter.py,
./tests/runLinter.py --markup and git diff --check. Leave unrelated lint alone.
Report files changed, actual resolution priority, durable identity preservation,
network prevention, tests and check results, and risks deferred to
feature/canonical-media-identification.
