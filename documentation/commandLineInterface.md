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
organiseMyVideo media clean [SOURCE]
organiseMyVideo library rescan [SOURCE] [--target both|movies|tv]
organiseMyVideo torrent maintain [SOURCE] [--clean-names]
organiseMyVideo grok --import-firefox
organiseMyVideo grok --reset
organiseMyVideo grok --scan
organiseMyVideo camera inventory SOURCE --card ID
organiseMyVideo camera inventory --card ID
```

Every command level supports `--help`. A source supplied to a canonical command
must exist and be a directory before domain services are constructed.

## Universal options

The executable supports:

- `--help` for contextual help;
- `--version` for the installed package version;
- `--confirm` to authorize changes, with dry-run as the default;
- `--verbose` for detailed logging; and
- `--quiet` for errors-only logging.

Shared behavioral options may be placed before the command hierarchy or after
the final action. `--debug` remains a compatibility alias for `--verbose`.

## Grok actions

The `grok` command requires exactly one mutually exclusive action:

- `--import-firefox` imports the authenticated grok.com session from Firefox;
- `--scan` scans and downloads the account's generated Imagine media; and
- `--reset` quarantines saved session configuration.

Add `--confirm` to perform writes; otherwise the selected action uses dry-run
behaviour where applicable.

## Camera inventory

The `camera inventory` action catalogues a mounted SD card or copied card
directory against an operator-assigned positive integer card ID. GoPro, DJI,
and dash-cam layouts are recognised. Dry-run prints date range, sold card
size (32, 64, 128, or 256 GB), free space, and file counts. `--confirm`
writes a SQLite snapshot in the shared media catalogue, writes
`organiseMyVideo.NNN` onto the card, and describes sampled `.THM` thumbnails
(or JPEGs) through xAI. After that file exists, `--card` may be omitted. To
change the ID, pass `--card NEW --reassign --confirm`. The UI should show card
size and remaining space from `catalogueCardsList()` rather than USB-reader
brand strings. USB thumb drives will use the same numbered list
([REQ-015](../project/requirements/features/015-usbVolumeInventory.md)).
`--brand` remains optional when the operator wants to store a make by hand.
Omitting `SOURCE` shows the latest stored snapshot for that card ID. See [Camera card inventory](cameraInventory.md) and
[Media catalogue](mediaCatalogue.md).

`library rescan` also refreshes movie and TV rows in that catalogue from
current storage. The Qt browser is expected to query the catalogue rather
than walk disks.

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
