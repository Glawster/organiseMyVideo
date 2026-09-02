# Command-line interface

## Entry points

The module and installed console script are equivalent:

```bash
python -m organiseMyVideo --help
organiseMyVideo --help
```

Both call `organiseMyVideo.__main__:main`. Importing `organiseMyVideo` as a
library does not initialize application logging or create application-state
directories; logging is initialized only after executable argument parsing and
validation.

## Canonical commands

New scripts and documentation should use the object/action hierarchy:

```bash
organiseMyVideo media organise [SOURCE]
organiseMyVideo media clean [SOURCE]
organiseMyVideo library rescan [SOURCE] [--target both|movies|tv]
organiseMyVideo torrent maintain [SOURCE] [--clean-names]
organiseMyVideo gallery download
organiseMyVideo gallery import-session
organiseMyVideo gallery reset-session
organiseMyVideo grok generate PROMPT
organiseMyVideo grok list
organiseMyVideo grok download
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

## Compatibility interface

The previous flags and the no-command organiser form remain supported without
deprecation warnings during Phase 3. Examples include:

```bash
organiseMyVideo --source SOURCE
organiseMyVideo --source SOURCE --clean
organiseMyVideo --source SOURCE --rescan --movie
organiseMyVideo --source SOURCE --torrent --clean
organiseMyVideo --grok
organiseMyVideo --import-firefox-session
organiseMyVideo --reset-grok
```

Canonical commands remain stable and documented for at least one minor release
before legacy warnings may begin. Removing a legacy form requires a later major
release, a dedicated requirement, migration notes, and evidence that maintained
automation has migrated.

## Status codes

Successful execution returns zero. Argument errors, conflicting modes, missing
canonical source directories, and handled runtime failures return non-zero.
Dry-run success still returns zero because no requested mutation failed.
