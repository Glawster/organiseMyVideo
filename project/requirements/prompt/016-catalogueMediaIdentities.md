# Requirement: 016 — Catalogue media identities

## Assignment

Implement and verify all acceptance criteria in
[REQ-016](../features/016-catalogueMediaIdentities.md) on
`feature/catalogue-identities`. Read repository guidance and ADR-008/009.

## Boundaries

Keep changes in the catalogue schema/dataclasses, necessary camera persistence
mapping, tests, and documentation. Reuse existing TV identity support and
additive upgrades. Preserve current scan, parsing, and metadata-resolution
behaviour. Do not implement REQ-014, REQ-015, scraping, media mutations, or a
card-to-removableVolume API migration. Use camelCase and no new dependencies.

Update `documentation/mediaCatalogue.md`, the requirements index, and current
increment. Amend an ADR only for a genuinely changed decision. Preserve the
completed scope of REQ-010.

## Verification and handoff

Run `pytest`, `black --check .`, `runLinter .`, `runLinter --markup`, and
`git diff --check`. Report changed files, schema changes, migration strategy,
added tests, test/lint results, and design issues deferred to
`feature/catalogue-metadata-resolution`.
