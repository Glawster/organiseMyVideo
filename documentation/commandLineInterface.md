# Command-line interface

## Entry points

The module and installed console script are equivalent:

```bash
python -m organiseMyVideo --help
organiseMyVideo --help
```

Both call `organiseMyVideo.__main__:main`. The application uses
`organiseMyProjects.logUtils` directly and intentionally maintains log and
configuration files in its documented user-state locations. Importing the
package must not copy, move, rename, or delete media.

## Canonical commands

New scripts and documentation should use the object/action hierarchy:

```bash
organiseMyVideo media organise [SOURCE]
organiseMyVideo media organise [-s SOURCE]
organiseMyVideo media organise --merge
organiseMyVideo media clean [SOURCE]
organiseMyVideo media clean [-s SOURCE]
organiseMyVideo library rescan [SOURCE] [--target both|movies|tv]
organiseMyVideo library rescan [-s SOURCE] [--target both|movies|tv]
organiseMyVideo torrent maintain [SOURCE] [--clean-names]
organiseMyVideo torrent maintain [-s SOURCE] [--clean-names]
organiseMyVideo grok --import-firefox
organiseMyVideo grok --reset
organiseMyVideo grok --scan
organiseMyVideo camera inventory [SOURCE] --card ID
organiseMyVideo camera inventory [-s SOURCE] --card ID
organiseMyVideo camera inventory --card ID
```

Every canonical action that accepts one filesystem source accepts either the
positional `SOURCE` form or `-s SOURCE` / `--source SOURCE`. The two forms are
aliases for the same value. Existing positional commands remain valid.

Every command level supports `--help`. A source supplied to a canonical command
must exist and be a directory before domain services are constructed.

## Universal options

The executable supports:

- `--help` for contextual help;
- `--version` for the installed package version;
- `--confirm` to authorize changes, with dry-run as the default;
- `--debug` for debug-level logging; and
- `--quiet` for errors-only logging.

Shared behavioral options may be placed before the command hierarchy or after
the final action. `--debug` enables the DEBUG logging level.

The top-level `-s/--source` remains part of the legacy compatibility interface.
Canonical commands own their own `-s/--source` alias so a command such as
`organiseMyVideo camera inventory -s /media/card` is valid and does not depend
on where the option appears relative to the command hierarchy.

## Grok actions

The `grok` command requires exactly one mutually exclusive action:

- `--import-firefox` imports the authenticated grok.com session from Firefox;
- `--scan` scans and downloads the account's generated Imagine media; and
- `--reset` quarantines saved session configuration.

Add `--confirm` to perform writes; otherwise the selected action uses dry-run
behaviour where applicable.

## Camera inventory

The `camera inventory` action catalogues a mounted SD card or copied card
directory against an operator-assigned positive integer card ID. The source may
be supplied positionally or with `-s/--source`. GoPro, DJI, and dash-cam layouts
are recognised, as are Canon-style SLR `DCIM/100CANON` trees. Dry-run prints
date range, sold card size (32, 64, 128, or 256 GB), free space, and file
counts. `--confirm` writes a SQLite snapshot in the
shared media catalogue, writes `organiseMyVideo.NNN` onto the card, and
describes sampled `.THM` thumbnails (or JPEGs) through xAI. After that file
exists, `--card` may be omitted. To change the ID, pass
`--card NEW --reassign --confirm`. The UI should show card size and remaining
space from `catalogueCardsList()` rather than USB-reader brand strings. USB
thumb drives will use the same numbered list
([REQ-015](../project/requirements/features/015-usbVolumeInventory.md)).
`--brand` remains optional when the operator wants to store a make by hand.
Omitting `SOURCE` shows the latest stored snapshot for that card ID. See
[Camera card inventory](cameraInventory.md) and
[Media catalogue](mediaCatalogue.md).

`media organise --merge` consolidates duplicate TV and movie folders that
share a catalogue provider ID into the most complete existing folder.
Dry-run is the default; `--confirm` performs moves. Same-name folders
without IMDb/TMDB (movies) or TVDB/TMDB/IMDb (TV) are not merged. TV show
folders that begin with `The` are stored as `Name, The`; movie folders
as `Name, The (Year)`. Titles and media filenames keep `The Name`. Season
folders are rewritten to unpadded `Season N`. Organise and merge own library
folder normalisation; `media clean` does not. Merge discovers duplicates from the current
filesystem, then reconciles catalogue location state for every storage root
it could list. That reconcile runs on a dry-run as well as after a confirmed
merge, including when no duplicate group was found. A confirmed move also
points the moved catalogue row at the new path and keeps the old path as
`stale`.

`media locate` reads catalogued TV show folders. `--show NAME` selects a
case-insensitive exact or partial name. Omitting `--show` lists every
catalogued show. Each folder is printed as `current`, `stale`, or
`unverified`. `current` means an authoritative scan saw the folder and it is
still present. `stale` means that scan's root was listed and the folder was
absent. `unverified` means the catalogue has not confirmed the path, or the
folder is missing and its root was not listed. Locate does not delete rows.

`media scan` is non-destructive. It inspects movie and TV libraries, reports
naming/metadata/catalogue issues and proposed canonical paths, and may refresh
application/catalogue state without mutating media. Use `media scan --show NAME`
for focused inspection or `media scan --all` for exhaustive episode-level
inspection and catalogue refresh. The older `library rescan` command can still target one side
independently for compatibility and retains exhaustive behaviour. The Qt browser is
expected to query the catalogue rather than walk disks.

A different movie title, or any different release year, is an identity conflict
during movie scan and when a parsed movie is moved. The report names the
current title and year, the proposed title and year, the evidence that
disagreed (usually `movie.xml`), and any IMDb id, TMDB id, or runtime already
stored. The folder and file stay where they are, `movie.xml` is left
unchanged, and no online lookup is made to decide which film is correct.
Punctuation, spacing, and filesystem-safe substitutions are proposed when the
title and year agree. A metadata title that only changes capitals does not
replace an already capitalised title. Dry-run and `--confirm` both refuse the
conflict. Apply approved canonical repairs using `media organise --confirm`;
scan aliases remain observational even with compatibility `--confirm`.

The folder and filename are made safe before that rename is planned.
`\`, `/`, `:`, and `|` become ` - `. `?`, `*`, `<`, `>`, and `"` are removed,
so a title such as `Thunderbolts*` is planned as `Thunderbolts` and is not
passed to `rename()`. Removing those characters does not make a different
title or year safe. Recognisable sample variants and video inside sample folders are not treated as
feature media. When the safe folder or file already exists, the scan
reports a same-identity merge candidate, a possible duplicate feature file,
ignored ancillary media, or an unresolved collision. Neither side is
overwritten or deleted. A merge of the two folders is not performed.

## Incoming media cleaning

`media clean [SOURCE]` is restricted to the selected incoming/staging source
tree. It cleans staged release/site-name noise and may quarantine/remove empty
or sample-only staged folders when confirmed. It does not normalise established
TV show/season folders, rename library media, merge folders, or perform
catalogue-wide reconciliation.

The normal workflow is:

```bash
organiseMyVideo media clean
organiseMyVideo media clean --confirm
organiseMyVideo media scan
organiseMyVideo media organise
```

`media scan` may reuse the same name-normalisation rules in memory for
classification without filesystem writes. Trusted metadata takes precedence,
then the feature filename, then the cleaned enclosing folder. Cleanup quarantine
is retained under `.organiseMyVideo-quarantine` inside the selected source;
symlinks and retained quarantine are excluded from subsequent cleanup.

Multipart features retain their `-partN` suffix. Bounded sample tokens and
explicit release markers such as `RARBG.COM.mp4` are ancillary, never duplicate
features. All-uppercase movie titles receive readable casing; for example,
`TAYLOR SWIFT | THE ERAS TOUR` becomes `Taylor Swift - The Eras Tour`.
Already capitalised titles such as `Anyone But You` are preserved.

Run summaries are application state and are written under
`~/.local/state/organiseMyVideo/` (or `XDG_STATE_HOME`). They group related
movie folder/file renames and finish with a `Needs further investigation`
section for unresolved identity conflicts, merge candidates and possible
duplicates.

## Compatibility interface

The previous flags and the no-command organiser form remain supported without
deprecation warnings during Phase 3. Examples include:

```bash
organiseMyVideo --source SOURCE
organiseMyVideo --source SOURCE --clean
organiseMyVideo --source SOURCE --rescan --movie
organiseMyVideo --source SOURCE --torrent --clean
```

The former `--non-interactive` and `--no-curses` options have been removed.
Use `media organise --auto` for unattended processing. The former top-level
Grok flags and `gallery` commands have been replaced by the `grok` options
shown above.

Canonical commands remain stable and documented for at least one minor release
before legacy warnings may begin. Removing a legacy form requires a later major
release, a dedicated requirement, migration notes, and evidence that maintained
automation has migrated.

## Status codes

Successful execution returns zero. Argument errors, conflicting modes, missing
canonical source directories, and handled runtime failures return non-zero.
Dry-run success still returns zero because no requested mutation failed.
