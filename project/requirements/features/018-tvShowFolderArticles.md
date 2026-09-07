# 018: TV show folder leading articles

## Status

Completed

## Outcome

TV show and movie *folders* that begin with ``The`` are stored as
``Name, The`` or ``Name, The (Year)`` so titles sort under the significant
word. The show or movie *title* itself stays ``The Name``. Library cleanup
finds incorrectly formed folders and renames or merges them into that
canonical folder form.

## Context

New organisation already uses `_buildTvShowFolderName`, so incoming files
for "The Boys" land in `Boys, The`. Existing libraries still contain
`The Boys`. Those folders should be repaired as part of TV library
cleanup, using the same dry-run/`--confirm` contract as season-folder
normalisation.

## Scope

- Canonical on-disk folder form for a leading English article ``The`` is
  ``Remainder, The`` (movies: ``Remainder, The (Year)``).
- Display titles, MCM XML, catalogue names, and media filenames keep
  ``The Remainder``.
- Scan configured TV and movie library roots for folders whose names are
  not in that form.
- Rename when the canonical name is unused.
- If both ``The Boys`` and ``Boys, The`` exist on the same root, merge
  unique contents into ``Boys, The`` without overwriting; keep
  duplicates/conflicts.
- Run during `media organise`, `media organise --merge`, and
  `media clean`.
- Refresh the TV catalogue after confirmed folder changes.

## Out of scope

- Inverting ``A`` / ``An``.
- Rewriting episode or movie filenames from ``The.Boys.S01E01`` /
  ``The Godfather (1972).mkv`` into comma form.
- Cross-volume merges of ``The Boys`` on one disk and ``Boys, The`` on
  another; that remains provider-identity merge (REQ-017).

## Acceptance criteria

1. Given a TV root containing `The Boys`, when library folder
   normalisation runs with `--confirm`, then the folder is renamed to
   `Boys, The`.
2. Given `Boys, The` already exists beside `The Boys`, when
   normalisation is confirmed, then unique files move into `Boys, The`
   and the empty source is removed.
3. Given dry-run, when normalisation runs, then no folders are renamed.
4. Given `Breaking Bad` or a folder already named `Office, The`, when
   normalisation runs, then those folders are left unchanged.
5. Given a movie root containing `The Godfather (1972)`, when library
   folder normalisation is confirmed, then the folder is renamed to
   `Godfather, The (1972)` while the title remains `The Godfather`.
6. Given `media organise`, `media organise --merge`, or `media clean`,
   when they run, then this TV and movie folder normalisation is included.

## Dependencies and decisions

- [REQ-017](017-mergeDuplicateTvFolders.md) for same-root merge-without-overwrite.

## Verification

Temporary TV roots, `pytest`, `git diff --check`.

## Traceability

- Implementation: `organiseMyVideo/showFolders.py`,
  `organiseMyVideo/video.py`, `organiseMyVideo/__main__.py`
- Tests: `tests/test_showFolders.py`
- Documentation: [Command-line interface](../../../documentation/commandLineInterface.md)

## Change history

- 2026-09-07: created and completed — operator asked that shows such as
  "The Boys" be stored as `Boys, The` and that existing folders be
  cleaned up.
