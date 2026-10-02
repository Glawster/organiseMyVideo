# REQ-036: Incoming media preparation workflow

## Role

Implement and verify `project/requirements/features/036-incomingMediaPreparation.md`.

## Objective

Make `media clean` a narrowly scoped incoming/staging preparation command and
reuse its name-normalisation logic safely before classification without weakening
REQ-029's non-destructive `media scan` guarantee.

## Implementation plan

### Phase 1 - Separate pure name normalisation from filesystem mutation

- Extract the current staged release/site-prefix cleanup into a pure function/service
  that returns a cleaned candidate name without renaming anything.
- Keep the existing mutating `cleanNames()` path as a thin caller of that pure
  normaliser plus the filesystem safety boundary.
- Preserve current dry-run/`--confirm` semantics.

### Phase 2 - Restrict `media clean` to the incoming tree

- Keep `cleanNames()` scoped to the selected `sourceDir`.
- Keep recursive empty/sample-only detection scoped beneath that same source root.
- Remove `_normaliseSeasonFolders(...)` from the `media clean` command path.
- Do not trigger library-root discovery or catalogue-wide reconciliation from clean.
- Add guard tests proving no mutation can escape the selected source tree.

### Phase 3 - Reuse cleaning before classification

- In scan/classification paths that inspect incoming media, feed folder/file names
  through the pure normaliser before parsing.
- Do not rename staged content from `media scan`.
- Prefer evidence in this order: provider IDs/trusted metadata, feature filename,
  cleaned enclosing folder, then heuristics.
- If folder detection fails but the feature filename parses cleanly, continue with
  the filename-derived candidate.
- Keep fuzzy matches as review suggestions only.

### Phase 4 - Finish REQ-035 follow-ons exposed by production scans

- Broaden ancillary sample detection beyond exact `Sample.mkv` to recognisable
  sample-token patterns and sample directories.
- Classify `*-part2.*` as multi-part feature media rather than duplicate feature.
- Classify obvious release-marker/non-feature files such as a tiny `RARBG.COM.mp4`
  as ancillary/junk candidates without deletion during scan.
- Preserve valid punctuation spacing around `&`, apostrophes and parentheses.
- Canonicalise `TAYLOR SWIFT | THE ERAS TOUR` as
  `Taylor Swift - The Eras Tour`.
- Keep substantive title/year changes blocked as identity conflicts.

### Phase 5 - Summary/audit integration

- Keep summaries under `applicationStateDirectory()` / `~/.local/state/organiseMyVideo/`.
- Group movie folder and feature-file rename proposals in aligned blocks.
- Include a final `Needs further investigation` section.
- Record folder location on identity conflicts.
- Include same-identity merge candidates, possible duplicates and unresolved
  collisions; omit items confidently classified as ignored ancillary media.
- Coordinate with REQ-030's eventual one-summary-per-run filename requirement;
  do not regress current summary content while that separate audit work remains ToDo.

### Phase 6 - Scan/organise responsibility cleanup

- Ensure `media scan` reports expected canonical paths but does not mutate media,
  even when compatibility `--confirm` is supplied.
- Ensure actual canonical renames, season-folder normalisation, moves and merges
  live under `media organise`.
- Keep merge execution behind `media organise --merge --confirm`.

## Verification

- Unit tests for the pure incoming-name normaliser, including `www.UIndex.org - ...`.
- Source-boundary tests for `media clean`.
- Test proving `media clean` no longer calls `_normaliseSeasonFolders`.
- Test proving scan can consume cleaned candidate names without calling rename/delete.
- Regression tests for sample variants, multipart features, release-marker junk,
  punctuation spacing, Taylor Swift casing/separator and identity conflicts.
- Summary tests for state-directory path, aligned grouping, investigation section
  and identity-conflict folder path.
- Run full `pytest`, `runLinter`, `manageProject --check`, and `git diff --check`.

## Suggested implementation order

1. Finish/document the current REQ-035 branch changes and run the full suite.
2. Merge REQ-035 to `main` once green.
3. Create `feature/036-incoming-media-preparation` from updated `main`.
4. Implement Phases 1-3 first; these establish the clean/scan boundary.
5. Move any remaining library mutation still reachable from scan into organise
   under REQ-029, reusing existing logic rather than duplicating it.
6. Complete the outstanding collision/sample/multipart cases and audit summary
   integration where not already delivered.

## Handoff

Report changed files, responsibility moves between clean/scan/organise, tests run,
and any remaining legacy compatibility path that can still mutate during scan.
