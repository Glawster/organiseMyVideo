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
- Remove unsupported filename characters where identity remains clear, but preserve
  a readable separator when the unsupported character separates title parts; for
  example `TAYLOR SWIFT | THE ERAS TOUR` should become
  `Taylor Swift - The Eras Tour`.
- Apply the same safe-name rule to both the movie folder and movie filename.
- Exclude recognisable ancillary sample variants and sample-directory media from
  canonical feature-file reconciliation.
- Classify multipart files such as `*-part2.*` separately from duplicate feature
  files, and classify obvious release-marker/non-feature files as ancillary/junk
  candidates without destructive scan behaviour.
- Treat `Downloaded From ... .txt` release-note files as disposable junk
  candidates. Scan may report them, but must not delete them.
- Classify existing-target collisions instead of emitting only generic errors:
  ancillary media, same-identity folder merge candidate, possible duplicate
  feature file, or unresolved collision.
- Inspect same-identity collision contents recursively enough to distinguish
  top-level feature files from feature media nested under another canonical
  movie folder. A nested same-identity feature should be reported as a
  structural/complementary reconciliation case rather than a plain duplicate.
- Before expensive content comparison, use conclusive cheap checks first:
  different sizes mean different files; matching device+inode means the same
  physical file. Equal size/name/timestamp/link count alone is insufficient.
- When a genuine large-file content comparison is required, emit visible
  secondary progress so the enclosing library scan does not appear stalled.
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

For same-identity reconciliation, distinguish substantive media from disposable
release-note junk when comparing folder contents. Report nested feature folders
and junk candidates explicitly so an operator can see why two folders are
complementary. Do not perform the destructive merge or junk deletion during
`media scan`; any confirmed cleanup belongs under `media organise`.

## Verification

Add focused regression tests for every acceptance criterion, including:

- `13 minutes (2021)` versus `One Second Forever (2021)`;
- release-year disagreements;
- `Anyone But You` versus `Anyone but You`;
- safe punctuation-only normalisation;
- canonical names containing `?`, `|`, `*`, `:`, `<`, `>`, and `"`;
- the real-library examples `Nativity 3 - Dude, Where's My Donkey?!`,
  `TAYLOR SWIFT | THE ERAS TOUR` -> `Taylor Swift - The Eras Tour`, and
  `Thunderbolts*`;
- folder and filename destinations being safe before `rename()` is called;
- sample-name variants/sample directories not being treated as the feature;
- multipart `-part2` files not being treated as duplicate features;
- obvious release-marker/non-feature files being reported without deletion;
- `Downloaded From glodls.to.txt`, `Downloaded From The Pirate Bay.txt`, and
  `Downloaded From torrentgalaxy.to.txt` being classified as disposable junk;
- same-identity folder collisions such as `Inside Out 2 (2024)_` versus
  `Inside Out 2 (2024)` being reported as reconciliation/merge candidates;
- the real Inside Out 2 layout where the canonical folder has metadata/artwork
  while the underscore folder contains a nested `Inside Out 2 (2024)` feature
  folder, proving the structure is reported as complementary reconciliation;
- equal-sized different-inode feature files not being assumed identical;
- matching device+inode files bypassing full content comparison;
- large-file comparison progress being observable;
- existing canonical feature targets being reported as possible duplicate or
  unresolved collisions without overwriting; and
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
