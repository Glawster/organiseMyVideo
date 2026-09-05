# Current increment

## Requirement

No requirement is currently in delivery. The next planned product increment is
[REQ-004: Camera media import](requirements/features/004-cameraMediaImport.md).

## Objective

Implement camera import and existing-archive migration in independently
verifiable stages, starting with the typed dry-run planner.

## Status

Ready to start after the current feature branch is reviewed and integrated.
REQ-004 remains `ToDo` until implementation actually begins.

## Entry checks

- Phase 4 filesystem safety is completed.
- Camera inventory and metadata readers are available for reuse.
- Files without a trustworthy migration date remain in place for manual review.
