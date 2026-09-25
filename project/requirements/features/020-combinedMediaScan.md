# 020: Combined media scan command

## Status

InProgress

## Outcome

As an operator, I need the original movie and TV library scan exposed through
the canonical object/action CLI so that scanning is consistent with the rest of
organiseMyVideo and does not require separate movie/video selection.

## Scope

- Add `organiseMyVideo media scan` as the canonical library-scan command.
- Scan movies and TV together; do not expose movie/video selectors on this command.
- When `--source` is omitted, read the normal source from the `source` setting
  in `~/.config/organiseMyVideo/config.json`.
- Fall back to `/mnt/video2/toFile` when no configured source exists.
- Accept `media scan --source PATH` as an explicit override for that invocation.
- Reuse the established rescan implementation rather than duplicate scan logic.\n- Present the user-facing mode and activity as `scan`, not the legacy internal `rescan` name.\n- Show single-line terminal progress while movie folders and TV shows are scanned.
- Keep the normal TV scan lightweight: inspect show-level identity metadata and only
  descend into shows whose top-level metadata needs repair.
- Accept `--show NAME` to repair matching TV show folders across all configured TV roots
  without scanning unrelated shows.
- Accept `--all` to request the exhaustive integrity pass, including every TV episode
  and a full media-catalogue refresh.
- Retain legacy `--rescan` and `library rescan --target ...` forms for
  compatibility.

## Acceptance criteria

1. `organiseMyVideo media scan` selects rescan mode and scans both movie and TV
   libraries.
2. The canonical command has no movie/video target selector.
3. With no `--source`, the command uses the configured `source` value.
4. `--source PATH` overrides the configured value and is validated before the
   organiser is constructed.
5. If no source is configured, the historical `/mnt/video2/toFile` default is
   retained.
6. Existing compatibility scan forms continue to work.
7. CLI help and user documentation describe the combined command and source
   resolution.
8. A normal canonical scan performs lightweight TV show-level checks rather than
   reading every episode metadata file.
9. `media scan --show NAME` limits repair to matching TV show folders across all TV roots.
10. `media scan --all` performs the exhaustive movie/TV integrity pass and full
    catalogue refresh.

## Traceability

- Implementation: `organiseMyVideo/__main__.py`
- Tests: `tests/test_cli.py`
- Documentation: `README.md`, `documentation/commandLineInterface.md`
- Branch: `feature/media-scan-command`

## Change history

- 2026-09-20: created and implemented — canonical combined media scan with
  configured-source resolution and explicit `--source` override.
- 2026-09-22: added lightweight show-level TV repair, targeted `--show` scans,
  exhaustive `--all` scans, and corrupt `series.xml` regeneration.
