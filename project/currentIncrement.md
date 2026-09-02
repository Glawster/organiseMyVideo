# Current increment

## Requirement

[REQ-006: Entry-point and CLI architecture](requirements/features/006-cliArchitecture.md)

## Objective

Deliver Phase 3 of the standards-adoption roadmap while preserving legacy CLI
behaviour.

## Status

Completed on 2026-09-02 — side-effect-free imports, entry-point logging,
canonical commands, compatibility, validation, statuses, documentation,
production paths, 353 tests, and both pre-commit hooks passed.

## Verification target

- Side-effect-free package import
- Equivalent canonical and legacy command paths
- Nested help, version, verbosity, validation, and exit statuses
- Module and console production paths
- Full pytest and pre-commit suites
