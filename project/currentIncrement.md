# Current increment

## Objective and status

REQ-035 movie identity conflict detection is complete. Movie scan and movie
move report a different title or any release-year change and leave the folder
and file in place. Punctuation-safe names and already capitalised titles are
unchanged by that guard. The requirement and the requirements index both
record REQ-035 as Completed.

## Accepted scope

- Compare the parsed folder and filename with the metadata about to be applied.
- Refuse an unresolved title or year conflict before renaming, before rewriting
  `movie.xml`, and before fetching online metadata to choose a film.
- Report the current and proposed title and year, the evidence source, known
  provider IDs, and runtime text already stored.
- Keep filesystem-safe punctuation changes, leading-`The` folder names, and
  capitalisation of an all-lowercase title.
- Refuse the same conflict on a dry-run and on a confirmed run.

## Final verification

Verified in the `mediaStudio` Conda environment:

- Full `pytest` suite: 795 passed.
- `runLinter`: no findings.
- `runLinter --markup`: no remaining issues.
- `manageProject --check`: zero failures and zero warnings.
- Black was applied to the changed Python files, and `git diff --check` passed.

## Remaining work and immediate next action

REQ-035 verification and documentation are complete. No implementation or
verification work remains for this increment. Select the next increment through
the requirements index when further work is requested.
