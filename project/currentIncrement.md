# Current increment

## Requirement

[REQ-028: Camera history reconciliation](requirements/features/028-cameraHistoryReconciliation.md)
on `feature/028-camera-history-reconciliation`.

## Objective and scope

Finish read-only reconciliation with race/unreadable-file handling, best-effort
progress caching, legacy digest compatibility, isolated tests, CLI execution
coverage, operator documentation and requirements-index repairs.

## Acceptance and verification

Failure cases and the real CLI dispatch path are covered with temporary media.

- Full pytest: 639 passed using the `mediaStudio` Conda environment.
- `python -m organiseMyProjects.runLinter .`: changed code passes; 10 existing
  findings remain in the unrelated standard-logging script `rugbyAudit.py`.
- `python -m organiseMyProjects.runLinter --markup`: passed after documentation fixes.
- `git diff --check`: passed.
- Requirements 029, 030 and existing 031 retained; next ID is 032 by agreement.

The system launchers lack required package metadata/dependencies; validation uses
`/home/andy/miniconda3/envs/mediaStudio/bin/python`.

## Immediate next action

Squash the verified branch and open the REQ-028 pull request for review.
