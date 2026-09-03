# ADR-003: Centralise filesystem safety

## Status

Accepted — 2026-09-03

## Context

Media and application-state mutations currently occur across several modules.
Dry-run checks are repeated, and cleanup uses irreversible deletion in some
paths. The shared standard requires centralized, reusable file operations and
prefers recoverable actions.

## Options considered

1. Keep direct filesystem calls and review each call independently.
2. Introduce one operation boundary for planning and applying mutations while
   preserving the current `pathlib`/`shutil` implementation underneath.
3. Adopt an external transaction or filesystem abstraction dependency.

## Decision

Introduce a small internal operation boundary that represents copy, move,
rename, create, write, quarantine, and empty-directory removal actions. It owns
dry-run planning, validation, collision policy, temporary-file cleanup, and
verification.

Cleanup targets are moved to a unique hidden quarantine alongside the owning
source root so the move normally remains on the same filesystem. Quarantined
content becomes eligible for explicit purge after 30 days, but Phase 4 never
purges automatically. Permanent deletion requires a later dedicated
requirement and confirmed command.

Cross-filesystem file moves use copy to a sibling temporary destination,
flush/finalize, size and SHA-256 verification, atomic destination rename, and
source removal only after verification. Any failure removes only incomplete
temporary output and leaves the source intact.

## Rationale

A narrow internal boundary improves consistency and testability without adding
a large dependency or forcing domain logic to understand storage mechanics.

## Consequences

- Existing media workflows migrate incrementally behind the boundary.
- Tests must verify planning performs no media mutations and failure does not
  silently lose the source.
- Application-state writes allowed during dry-run remain separately classified
  and documented.

## Related requirements

- [REQ-001: Standards adoption governance](../requirements/features/001-standardsAdoption.md)
- [REQ-007: Central filesystem safety](../requirements/features/007-filesystemSafety.md)
