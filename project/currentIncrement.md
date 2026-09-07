# Current increment

## Requirement

[REQ-018: TV show folder leading articles](requirements/features/018-tvShowFolderArticles.md)
[REQ-017: Catalogue metadata resolution](requirements/features/017-catalogueMetadataResolution.md)
on feature/catalogue-metadata-resolution.

## Objective

Keep titles as `The Boys` / `The Godfather`, and store folders as
`Boys, The` / `Godfather, The (1972)` for browsing.

## Status

Completed — TV and movie folder cleanup invert a leading `The` on the
folder only; catalogue titles stay in natural order.
Record the best existing movie/TV metadata offline and preserve durable provider
IDs across replacements. Reuse organiser readers; refresh descriptions from
current evidence. No provider identification or media mutations.

## Status

Implementation and acceptance verification complete; ready for review.

## Verification result

- pytest
- `git diff --check`
- Ten new production-path cases cover movie MCM/library/name/folder resolution,
  XML-only folders, TV source priority and identity scope, series-key episode
  lookup, season zero, durable fallback, refreshed descriptions and independent
  replacement. Network, input and provider/enrichment guards cover every case.
- Full pytest suite: 436 passed, including migrations and REQ-016.
- black --check . with installed Black 26.3.1: four unchanged files require
  formatting (organiseMyVideo/__main__.py, organiseMyVideo/grokGallery.py,
  tests/test_mediaCatalogue.py and tests/test_grokGallery.py). Changed Python
  files pass. Unrelated formatting was left alone.
- Both requested ./tests/runLinter.py commands fail with permission denied.
  Invoking with python3 requires PYTHONPATH=/home/andy/Source/organiseMyProjects
  because the shared package is not installed for that interpreter.
- Those fallback naming and markup runs completed: existing repository findings
  remain. Catalogue code/new tests pass naming checks; changed Markdown passes.
  Existing metadata/video logging findings are unchanged.
- git diff --check passes. No acceptance verification remains; repository-wide
  formatting/lint remediation is outside this increment.

## Deferred risks and next action

Review the changes. feature/canonical-media-identification owns ambiguous
provider matches, provenance modelling, conflicting partial IDs and identity
continuity across renamed paths. Reconciliation deliberately uses stable local
paths and cannot distinguish a different media item replacing one at the same
path. No fresh identification is attempted to resolve those cases.
