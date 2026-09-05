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
| 4 | Centralise safe filesystem behaviour | Completed | REQ-007 verified |
| 5 | Refactor by domain without changing behaviour | ToDo | Phases 2–4 provide stable boundaries |
| 6 | Make verification enforceable | ToDo | Measurable package and domain boundaries exist |
| 7 | Finish layout and documentation adoption | ToDo | Ownership decisions for auxiliary files are agreed |

## Current priority

The next product-delivery priority is REQ-004 camera media import, beginning
with its typed, non-mutating planner and then adding verified import and archive
migration. Phase 5 remains the next internal standards-adoption phase and may
be scheduled separately without obscuring the camera-import commitment.

REQ-007 completed Phase 4 with a central filesystem-operation boundary,
source-filesystem quarantine, 30-day purge eligibility, and verified
cross-filesystem recovery rules. REQ-006 completed Phase 3 with
established shared logging, media-safe imports, decomposed CLI orchestration,
canonical commands, legacy compatibility, universal options, validation, and
reliable statuses.
REQ-005 completed Phase 2 with verified package distributions, a clean install,
the console-script entry point, declared dependencies, Conda setup, consolidated
pytest/pre-commit configuration, and corrected ignore rules.
REQ-002 captures the Qt media-library browser as a separate product outcome;
it remains `ToDo` pending its open product decisions and ADR-004.
REQ-003 captures the official Imagine API archive as a Python service. The
Firefox-backed `grok --scan` workflow separately retrieves the operator's own
grok.com generated media.
REQ-004 captures the agreed GoPro, DJI, and dash-cam media importer as a
separate product outcome using Python services and a `camera import`
subcommand.
REQ-009 catalogues numbered SD cards through `camera inventory` and SQLite
local-state snapshots; it does not import media.
REQ-010 stores movies, TV, and cards in one SQLite catalogue that the UI
reads and that scans update.
REQ-011 adds dash-cam cards to the same inventory routine as GoPro and DJI.
REQ-014 indexes `/mnt/myVideo/Video` as home video, including GoPro and
Drone. REQ-015 inventories USB thumb drives in the same numbered volume
list.

## Deferred decisions

- Phase 4: a future purge command and its permanent-deletion safeguards.
- Phase 7: ownership of `rugbyAudit.py` and the root XML artifact.
