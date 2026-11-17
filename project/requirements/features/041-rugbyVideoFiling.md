# 041: Rugby video filing

## Status

ToDo

## Outcome

As the owner of a rugby video store, I need `media organise --rugby` to identify
downloaded rugby matches, rename them to the agreed convention and move them
into the store, so that new matches are filed consistently with no guessed dates
and no risk to the original files.

## Context

Rugby videos arrive in a download folder with inconsistent names, such as
`14 FULL MATCH Exeter Chiefs v Gloucester Hartpury 01 11 25 - You.mp4`,
`835 Gloucester-Hartpury vs Bristol Bears Full Match Premiership _1.mp4` and
`RU.2025.Autumn.Nations.Series.W01.England.v.Australia.1080p.H.264-bill.mkv`.
These were filed by hand on 2026-11-02, and that exercise defines this behaviour.

Names alone are not enough:

- Some names have no date, and a season can contain the same pairing more than
  once. The `835` Bristol file could have been Round 8, Round 12 or the
  semi-final; its on-screen score of 36-20 identified the semi-final.
- A file's modified time is the download time. It can narrow the candidates but
  never establishes a played date.
- A download can be incomplete. One 2.9 GB file had no `moov` atom and could not
  be played.
- Download folders also hold videos that are not rugby.

The store is a personal collection rather than the TV library, as described in
[homeVideo.md](../../../documentation/homeVideo.md). It is currently at
`/mnt/raid/Rugby`, having moved from `/mnt/media/homeVideo/Rugby`, so the store
path must come from configuration.

## Scope

### Command

- Add `organiseMyVideo media organise --rugby [SOURCE]`, also accepting
  `-s SOURCE`. SOURCE is the folder to file from.
- Default to a dry run that prints the full plan. Change files only with
  `--confirm`.
- Read the default source and store from
  `~/.config/organiseMyVideo/config.json`, and accept an explicit store override.
- Run only the rugby workflow. `--rugby` does not perform movie or TV organising
  and is rejected in combination with `--merge`.

### Source folder

- When SOURCE is a download folder outside the store, read it and its
  subfolders.
- When SOURCE is the store itself, read only the loose files at its top level.
  Never read the competition, team or season folders, because files there are
  already filed.
- Refuse a SOURCE inside the store, such as `<store>/Six Nations`, with a clear
  message, and change no files.
- Refuse a SOURCE that contains the store, for the same reason.

### Naming convention

- Folder: `<store>/<competition or team>/<season start year>/`. The year is the
  season's start year, so `2024` holds 2024/25.
- File: `<YYYY-MM-DD> <Home> v <Away> - <Competition> <Round>.<ext>`, for example
  `2025-03-02 Gloucester-Hartpury v Bristol Bears - PWR SF.mp4`.
- Always use ` v `. Round is `R<n>`, `QF`, `SF` or `Final`. Home and away follow
  the results source, not the order in the downloaded name.
- Matches outside a numbered series omit the round, for example
  `2025-11-01 Ireland v New Zealand - Autumn International.mkv`.
- Lions tours name only the opponent, for example
  `British Lions/2013/2013-06-22 Australia - Lions Tour Test 1.mp4`.
- Halves of one match end with a space and `Part 1` or `Part 2`. Highlights end
  with a space and `Highlights`.
- Keep the original extension and never re-encode.
- Use configured folder and team-name mappings, because the two can differ: the
  folder is `Gloucester Hartpury` and the team name in a file is
  `Gloucester-Hartpury`.

### Identification and evidence

- Classify each video as rugby, not rugby or undetermined. Only rugby videos are
  planned for filing; the others are reported and left in place.
- Parse teams, date, competition and round from the common name forms above.
- Establish every played date, home and away order, and round from a dated
  fixture or results source, and show that evidence in the plan.
- When a name fits several fixtures, resolve it only from evidence such as a date
  in the name or a confirmed on-screen score. Otherwise, mark the file as needing
  review and leave it in place.
- Provide a way to review a held file, by extracting scoreboard frames or playing
  it, and to supply the fixture explicitly.

### Safe filing

- Check that each video can be opened and has a usable duration before planning
  to move it. Report unplayable files as damaged and leave them in place.
- Perform moves through the filesystem safety boundary described in
  [filesystemSafety.md](../../../documentation/filesystemSafety.md), including
  moves between drives: copy, verify by checksum, finalise, then remove the source.
- Never overwrite an existing file.
- Report a byte-identical copy in the store as a duplicate, without copying it.
- Report a different file for the same match as a conflict for review.
- Record each move in a journal that holds the source, destination and checksum,
  so that it can be reversed.
- End with a summary of files moved, held for review, damaged, not rugby,
  duplicates, conflicts and failures. Exit non-zero if any move failed.

## Out of scope

- Writing metadata tags, which remains with `rugbyAudit.py`.
- Renaming or reorganising files already in the store.
- Replacing a stored copy with a better-quality one.
- Repairing damaged downloads.
- Reading scoreboards automatically from video frames.
- Adding rugby matches to the media catalogue, which belongs with
  [REQ-014](014-homeVideoCatalogue.md).
- Filing other sports.

## Acceptance criteria

1. Given a download folder of rugby videos, when `media organise --rugby` runs
   without `--confirm`, then it prints each planned source, destination and
   evidence, and changes no files.
2. Given `14 FULL MATCH Exeter Chiefs v Gloucester Hartpury 01 11 25 - You.mp4`,
   when it is filed with `--confirm`, then it becomes
   `Gloucester Hartpury/2025/2025-11-01 Exeter Chiefs v Gloucester-Hartpury - PWR R2.mp4`.
3. Given a downloaded name that lists the teams in the opposite order to the
   results source, when it is planned, then the new name follows the results
   source.
4. Given `RU.2025.Autumn.Nations.Series.W03.England.v.New.Zealand.1080p.H.264-bill.mkv`,
   when it is filed, then it becomes
   `Autumn Internationals/2025/2025-11-15 England v New Zealand - Autumn International R3.mkv`.
5. Given a match played in January to June, when it is filed, then its folder uses
   the season's start year, not the year it was played.
6. Given a name with no date that fits several fixtures and no other evidence,
   when it is planned, then it is reported as needing review, no date is assigned
   and the file stays in place.
7. Given a held file and a fixture confirmed by the user, when the workflow runs
   again with that fixture, then the file is named from that fixture.
8. Given a file with no `moov` atom, when it is planned, then it is reported as
   damaged and stays in place.
9. Given a video that is not rugby, when the workflow runs, then it is reported as
   not rugby and stays in place.
10. Given an existing file at the destination, when the workflow runs with
    `--confirm`, then neither file changes and a duplicate or conflict is reported.
11. Given a move between drives, when the copy or checksum fails, then the source
    remains, no temporary file remains, the failure is reported and the command
    exits non-zero.
12. Given a completed move, when the journal is read, then it holds the source,
    destination and checksum, and the source no longer exists.
13. Given `--rugby` with `--merge`, when the command is parsed, then it is rejected
    with a clear message and no files change.
14. Given a Lions tour match, a two-part match or a highlights file, when it is
    planned, then its name follows the matching rule in the naming convention.
15. Given SOURCE is the store, when the workflow runs, then only loose files at
    the store's top level are planned, and no file in a subfolder is reported or
    changed.
16. Given SOURCE is inside the store or contains it, when the command runs, then
    it is refused with a clear message and no files change.
17. Given a download folder with videos in subfolders, when the workflow runs,
    then the videos in the subfolders are planned.

## Dependencies and decisions

- [ADR-003](../../adr/003-filesystemSafetyBoundary.md) and
  [REQ-007](007-filesystemSafety.md): the move and recovery boundary.
- [REQ-029](029-nonDestructiveMediaScan.md): renames and moves belong to
  `media organise`.
- [REQ-014](014-homeVideoCatalogue.md): catalogue treatment of rugby recordings.
- Results sources for women's club games:
  [thepwr.com](https://www.thepwr.com/fixtures-results) and
  [RugbyPass](https://www.rugbypass.com/premiership-womens-rugby/fixtures-results/),
  chosen by the user on 2026-11-02.
- Results source for Gloucester and Gloucester-Hartpury games:
  [gloucesterrugby.co.uk](https://www.gloucesterrugby.co.uk), chosen by the user
  on 2026-11-02.
- Results source for other men's and international games:
  [RugbyPass](https://www.rugbypass.com/), chosen by the user on 2026-11-02 subject
  to it working. Its Premiership and internationals pages returned dated results
  when tested, but its Autumn and Six Nations pages did not, and the
  internationals page did not show matches from before 2026.
- Pending decision: how earlier seasons are looked up, and how results are read and
  cached. This needs an ADR before delivery starts. Matches that no source can
  confirm are held for review.
- Pending decision: a results source for the Nations Championship, which began in
  2026. A search on 2026-11-16 found the format and the finals weekend, but not
  the dates of the November rounds. Until a source is chosen, its matches are held
  for review.
- Pending decision: the store folder and competition label for the Nations
  Championship. It replaces the Autumn Nations Series in November and also has
  July rounds, so it could have its own `Nations Championship` folder or its
  November rounds could file under `Autumn Internationals`. Its season year is the
  calendar year, because it runs within one year.
- [REQ-036](036-incomingMediaPreparation.md): `media clean` refuses library stores in
  the same way that this workflow refuses a SOURCE inside the rugby store.

## Verification

- Unit tests for name parsing, season-year calculation, round and exception
  naming, and team-name mappings, using the example names in this requirement.
- Tests for ambiguity, damaged files, duplicates, conflicts and failed moves, using
  temporary trees and a stubbed results source.
- A public CLI test that compares a dry run with a confirmed run.
- A manual check against a real download folder, following
  [testingProcess.md](../../../documentation/testingProcess.md).

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-11-02: created — from the manual filing of rugby videos from `~/dwhelper`
  into the rugby store, using the naming convention agreed on 2026-10-29.
- 2026-11-02: refined — recorded the results sources for women's club games, for
  Gloucester and Gloucester-Hartpury, and for other men's and international games.
- 2026-11-16: updated — the rugby store moved to `/mnt/raid/Rugby`.
- 2026-11-16: refined — defined which files are read from SOURCE when it is a
  download folder, the store itself, or inside the store; recorded pending
  decisions for the Nations Championship results source and store folder.
