# REQ-035: Movie identity conflict detection

## Role

Implement and verify the movie identity-conflict safeguards defined by
`project/requirements/features/035-movieIdentityConflictDetection.md`.

## Requirement

The authoritative requirement is:

- `project/requirements/features/035-movieIdentityConflictDetection.md`

Do not redefine its outcome or acceptance criteria in this prompt.

## Objective

Prevent movie scan/organise workflows from treating title or release-year
identity changes as routine renames, while retaining legitimate punctuation,
spacing and filesystem-safe normalisation, preserving the library's
capitalised title convention, and ensuring canonical movie names are made
filesystem-safe before rename planning.

## Constraints

- Follow the repository agent instructions and requirements process.
- Preserve the existing metadata-source priority model unless the requirement
  explicitly requires conflict handling around it.
- Do not solve conflicts by fetching fresh online metadata.
- Do not mutate or repair `movie.xml` as part of this requirement.
- Keep scan behaviour non-destructive in accordance with REQ-029.
- Route any confirmed filesystem mutation through the established filesystem
  safety boundary.
- Do not rely on catching `EINVAL` after an attempted rename as the primary
  filesystem-safety mechanism. Derive a safe destination before collision
  checks, logging, dry-run reporting, and mutation.
- Apply the same deterministic safe-name mapping to both the movie folder and
  the movie filename.
- Do not convert already-capitalised titles to metadata sentence casing; for
  example, do not rename `Anyone But You` to `Anyone but You`.

## Implementation guidance

Introduce a clear distinction between safe naming normalisation and a material
identity change.

At minimum, treat a release-year change as a conflict. Treat a substantive
title change as a conflict while allowing narrowly defined normalisations such
as punctuation, whitespace, filesystem-safe substitutions and existing
article-placement conventions.

Where a conflict is detected, report the current identity, proposed identity,
the metadata/evidence source that produced the proposed value, and useful
supporting evidence such as provider IDs and duration where available.

Extend the existing filesystem-safe naming behaviour beyond the current
colon-only fallback. Canonical metadata containing Windows/NTFS-invalid path
characters such as `:`, `|`, `?`, `*`, `<`, `>`, or `"` must be mapped to a
deterministic safe representation before a destination path is planned. The
mapping must preserve recognisable identity and must not mask a substantive
movie title or year conflict.

## Verification

Add focused regression tests for every acceptance criterion, including:

- `13 minutes (2021)` versus `One Second Forever (2021)`;
- release-year disagreements;
- `Anyone But You` versus `Anyone but You`;
- safe punctuation-only normalisation;
- canonical names containing `?`, `|`, `*`, `:`, `<`, `>`, and `"`;
- the real-library examples `Nativity 3 - Dude, Where's My Donkey?!`,
  `TAYLOR SWIFT | THE ERAS TOUR`, and `Thunderbolts*`;
- folder and filename destinations being safe before `rename()` is called; and
- both dry-run and confirmed workflows.

Run the full repository-standard test and lint checks before handoff.

## Handoff

Report:

- files changed;
- conflict-classification rules introduced;
- acceptance criteria satisfied;
- tests and results;
- any metadata cases deliberately left ambiguous; and
- any follow-on requirement needed for explicit user review/override.
