# ADR-001: Preserve the packaged CLI layout

## Status

Accepted — 2026-08-04

## Context

`organiseMyVideo` is an established packaged command-line application whose
supported entry point is `python -m organiseMyVideo`. A generic scaffold update
added a root UI-oriented `main.py` and unrelated `src/globalVars.py`, creating
two competing application shapes.

## Options considered

1. Preserve the existing top-level `organiseMyVideo/` package and package-level
   entry point.
2. Move the package under `src/` immediately.
3. Treat the repository as a standalone UI application with root `main.py`.

## Decision

Preserve `organiseMyVideo/` as the source-package directory and
`organiseMyVideo.__main__:main` as the executable workflow. Do not add a root
`main.py`, generic `src/globalVars.py`, or UI scaffold. A future `src/` layout
migration requires a separate requirement demonstrating sufficient benefit.

## Rationale

The current package boundary is functional, documented, and tested. Moving it
does not itself improve safety or user outcomes and would create avoidable
import and deployment churn.

## Consequences

- Packaging must discover the existing top-level package explicitly.
- The shared layout's packaged-CLI exception is documented in
  `.github/additional-instructions.md`.
- Generic application and UI templates are inapplicable unless a later
  requirement changes the product role.

## Related requirements

- [REQ-001: Standards adoption governance](../requirements/features/001-standardsAdoption.md)
