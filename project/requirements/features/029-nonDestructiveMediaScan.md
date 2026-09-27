# 029: Non-destructive media scan

## Status

ToDo

## Outcome

As a media-library maintainer, I need every `media scan` action to be
non-destructive so that I can inspect library integrity, naming, metadata and
catalogue state without risking changes to media files or folders.

Filesystem and embedded-media mutations belong to explicit maintenance
commands. `media organise` owns arrangement, renames, moves and merges;
`media clean` owns removals and cleanup. Those commands remain dry-run by
default and require `--confirm` before changing media.

## Context

The current `media scan` command exposes behaviour inherited from the older
rescan workflow. That workflow can repair movie naming/metadata and rename TV
episodes when confirmed. This makes the word "scan" ambiguous: an inspection
command can also become a media-mutation command.

The CLI should make the safety boundary obvious from the command name.

## Command contract

### `media scan`

`media scan` and all of its variants are observational with respect to the
media library.

Examples:

```bash
organiseMyVideo media scan
organiseMyVideo media scan --all
organiseMyVideo media scan --show Farscape
```

A scan may:

- walk configured movie and TV library roots;
- inspect filenames, folders and supported media metadata;
- resolve already-known movie, series and episode identities;
- identify malformed or non-canonical names;
- calculate and report the canonical filename/folder that would be expected;
- report missing, conflicting or suspicious metadata;
- refresh derived OMV catalogue/application state.

A scan must not:

- rename a media file or directory;
- move a media file or directory;
- merge folders;
- delete files or directories;
- rewrite embedded media metadata;
- create or replace media-library artwork/sidecars as a repair action;
- make any other change to the user-owned media filesystem.

Because it cannot mutate media, `media scan` does not require `--confirm`.
If supplied for compatibility during migration, `--confirm` must not enable
media mutations and should ultimately be rejected or removed from the scan
parser.

### `media organise`

`media organise` owns changes whose purpose is to arrange media into the
canonical library structure, including:

- file and folder renames;
- canonical TV episode filenames;
- canonical movie/show folder naming;
- season-folder normalisation;
- moves required by the organiser;
- provider-identified folder merges when `--merge` is selected.

It remains dry-run by default. `--confirm` is required before filesystem or
embedded-metadata mutations are performed.

### `media clean`

`media clean` owns destructive cleanup such as removal of confirmed-empty or
otherwise explicitly cleanable material. It remains dry-run by default and
requires `--confirm` before deletion.

## Reporting

When a scan identifies a naming problem, it should report both the existing
path and the proposed canonical path without performing the rename.

Example:

```text
naming issue
  current:  /mnt/video1/TV/Farscape/Season 1/Farscape.S01E01.720p.WEB.x264.mkv
  expected: /mnt/video1/TV/Farscape/Season 1/Farscape - S01E01 - Premiere.mkv
```

The same planned correction may subsequently be presented by
`media organise`; only a confirmed organise run may execute it.

## Application-state exception

The non-destructive guarantee applies to user-owned media and embedded media
metadata. A scan may update derived application state such as the SQLite media
catalogue, scan timestamps, cached identity data and scan summaries, provided
those writes do not alter the media filesystem.

## Compatibility

- Preserve `media scan --all` exhaustive inspection behaviour.
- Preserve `media scan --show NAME` focused inspection behaviour.
- Preserve configured-source and explicit `--source` resolution.
- Retain legacy CLI aliases only as compatibility adapters; they must respect
  the same non-destructive scan boundary.
- Existing repair logic should be reused from `media organise` where
  practical rather than duplicated.

## Acceptance criteria

1. Given any `media scan` invocation, when the command completes, then no
   media file or directory has been renamed, moved, merged, deleted or created
   as a repair action.
2. Given any `media scan` invocation, when media metadata is inspected, then
   embedded metadata is not rewritten.
3. Given a malformed TV or movie filename, when `media scan` runs, then the
   issue and proposed canonical name are reported without changing the file.
4. Given the same malformed name, when `media organise` runs without
   `--confirm`, then the proposed repair is reported but the filesystem is
   unchanged.
5. Given the same repair and `media organise --confirm`, when safety checks
   pass, then the supported rename/organisation action is executed.
6. Given a merge candidate, only `media organise --merge --confirm` may
   mutate the library.
7. Given a cleanup candidate, only the appropriate confirmed cleanup command
   may delete it.
8. `media scan` may refresh derived SQLite catalogue/application state
   without requiring `--confirm`.
9. Tests prove that scan code cannot reach mutating filesystem operations even
   when a compatibility `--confirm` flag is supplied.
10. Public CLI documentation describes the boundary as **scan = observe,
    organise = arrange, clean = remove**.
11. Existing scan filters, catalogue refresh, source resolution and focused
    show scanning continue to work.
12. `pytest`, `runLinter` and `git diff --check` pass.

## Dependencies and decisions

- [REQ-006](006-cliArchitecture.md)
- [REQ-007](007-filesystemSafety.md)
- [REQ-010](010-sqliteMediaCatalogue.md)
- [REQ-017](017-mergeDuplicateTvFolders.md)
- [REQ-018](018-tvShowFolderArticles.md)
- [REQ-020](020-combinedMediaScan.md)
- [ADR-003](../../adr/003-filesystemSafetyBoundary.md)
- [ADR-008](../../adr/008-sqliteMediaCatalogue.md)

## Change history

- 2026-09-27: created to make scan commands explicitly non-destructive and
  move repair mutations behind explicit organise/clean command boundaries.
