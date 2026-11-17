# 042: Storage paths and camelCase names

## Status

ToDo

## Outcome

As the owner of a media library that has moved to a new folder layout, I need OMV
to take its storage paths from configuration and to use camelCase names, so that
imports land in the existing folders, commands work without a stale default
source, and config keys match the other organise applications.

## Context

The library now uses `/mnt/media/homeVideo` with no nested `Video` folder, and
`byDate` rather than `By Date`. Inspection on 2026-11-03 found these gaps:

- SLR imports always write beneath `By Date` (`cameraPlan.py`), so they would
  create a second tree beside `byDate`. Configuration cannot change this.
- `media organise`, `library rescan` and `torrent maintain` default to
  `/mnt/video2/toFile`, which no longer exists. The config `source` key applies
  only to `media scan` and `media clean`.
- `camera migrate --root` defaults to `/mnt/myVideo/Video/GoPro` and ignores
  configuration.
- Camera destinations need setting one by one, although each normally sits
  beneath the home video root.

OMV also reads and writes the snake_case config keys `storage_locations`,
`tvdb_api_key` and `ignored_tv_show_duplicates`, and accepts snake_case storage
aliases. organiseMyPhotos and organiseMediaStudio config files already use
camelCase. A misspelt or unrecognised storage key is ignored silently, so a
rename must not leave the owner's existing config without effect.

A scan of OMV's Python on 2026-11-03 found little other snake_case: 25 uses of
`args` attributes generated from CLI flags, such as `args.gopro_destination`, and
the locals `int_val` and `msg_lower` in `grokGallery.py`.

## Scope

### Storage paths

- Follow the suite's master and root terms, defined in
  [Media library organisation](../../../../organiseMediaStudio/documentation/mediaLibraryOrganisation.md#master-and-root).
- Read `storageLocations.photoRoot` and `storageLocations.videoRoot`. When a root is
  unset, it defaults to `<master>/byDate`.
- File SLR photos and videos as `<root>/YYYY/MM/<original filename>`. Command-line
  photo and video destinations name the root and take precedence. The offer to
  save a command-line folder to config then writes `photoRoot` or `videoRoot`.
- Capture-time correction uses `YYYY/MM` when `--root` is a configured root. Camera
  folders keep `YYYY/MM/DD`.
- Camera history recognises the configured roots, `byDate` and the older `By Date`,
  so that older import records still reconcile, including their `YYYY/MM/DD` paths.
- `media organise`, `library rescan` and `torrent maintain` use the config `source`
  key when no source is given. An explicit source takes precedence, and the
  existing fallback applies when `source` is unset.
- `camera migrate --root` defaults to the configured `gopro` location.
- When `gopro`, `drone` or `dashcam` is unset, derive it from `videoMaster`, as
  `<videoMaster>/GoPro`, `<videoMaster>/Drone` or `<videoMaster>/Dashcam`, before
  using the built-in fallback. Command-line destinations still take precedence.

### Config key rename

| Old key | New key |
| --- | --- |
| `storage_locations` | `storageLocations` |
| `tvdb_api_key` | `tvdbApiKey` |
| `ignored_tv_show_duplicates` | `ignoredTvShowDuplicates` |
| `storage_locations.photos` | `storageLocations.photoMaster` |
| `storage_locations.homeVideo` | `storageLocations.videoMaster` |
| `photo` | Retired; use `photoMaster` |
| `videoByDate` | Retired; use `videoMaster` |
| `movie_dirs` | Retired; use `movies` |
| `movie_storage_locations` | Retired; use `movies` |
| `video_dirs` | Retired; use `tv` |
| `tv_storage_locations` | Retired; use `tv` |

- Read the new key first and fall back to the old key, so existing config keeps
  working. If both exist, the new key wins.
- When OMV saves config, write only camelCase keys for values it changes, remove
  the old spelling of those keys, and preserve all other keys.
- Warn when a retired storage alias is present, naming its replacement.

### camelCase names

- Rename OMV-owned snake_case names to camelCase, including `args` attributes,
  using an explicit camelCase `dest` where argparse would generate snake_case.
- Keep each public CLI flag's spelling, such as `--gopro-destination`.
- Check other data files that OMV writes, and rename any OMV-owned snake_case
  keys with the same read fallback.

## Out of scope

- Moving or renaming media, including `byDate` and the camera archives. New
  `YYYY/MM` folders can sit beside older month folders until a confirmed plan
  changes them.
- Moving misplaced media between Photo Root and Video Root, which belongs to Photos.
- Changing the `/mnt` name patterns used for storage discovery.
- Changing the built-in fallback path values.
- Editing the owner's `config.json`, which the owner does after delivery.
- Names required by an external package, protocol or format, such as sqlite3's
  `row_factory`, Playwright's `sync_playwright`, and xAI, TMDb or TVDB fields such
  as `storage_options`, `api_key` and `imdb_id`.
- Class and constant naming, which already follow the shared guidelines.
- Rugby filing, although the REQ-041 config keys must use camelCase.

## Acceptance criteria

1. Given masters set and no roots, when an SLR card is planned, then photos and
   videos are planned as `<master>/byDate/YYYY/MM/<original filename>`.
2. Given `photoRoot` and `videoRoot` set, when an SLR card is planned, then its
   destinations use those roots.
3. Given import records under `By Date/YYYY/MM/DD` and others under `byDate/YYYY/MM`,
   when camera history runs, then archive roots are recognised for both.
4. Given a configured `source` and no source argument, when `media organise`,
   `library rescan` or `torrent maintain` runs, then it uses the configured source.
5. Given a configured `source` and an explicit source, when any of those commands
   runs, then the explicit source is used.
6. Given a configured `gopro` location and no `--root`, when `camera migrate` runs,
   then it inspects the configured location.
7. Given `videoMaster` set and no `gopro`, `drone` or `dashcam` location, when a
   camera import is planned, then its destinations are beneath `videoMaster` and
   keep `YYYY/MM/DD`.
8. Given a config with only the old keys, when any workflow reads it, then it
   behaves as it did before the rename.
9. Given both the old and new name of a key with different values, when it is read,
   then the new value is used.
10. Given a config with old keys and unknown keys, when OMV saves a TVDB key or the
    ignored duplicates, then the saved value uses its camelCase key, its old key is
    gone, and unrelated keys are preserved.
11. Given a retired storage alias, when config is read, then a warning names the
    replacement.
12. Given OMV's Python source, when it is scanned, then the only remaining
    snake_case names are those excluded above, and every public CLI flag still
    parses.
13. Given `--root` set to a configured root, when a capture-time correction is
    previewed, then proposed paths use `YYYY/MM`. Given a camera folder, they use
    `YYYY/MM/DD`.

## Dependencies and decisions

- The naming rule is defined in the organiseMyProjects agent instructions, and
  reaches this repository's deployed copy at the next guideline sync.
- The owner's suite decisions of 2026-11-04 are recorded in the guide above.
- [REQ-027](027-slrCardImport.md): SLR import destinations, whose `By Date/YYYY/MM/DD`
  layout this requirement replaces.
- organiseMyPhotos REQ-018 applies the same filing standard to Photos.
- [REQ-028](028-cameraHistoryReconciliation.md): import history reconciliation.
- [REQ-041](041-rugbyVideoFiling.md) adds rugby config keys, which follow this
  naming.

## Verification

- Unit tests for key precedence, fallback, retired aliases and config saving, using
  temporary config files.
- Tests for SLR destinations, capture-time correction paths, and history roots with
  both folder names.
- Public CLI tests for source and `--root` precedence, and for parsing every flag.
- `python -m pytest`, `runLinter` and `manageProject check`.
- A camera import dry run against a real card or folder to confirm its destinations.
  Any confirmed run on real media needs the owner's approval.

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-11-03: created — from checking OMV against the new library layout, and the
  owner's decision that names and config keys use camelCase.
- 2026-11-03: refined — the owner made `byDate` the standard, so it replaces
  `By Date` as the default folder name.
- 2026-11-04: refined — the owner's suite decisions replace `byDateFolder` with
  `photoRoot` and `videoRoot`, rename `photos` and `homeVideo` to `photoMaster` and
  `videoMaster`, and set `YYYY/MM` inside roots.
