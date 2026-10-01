# Implement REQ-035: Movie identity conflict detection

## Requirement

Implement [REQ-035](../features/035-movieIdentityConflictDetection.md),
following the repository instructions. This prompt assigns that requirement.
The requirement remains the contract.

## Boundaries

Distinguish a safe movie-name tidy-up from a different film or a different
release year. Keep legitimate punctuation, spacing, filesystem-safe
substitution, leading-`The` inversion, and capitalisation of an all-lowercase
title. Do not replace an already capitalised title with a less capitalised
one.

On an unresolved conflict, refuse the rename in both dry-run and confirmed
runs, leave `movie.xml` unchanged, and do not fetch online metadata to pick a
winner. Report the current and proposed title and year, the evidence source,
known provider IDs, and any runtime already stored.

Do not implement REQ-029's scan/organise split, and do not add an operator
override that accepts the conflicting identity.

## Verification and handoff

Cover `13 minutes (2021)` against `One Second Forever (2021)`, the named year
mismatches, `Anyone But You` casing, a punctuation-only rename, and both
dry-run and confirmed refusal. Use temporary paths. Run the full test suite,
linters, and project checks.

Report the files changed, the classification rules, the acceptance criteria,
the commands and results, ambiguous cases left unresolved, and any follow-on
requirement. Do not broaden the change beyond REQ-035.
