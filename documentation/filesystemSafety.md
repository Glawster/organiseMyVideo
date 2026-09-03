# Filesystem safety

All production file changes pass through `FilesystemOperations`. The service
is the common boundary for directory creation, atomic text and byte writes,
copies, moves, renames, quarantine, and removal of known-empty directories.

## Dry-run behaviour

Media operations use the command's `dryRun` value. In dry-run mode the service
validates the request and records a `FilesystemOperation`, but does not change
the filesystem. Configuration, cache, catalog, session, and summary files are
classified as `application-state`; workflows that have always maintained this
state during dry-run use a separately confirmed instance of the same service.

Missing sources, identical source and destination paths, and existing
destinations are rejected. This means a second file targeting an existing
library filename remains at its source and is reported as an error rather than
overwriting the stored file.

## Copy and move recovery

Writes and copies are created under a unique temporary name next to the final
destination, flushed, and then atomically finalized. Copies are verified using
file size and SHA-256.

A same-filesystem move uses an atomic rename. If the operating system reports
a cross-filesystem move, the service copies to a temporary destination,
verifies it, finalizes it, and removes the source only after verification. If
copying or verification fails, incomplete temporary output is removed and the
source remains intact.

## Quarantine

Cleanup no longer permanently deletes media, torrent files, or Grok session
files. It moves them into a timestamped `.organiseMyVideo-quarantine` directory
on the owning source filesystem. Name collisions receive a numeric suffix.

Quarantined content is eligible for a future explicit purge after 30 days, but
this release has no purge command and never removes it automatically. Recovery
is manual: inspect the recorded/logged quarantine destination and move the item
back to its desired location.

The only direct cleanup outside this boundary is deletion of the private
temporary copy of Firefox's cookie database after session import. That copy is
created solely for SQLite reading, resides in the operating-system temporary
directory, and contains no library media.

## Developer contract

New production code must receive or create a `FilesystemOperations` instance
and must not call mutation methods on `Path`, `os`, or `shutil` directly.
Focused tests belong in `tests/test_filesystemOperations.py`; workflow tests
must also prove their writes route through the boundary. See
[ADR-003](../project/adr/003-filesystemSafetyBoundary.md) and
[REQ-007](../project/requirements/features/007-filesystemSafety.md).
