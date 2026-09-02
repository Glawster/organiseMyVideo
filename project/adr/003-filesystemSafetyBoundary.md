# ADR-003: Centralise filesystem safety

## Status

Proposed

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

## Proposed decision

Introduce a small internal operation boundary that represents copy, move,
rename, create, write, quarantine, and removal actions. It owns dry-run
reporting, validation, collision policy, and failure cleanup. Prefer quarantine
or trash for cleanup when practical; any permanent deletion requires an
explicitly documented case and confirmed execution.

The quarantine location, retention policy, and cross-filesystem recovery rules
must be agreed in the Phase 4 requirement before this ADR is accepted.

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
