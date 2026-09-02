# 005: Reproducible packaging and installation

## Status

Completed

## Outcome

As a maintainer, I need one authoritative Python package definition and a
verified clean installation workflow so that contributors and operators can
install, test, and run `organiseMyVideo` reproducibly.

## Context

Phase 2 of the standards-adoption roadmap addresses packaging findings from
the 2026-08-04 audit. The repository previously lacked `pyproject.toml`, a
declared package version, complete runtime dependencies, and a console-script
entry point. Its pytest, pre-commit, ignore, environment, and installation
documentation were also inconsistent.

## Scope

- Make `pyproject.toml` authoritative for build metadata, package discovery,
  Python support, dependencies, development extras, and the console script.
- Retain requirements files only as aligned compatibility exports.
- Provide a Conda-first editable development installation.
- Keep pytest configuration in `pyproject.toml`.
- Make pre-commit configuration non-duplicated and installable.
- Correct generated-artifact, virtual-environment, and secret ignore rules.
- Document package-module and console-script execution.
- Verify package metadata, clean installation, CLI help, tests, and hooks.

## Out of scope

- Refactoring logging initialization or import-time side effects.
- Migrating legacy CLI modes to subcommands.
- Implementing camera import or archive migration.
- Publishing a release or uploading a distribution.

## Acceptance criteria

1. Given the repository, when a PEP 517 frontend reads it, then it finds valid
   build metadata, version, Python requirement, package discovery, runtime
   dependencies, development extras, and an `organiseMyVideo` console script.
2. Given the declared Conda environment, when it is created or updated, then
   the project and development extras are installed editable.
3. Given compatibility requirements files, when compared with
   `pyproject.toml`, then every runtime and development dependency is aligned.
4. Given pytest runs from the repository, when it loads configuration, then it
   uses valid settings from `pyproject.toml` and discovers the established
   suite.
5. Given pre-commit installs its environments, when hooks run, then each hook
   is declared once and has a resolvable entry point and dependencies.
6. Given common local environments, secrets, caches, and build artifacts, when
   Git status is inspected, then the documented ignore rules exclude them.
7. Given a clean environment with the project installed, when the module and
   console entry points request help, then both execute successfully.
8. Given Phase 2 verification, when the full suite and configuration checks
   run, then they pass without changing runtime media.

## Dependencies and decisions

- [Standards adoption audit](../../reviews/2026-08-04-standardsAudit.md)
- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)

## Verification

- `python -m build` produced `organisemyvideo-0.5.0.tar.gz` and
  `organisemyvideo-0.5.0-py3-none-any.whl` on 2026-09-02.
- The wheel and all runtime dependencies installed into a new temporary Python
  3.12 virtual environment; module and console-script help both passed.
- `conda env create --dry-run -f environment.yml` passed on 2026-09-02.
- Runtime and development compatibility exports matched the authoritative
  `pyproject.toml` dependency lists.
- `pytest -q` — 342 passed on 2026-09-02, loading `pyproject.toml`.
- `pre-commit run --all-files` — Black and GUI Naming Linter passed on
  2026-09-02.
- `git diff --check` — passed on 2026-09-02.

## Traceability

- Implementation: `pyproject.toml`, `environment.yml`, `requirements.txt`,
  `dev-requirements.txt`, `.pre-commit-config.yaml`, `.gitignore`
- Tests: existing 342-test suite using configuration in `pyproject.toml`
- Documentation: `README.md`, `.github/additional-instructions.md`
- Pull request: pending
- Agent runs: 2026-09-02 — Codex, Phase 2 implementation and verification

## Change history

- 2026-09-02: created and started — deliver Phase 2 of the standards-adoption
  roadmap after agreement to proceed.
- 2026-09-02: completed — verified distributions, clean installation, both
  entry points, Conda solve, dependency exports, tests, hooks, and whitespace.
