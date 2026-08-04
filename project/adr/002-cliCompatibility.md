# ADR-002: Migrate the CLI with compatibility

## Status

Proposed

## Context

The current CLI uses many top-level mode flags. The shared standard prefers
discoverable action or object/action subcommands, but scripts and operator
habits may depend on existing invocations.

## Options considered

1. Replace all legacy flags with subcommands in one breaking release.
2. Add canonical subcommands while retaining legacy flags as documented
   compatibility aliases for an agreed period.
3. Keep the flat flag interface permanently as a repository exception.

## Proposed decision

Introduce canonical subcommands and retain existing mode flags as compatibility
aliases. Emit a clear deprecation notice only after the replacement commands
are stable and documented. The compatibility duration and removal criteria must
be agreed in the Phase 3 requirement before this ADR is accepted.

## Rationale

A staged migration improves discoverability without unexpectedly breaking
automation or familiar operator workflows.

## Consequences

- Parser tests must prove equivalent behaviour for canonical and legacy forms.
- Help output must identify one canonical invocation for each workflow.
- Phase 3 cannot remove legacy flags until the unresolved compatibility policy
  is approved.

## Related requirements

- [REQ-001: Standards adoption governance](../requirements/features/001-standardsAdoption.md)
