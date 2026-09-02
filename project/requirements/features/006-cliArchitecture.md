# 006: Entry-point and CLI architecture

## Status

Completed

## Outcome

As an operator and Python-library user, I need side-effect-free imports and a
discoverable, validated command hierarchy so that the application is safe to
embed, script, and operate while existing command lines continue to work.

## Context

Phase 3 of the standards-adoption roadmap addresses import-time logging,
monolithic CLI orchestration, flat mode flags, missing universal options,
late path validation, and inconsistent exit behaviour identified by the
standards audit. ADR-002 governs the compatibility migration.

## Scope

- Make importing `organiseMyVideo` free of log-directory/file creation.
- Initialise application logging only from an executable entry point.
- Separate parser construction, normalization, validation, logging setup,
  dispatch, and summary rendering into focused typed functions.
- Add canonical object/action commands for organisation, cleanup, rescanning,
  torrent maintenance, and legacy gallery workflows.
- Preserve all existing mode flags and the no-subcommand organiser invocation
  as compatibility aliases.
- Keep the existing `grok generate|list|download` hierarchy working.
- Add `--version`, `--verbose`, and `--quiet`; retain `--debug` as a legacy
  verbosity alias.
- Validate source paths and incompatible arguments before creating the domain
  organiser.
- Return zero for successful commands and non-zero for invalid input and
  runtime failures.
- Update CLI help, README examples, and parser/production-path tests.

## Out of scope

- Removing legacy flags or emitting deprecation warnings in this release.
- Centralising domain filesystem mutations from Phase 4.
- Refactoring large movie, TV, torrent, or metadata domain modules.
- Implementing the documented camera commands.

## Acceptance criteria

1. Given a clean home/state directory, when `import organiseMyVideo` runs,
   then it creates no application directories or log files.
2. Given module or console-script execution, when the entry point starts, then
   it initializes logging once before command dispatch.
3. Given root or nested `--help`, when help is requested, then canonical
   commands and actions are discoverable without performing application work.
4. Given each legacy workflow invocation and its canonical replacement, when
   arguments are normalized, then they select equivalent mode, targets,
   confirmation, prompting, and source behaviour.
5. Given conflicting legacy modes or command/legacy combinations, when parsing
   or validation runs, then it exits non-zero with an actionable message before
   creating `VideoOrganizer`.
6. Given a command requiring a source path, when the path is missing or not a
   directory, then it exits non-zero before domain execution.
7. Given `--version`, `--verbose`, `--quiet`, or legacy `--debug`, when used,
   then version output and logging levels behave as documented.
8. Given a successful command, when dispatch completes, then `main()` returns
   zero; given a handled runtime failure, then it returns a non-zero status.
9. Given `python -m organiseMyVideo` without a subcommand, when it runs, then
   the legacy organiser workflow remains available for compatibility.
10. Given the Phase 3 changes, when the full suite, production-path CLI tests,
    hooks, and whitespace checks run, then they pass.

## Dependencies and decisions

- [Standards adoption audit](../../reviews/2026-08-04-standardsAudit.md)
- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-002: Migrate the CLI with compatibility](../../adr/002-cliCompatibility.md)

## Verification

- Isolated subprocess import with temporary HOME/XDG state created no
  application state — passed on 2026-09-02.
- Parser equivalence, canonical dispatch, validation, logging initialization,
  nested help, version, handled-failure status, and import-side-effect tests
  are in `tests/test_cli.py`.
- `pytest -q` — 353 passed on 2026-09-02.
- `python -m organiseMyVideo --version` and nested module help — passed.
- Editable install followed by installed `organiseMyVideo --version` and nested
  help — passed.
- Missing canonical source returned status 2 through both module and installed
  console production paths.
- `pre-commit run --all-files` — Black and GUI Naming Linter passed.
- `git diff --check` — passed.

## Traceability

- Implementation: `organiseMyVideo/__main__.py`,
  `organiseMyVideo/logging_utils.py`, lazy logger adoption across package
  modules
- Tests: `tests/test_cli.py`, `tests/conftest.py`, existing CLI suites
- Documentation: `documentation/commandLineInterface.md`, `README.md`
- Pull request: pending
- Agent runs: 2026-09-02 — Codex, Phase 3 implementation and verification

## Change history

- 2026-09-02: created and started — deliver Phase 3 of the standards-adoption
  roadmap after operator approval.
- 2026-09-02: completed — verified side-effect-free imports, canonical and
  compatibility paths, universal options, statuses, tests, and production
  entry points.
