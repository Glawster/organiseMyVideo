# ADR-004: Qt application architecture

## Status

Proposed

## Context

REQ-002 introduces a desktop media-library browser while the existing product is
a packaged CLI. The shared standards require UI orchestration to remain separate
from business logic. The Qt binding, process boundary, background loading model,
and packaging approach affect several later components and are costly to change
after widgets depend on them.

## Options considered

1. PySide6 widgets in this package, backed by framework-independent Python
   library/query services and worker tasks.
2. PyQt6 with the same separation.
3. Reuse the React/FastAPI starter from `organiseAIMediaStudio` instead of Qt.
4. Put scanning and media processing directly inside Qt widgets.

## Proposed decision

Use PySide6 for an optional Qt desktop surface in this repository. Define plain
Python media-item, collection-query, and load-result contracts outside the UI.
Qt models/view-models adapt those contracts for widgets, and background workers
perform potentially slow reads without mutating media. Keep the existing CLI
entry point and add a separately declared GUI entry point or canonical GUI
command during Phase 3.

Do not accept this ADR until refinement confirms the binding/license choice,
supported deployment platforms, background-task cancellation semantics, and
the boundary with any verified `organiseAIMediaStudio` components.

## Rationale

PySide6 matches the repository's Python implementation and the shared Qt
guidance while allowing core scanning and query behaviour to remain headlessly
testable. Reusing the current React starter would contradict the requested Qt
surface and introduce a client/server architecture without a demonstrated need.

## Consequences

- Qt is an optional dependency and must not be required for CLI-only use.
- Core library/query modules cannot import PySide6.
- Widgets cannot perform direct filesystem mutation or metadata-provider calls.
- Qt model and worker lifecycle behaviour requires dedicated automated tests.
- Packaging must expose and document both CLI and GUI launch paths.

## Related requirements

- [REQ-002: Qt media-library browser](../requirements/features/002-qtMediaLibraryBrowser.md)
