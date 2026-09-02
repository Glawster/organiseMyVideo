# ADR-002: Migrate the CLI with compatibility

## Status

Accepted — 2026-09-02

## Context

The current CLI uses many top-level mode flags. The shared standard prefers
discoverable action or object/action subcommands, but scripts and operator
habits may depend on existing invocations.

## Options considered

1. Replace all legacy flags with subcommands in one breaking release.
2. Add canonical subcommands while retaining legacy flags as documented
   compatibility aliases for an agreed period.
3. Keep the flat flag interface permanently as a repository exception.

## Decision

Introduce canonical subcommands and retain existing mode flags and the
no-subcommand organiser invocation as compatibility aliases. Do not emit a
deprecation notice during Phase 3. Canonical commands must remain stable and
documented for at least one minor release before warnings begin. Legacy forms
may be removed only in a later major release with a dedicated requirement,
migration notes, and evidence that maintained automation has moved.

## Rationale

A staged migration improves discoverability without unexpectedly breaking
automation or familiar operator workflows.

## Consequences

- Parser tests must prove equivalent behaviour for canonical and legacy forms.
- Help output must identify one canonical invocation for each workflow.
- Phase 3 preserves legacy forms without warnings.
- Removal requires a later major release and its own approved requirement.

## Related requirements

- [REQ-001: Standards adoption governance](../requirements/features/001-standardsAdoption.md)
- [REQ-006: Entry-point and CLI architecture](../requirements/features/006-cliArchitecture.md)
