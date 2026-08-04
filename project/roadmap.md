# Standards adoption roadmap

This roadmap sequences the findings in the
[standards audit](reviews/2026-08-04-standardsAudit.md). Each technical phase
receives its own requirement before implementation; completing this roadmap is
not itself a substitute for acceptance evidence.

| Phase | Outcome | Status | Entry condition |
| --- | --- | --- | --- |
| 0 | Establish a safe, reproducible baseline | Completed | Managed process documentation adopted |
| 1 | Bootstrap requirements and architecture governance | Completed | Phase 0 tests pass |
| 2 | Make installation and execution reproducible | ToDo | Create REQ-002 from packaging audit findings |
| 3 | Repair entry-point and CLI architecture | ToDo | Refine and accept ADR-002 |
| 4 | Centralise safe filesystem behaviour | ToDo | Refine and accept ADR-003 |
| 5 | Refactor by domain without changing behaviour | ToDo | Phases 2–4 provide stable boundaries |
| 6 | Make verification enforceable | ToDo | Measurable package and domain boundaries exist |
| 7 | Finish layout and documentation adoption | ToDo | Ownership decisions for auxiliary files are agreed |

## Current priority

Create and refine REQ-002 for Phase 2. It should cover `pyproject.toml`, the
console-script entry point, declared dependencies, `environment.yml`, clean
installation, pytest/pre-commit configuration, and corrected ignore rules.

## Deferred decisions

- Phase 3: duration and removal criteria for legacy CLI flags.
- Phase 4: cleanup quarantine location, retention, and permanent-deletion cases.
- Phase 7: ownership of `rugbyAudit.py`, the root XML artifact, and inactive
  Grok functionality.
