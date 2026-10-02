# Current increment

## Objective and status

REQ-035 movie identity conflict detection is complete, including the
filesystem-safe naming and collision-classification extension. A different
title or release year is still reported and left in place. Canonical movie
folder and file names are made safe before rename planning. `Sample.mkv` is
not renamed to the feature. An existing canonical folder or file is classified
and neither side is overwritten or deleted. The requirement and the
requirements index both record REQ-035 as Completed.

## Accepted scope

- Compare the parsed folder and filename with the metadata about to be applied.
- Refuse an unresolved title or year conflict before renaming, before rewriting
  `movie.xml`, and before fetching online metadata to choose a film.
- Report the current and proposed title and year, the evidence source, known
  provider IDs, and runtime text already stored.
- Remove `|?*<>"` from a planned movie folder and filename, and keep the
  existing ` - ` substitution for colons and path separators.
- Ignore `Sample.mkv` and video inside a sample folder when reconciling the
  feature filename.
- Classify an existing canonical target as ignored ancillary media, a
  same-identity folder merge candidate, a possible duplicate feature file, or
  an unresolved file collision. Do not merge, overwrite, or delete either side.
- Refuse the same conflict on a dry-run and on a confirmed run.

## Final verification

Verified in the `mediaStudio` Conda environment:

- Full `pytest` suite: 816 passed.
- `runLinter` on the changed Python files: no findings.
- `runLinter --markup`: no remaining issues.
- `manageProject --check`: zero failures and zero warnings.
- Black was applied to the changed Python files, and `git diff --check` passed.

## Remaining work and immediate next action

REQ-035 verification and documentation are complete. No implementation or
verification work remains for this increment. A later requirement can add an
operator action that merges a reported same-identity folder pair or accepts a
reported identity conflict. Select the next increment through the requirements
index when further work is requested.
