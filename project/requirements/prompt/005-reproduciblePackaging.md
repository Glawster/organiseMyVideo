# Requirement: 005 — project/requirements/features/005-reproduciblePackaging.md

Role: implement and verify

Read the authoritative requirement, standards audit, ADR-001, repository
instructions, repository-layout guide, testing process, and release process
before changing files.

Deliver Phase 2 packaging only. Make `pyproject.toml` authoritative, retain
aligned compatibility dependency exports, provide Conda-first editable setup,
repair pytest/pre-commit/ignore configuration, and document module and console
execution. Do not perform Phase 3 logging or CLI refactoring and do not publish
a release.

Verify metadata, build artifacts, a clean temporary installation, CLI help,
the full tests, pre-commit hooks, and `git diff --check`. Handoff with changed
files, acceptance-criterion evidence, commands run, and unresolved items.
