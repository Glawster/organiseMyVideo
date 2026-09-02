# Requirement: 006 — project/requirements/features/006-cliArchitecture.md

Role: implement and verify

Read the authoritative requirement, standards audit, ADR-001, ADR-002, and all
repository instructions before changing code. Deliver only Phase 3.

Remove package-import logging side effects, keep logging initialization at the
entry point, and decompose CLI construction, validation, dispatch, and summary
rendering. Add canonical object/action commands while retaining the current
flags and no-command organiser path as compatibility aliases. Add universal
version/verbosity options and reliable statuses. Do not remove or warn about
legacy forms yet, centralise domain filesystem operations, or implement camera
commands.

Verify direct parser equivalence, isolated import behaviour, module and console
production paths, the full tests, pre-commit, and whitespace. Handoff with
acceptance-criterion evidence and unresolved items.
