# Current increment

## Objective

Resolve the logging violations reported by OMP 0.8 `runLinter`.

## Scope

- Add shared run/header/summary separators to the legacy CLI entry point.
- Capitalise the reported movie and TV rename error messages.
- Pin OMP to commit `0aa24c1ca875c12919c14fab939ab24e0d82a24c`, which supplies
  `runStart()` and `line()`; the previous 0.6 pin does not provide these helpers.
- Extend the logging test stub with those separator helpers.

## Status

Complete. All application and test files pass the linter, and all 602 tests pass.

## Verification

- `python -m organiseMyProjects.runLinter`: all files OK.
- `python -m pytest -q`: 602 passed.
- `python -m organiseMyVideo --help`: passed with the installed real dependency.
- `git diff --check`: passed.
- The bare `runLinter` launcher in this shell uses system Python without OMP
  package metadata; the module invocation uses the active Conda environment.

## Immediate next action

Review the logging fixes. No reported lint violations remain.
