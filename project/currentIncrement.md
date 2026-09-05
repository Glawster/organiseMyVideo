# Current increment

## Requirement

[REQ-016: Catalogue media identities](requirements/features/016-catalogueMediaIdentities.md)
on `feature/catalogue-identities`.

## Objective and scope

Prepare external TV identities, home-video storage, and removable-volume kinds
through additive SQLite changes and compatible dataclasses. Preserve current
movie, TV, and camera scan behaviour. REQ-014 and REQ-015 scans remain out of scope.

## Status

Implementation and acceptance verification complete; ready for review.
Existing TV identity support is retained. Home-video schema and volume-kind
persistence are added. REQ-010's completed scope is unchanged.

## Acceptance and verification

- Eight new tests cover legacy migration via all three list APIs, preserved
  rows/indexes, repeated upgrades, TV identity round trips, home-video schema
  constraints, and SD/USB model persistence.
- Full suite: 416 passed.
- Project-pinned Black 25.1.0: all 28 Python files pass.
- Naming lint: existing HEAD findings unchanged; new catalogue tests and
  mediaCatalogue pass. Ran the module through the local organiseMyProjects
  checkout because the installed launcher lacks package metadata.
- Markup lint: existing repository violations; no findings in changed Markdown.
- `git diff --check`: passed.
- No acceptance verification remains; repository-wide lint cleanup is separate.

## Deferred design and next action

Review this increment. For `feature/catalogue-metadata-resolution`, decide how
provider provenance and identity reconciliation should preserve catalogue-only
IDs across scans: current movie/TV replacement can discard them. Do not change
that scan contract within REQ-016.
