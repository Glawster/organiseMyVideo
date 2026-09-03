# 007: Central filesystem safety

## Status

Completed

## Outcome

As a media-library operator, I need every application file mutation to pass
through one dry-run-aware safety boundary so that planned actions are visible,
collisions are rejected, failures preserve source data, and cleanup is
recoverable.

## Context

Phase 4 addresses direct copy, move, rename, write, and deletion calls spread
across media, metadata, torrent, gallery, configuration, and cleanup workflows.
ADR-003 defines the shared boundary and recovery policy.

## Scope

- Represent directory creation, byte/text writes, copy, move, rename,
  quarantine, and empty-directory removal in one Python service.
- Make dry-run plan operations without changing files.
- Validate sources, destinations, containment, and collisions centrally.
- Use temporary destinations and atomic finalization for writes and copies.
- Verify cross-filesystem file moves before removing the source.
- Quarantine cleanup targets on their source filesystem.
- Migrate existing production mutations to the service.
- Classify intentional application-state writes separately from media changes.
- Add focused unit and production-path tests and operator documentation.

## Out of scope

- Automatically purging quarantined content.
- Providing a purge CLI before a separate requirement authorizes permanent
  deletion.
- Transactional rollback across several independent operations.
- Camera import implementation.

## Acceptance criteria

1. Given dry-run, when any supported operation is requested, then it records a
   plan and performs no filesystem mutation.
2. Given invalid, missing, identical, or colliding paths, when an operation is
   requested, then it fails before source loss or destination overwrite.
3. Given a text/byte write or file copy, when confirmed, then content is written
   to a sibling temporary path and atomically finalized.
4. Given a same-filesystem move or rename, when confirmed, then it is finalized
   without overwriting an existing destination.
5. Given a cross-filesystem file move, when confirmed, then the destination is
   copied, verified by size and SHA-256, atomically finalized, and only then is
   the source removed; failure cleanup leaves the source intact.
6. Given a cleanup target, when confirmed, then it is moved into a unique
   source-filesystem quarantine path rather than permanently deleted.
7. Given quarantined content, when 30 days pass, then it is merely eligible for
   a future explicit purge; Phase 4 never purges it automatically.
8. Given application configuration, cache, summary, session, or catalog data,
   when its owning workflow permits the write, then the service records it as
   application state and writes it atomically.
9. Given existing workflows, when tests exercise media moves, metadata writes,
   gallery downloads, torrent cleanup, and source cleanup, then mutations use
   the shared boundary and established dry-run behavior is preserved or made
   safer.
10. Given Phase 4 verification, when the full suite, hooks, and direct-mutation
    audit run, then they pass and no unapproved permanent removal remains.

## Dependencies and decisions

- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)
- [REQ-006: Entry-point and CLI architecture](006-cliArchitecture.md)

## Verification

- Unit tests with temporary filesystems and injected EXDEV/failure behavior.
- Existing production-path workflow tests.
- Direct-mutation audit using `rg`.
- `pytest`
- `pre-commit run --all-files`
- `git diff --check`

## Traceability

- Implementation: `organiseMyVideo/filesystemOperations.py` and migrated workflows
- Tests: 359 passed; focused boundary and production workflow coverage
- Documentation: `documentation/filesystemSafety.md`
- Pull request: pending
- Agent runs: 2026-09-03 — Codex, Phase 4 implementation and verification

## Change history

- 2026-09-03: created and started — deliver Phase 4 after operator approval.
- 2026-09-03: completed — centralized mutations, collision safety, verified
  cross-filesystem moves, recoverable quarantine, tests, and operator guidance.
