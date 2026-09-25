# Requirement: 028 — project/requirements/features/028-cameraHistoryReconciliation.md

Role: refine, implement, and verify

Read REQ-028 together with REQ-004, REQ-026, ADR-003, ADR-006, ADR-008, and the camera import/history documentation.

Implement camera history verification around the existing import manifests. Add `camera history --check` with optional `--card` scoping. Classify recorded assets as `ok`, `moved`, `missing`, `ambiguous`, or `changed`. Use the recorded SHA-256 digest as primary identity and never silently choose an ambiguous candidate.

Keep the default check read-only. If confirmed reconciliation is implemented, persist the current path only for unambiguous moved files while preserving the original imported destination as immutable historical evidence. Keep legacy manifests readable and make the reconciliation service reusable by REQ-026 archive normalisation.

Add tests covering every reconciliation state, digest-vs-filename identity, non-mutating dry-run, legacy manifests, and preservation of original destination evidence. Run relevant tests, then `pytest` and `git diff --check`. Update traceability and documentation when implementation is complete.
