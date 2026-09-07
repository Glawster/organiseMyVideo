# Current increment

## Requirement

[REQ-019: Catalogue metadata resolution](requirements/features/019-catalogueMetadataResolution.md)
on `feature/catalogue-metadata-resolution`.

## Objective

Record the best existing movie and TV metadata offline, preserve durable provider
IDs across replacements, and refresh descriptions from current local evidence
without provider identification or media mutations.

## Status

Completed — implementation and final combined-branch verification are complete;
ready to merge.

## Verification result

- Production-path tests cover movie MCM/library/name/folder resolution, XML-only
  folders, TV source priority and identity scope, series-key episode lookup,
  season zero, durable SQLite provider-ID fallback, refreshed descriptions and
  independent movie/TV replacement.
- A dedicated regression test verifies that current MCM movie, series and episode
  provider IDs replace older provider IDs persisted in SQLite.
- Network, input and provider/enrichment guards fail the tests if a catalogue
  rescan attempts fresh identification.
- Full `pytest` run on the current combined tree is green.
- `git diff --check` produces no output.
- Black identified three combined-tree formatting changes; those were applied.
- `./tests/runLinter.py` reports no findings in the REQ-019 catalogue-resolution
  test file. Remaining naming findings are pre-existing or interface-shaped test
  helpers outside this increment.
- `./tests/runLinter.py --markup` reports repository-wide pre-existing Markdown
  findings outside the REQ-019 changed Markdown.

## Deferred risks and next action

`feature/canonical-media-identification` owns ambiguous provider matches,
provenance modelling, conflicting partial IDs and identity continuity across
renamed paths. Reconciliation deliberately uses stable local paths and cannot
distinguish a different media item replacing one at the same path. No fresh
identification is attempted to resolve those cases.

REQ-019 is complete and ready to merge to `main`.
