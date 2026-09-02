# Standards adoption roadmap

This roadmap sequences the findings in the
[standards audit](reviews/2026-08-04-standardsAudit.md). Each technical phase
receives its own requirement before implementation; completing this roadmap is
not itself a substitute for acceptance evidence.

| Phase | Outcome | Status | Entry condition |
| --- | --- | --- | --- |
| 0 | Establish a safe, reproducible baseline | Completed | Managed process documentation adopted |
| 1 | Bootstrap requirements and architecture governance | Completed | Phase 0 tests pass |
| 2 | Make installation and execution reproducible | Completed | REQ-005 verified |
| 3 | Repair entry-point and CLI architecture | Completed | REQ-006 verified |
| 4 | Centralise safe filesystem behaviour | ToDo | Refine and accept ADR-003 |
| 5 | Refactor by domain without changing behaviour | ToDo | Phases 2–4 provide stable boundaries |
| 6 | Make verification enforceable | ToDo | Measurable package and domain boundaries exist |
| 7 | Finish layout and documentation adoption | ToDo | Ownership decisions for auxiliary files are agreed |

## Current priority

Create and refine the Phase 4 requirement for a central filesystem-operation
boundary, including quarantine, retention, and cross-filesystem recovery
decisions needed to accept ADR-003. REQ-006 completed Phase 3 with
side-effect-free imports, decomposed CLI orchestration, canonical commands,
legacy compatibility, universal options, validation, and reliable statuses.
REQ-005 completed Phase 2 with verified package distributions, a clean install,
the console-script entry point, declared dependencies, Conda setup, consolidated
pytest/pre-commit configuration, and corrected ignore rules.
REQ-002 captures the Qt media-library browser as a separate product outcome;
it remains `ToDo` pending its open product decisions and ADR-004.
REQ-003 captures the official Imagine API archive (`grok generate|list|download`)
and replaces the inactive grok.com scraper.
REQ-004 captures the agreed GoPro and DJI camera-media importer as a separate
product outcome using Python services and a `camera import` subcommand.

## Deferred decisions

- Phase 3: duration and removal criteria for legacy CLI flags.
- Phase 4: cleanup quarantine location, retention, and permanent-deletion cases.
- Phase 7: ownership of `rugbyAudit.py` and the root XML artifact.
