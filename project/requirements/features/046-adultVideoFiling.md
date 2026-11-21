# 046: Adult video filing

## Status

Completed

## Outcome

As the owner of an adult video collection, I need
`media organise --adult` to rename downloaded scenes to one convention and
move them from the download folder into the collection's staging folder, so
that new scenes are filed consistently without hand renaming and without risk
to the downloads.

## Context

Scenes are downloaded to `/mnt/video/toMove` and filed by hand into
`/mnt/myVideo/decrypted/Pron/toMove`, which is on a different, encrypted
filesystem. On 2026-11-21 the download folder held three name forms:

- scene releases, usually a folder such as
  `PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]/` holding a lower-case
  video and a tracker `.nfo` file;
- `Brazzers - Cory Chase, Sophia Locke - The Baddest Milf On The Block - Part 1 (08.05.2026) rq.mp4`,
  with the date as day, month, year; and
- `[TabooHeat] Cory Chase Halloween Bush or Bald (26.10.31)[720p][xFans].mp4`,
  with the date as year, month, day.

Some names, such as `SoLo-Hrhsbntobdmt1080.mp4`, carry no studio or date.

Scene release names do not mark where the performers end and the title begins,
for example `PureTaboo.26.05.26.Sophia.Locke.Her.Loss.His.Gain`. The user asked
on 2026-11-21 for performer and title to be separated where possible.

## Scope

### Command

- Add `organiseMyVideo media organise --adult [SOURCE]`, also accepting
  `-s SOURCE`.
- Default SOURCE to `storage_locations.adultSource` in
  `~/.config/organiseMyVideo/config.json`, otherwise `/mnt/video/toMove`.
- Default the destination to `storage_locations.adultDestination`, otherwise
  `/mnt/myVideo/decrypted/Pron/toMove`, and accept `--destination PATH`.
- Keep the adult source and destination config values separate from the
  movie and TV `source`, which `--adult` never reads.
- When SOURCE or `--destination` is given and differs from its config value,
  offer to save it, as `media organise` does for `source`.
- Default to a dry run that prints the full plan. Change files only with
  `--confirm`.
- Run only the adult workflow. Reject `--adult` combined with `--merge`.
- Refuse a SOURCE and destination that are the same, or where one contains the
  other.

### Naming convention

- File: `<Studio> - <yymmdd> - <Performers> - <Title>.<ext>`, for example
  `PureTaboo - 260526 - Sophia Locke - Her Loss His Gain.mp4`.
- Omit ` - <Title>` when the name has no title, for example
  `PervMom - 261004 - Lexi Luna.mp4`.
- Separate several performers with `, `, for example
  `MomSwap - 260226 - Sophia Locke, Whitney OC.mp4`.
- Folder: one folder per studio, `<destination>/<Studio>/`.
- Keep the original extension and never re-encode.
- Make names filesystem-safe: `\`, `/`, `:` and `|` become ` - `, and `?`, `*`,
  `<`, `>` and `"` are removed.

### Parsing

- Take the studio, date, performers and title from the three name forms above.
- For a release folder holding one video, parse the folder name, because the
  file inside is often lower case or abbreviated (`i.dwc261011sl.480p.mp4`).
  Fall back to the file name when the folder name cannot be parsed.
- Drop release tags: `XXX`, resolution, codec, release group, `[XC]`, `rq` and
  bracketed site tags.
- Where the name separates performers explicitly, as the hyphen form does, use
  that.
- Otherwise take performers from the start of the remaining words: a known
  performer name, or else the first two words, followed by further names
  joined by `And` or matching a known performer. The words left are the title.
- Known performers are those in `adultPerformers` in config and those named
  explicitly by other files in the same run.
- A name without a recognisable studio and date is reported as unparsed and
  left in place.

### Safe filing

- Perform moves through the filesystem safety boundary described in
  [filesystemSafety.md](../../../documentation/filesystemSafety.md). A move
  between drives copies, verifies by checksum, finalises, then removes the
  source.
- Never overwrite an existing file. Report an existing destination, or two
  sources planned to the same destination, as a conflict and leave the source.
- After a release folder's only video has moved, quarantine tracker files
  (`.nfo`, `.txt`, `.url`, `.sfv`) on the source filesystem and remove the
  empty folder. Leave a folder holding anything else, and report it.
- End with a summary of files moved, unparsed, conflicts and failures. Exit
  non-zero if any move failed.

## Out of scope

- Looking up scene metadata online.
- Tagging, artwork or catalogue entries.
- Renaming or reorganising files already in the destination.
- Checking that a download is complete or playable.
- Resolution or quality in the new name.

## Acceptance criteria

1. Given the download folder, when `media organise --adult` runs without
   `--confirm`, then it prints each planned source and destination and changes
   no files.
2. Given `PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]/pervmom.26.10.04.lexi.luna.mp4`,
   when it is filed with `--confirm`, then it becomes
   `PervMom/PervMom - 261004 - Lexi Luna.mp4` and the release folder and its
   `.nfo` are gone from the source.
3. Given `PureTaboo.26.05.26.Sophia.Locke.Her.Loss.His.Gain.XXX.480p.MP4-XXX[XC]`,
   when it is planned, then the name is
   `PureTaboo - 260526 - Sophia Locke - Her Loss His Gain.mp4`.
4. Given `PervTherapy.21.10.29.Kenzie.Reeves.And.Penny.Barber.Stepbrother.On.My.Mind`,
   when it is planned, then the performers are `Kenzie Reeves, Penny Barber` and
   the title is `Stepbrother On My Mind`.
5. Given `Brazzers - Cory Chase, Sophia Locke - The Baddest Milf On The Block - Part 1 (08.05.2026) rq.mp4`,
   when it is planned, then the name is
   `Brazzers - 260508 - Cory Chase, Sophia Locke - The Baddest Milf On The Block - Part 1.mp4`.
6. Given `[TabooHeat] Cory Chase Halloween Bush or Bald (26.10.31)[720p][xFans].mp4`,
   when it is planned, then the name is
   `TabooHeat - 261031 - Cory Chase - Halloween Bush or Bald.mp4`.
7. Given a performer known from config or from another file in the run, when a
   scene name lists that performer after another, then both are performers.
8. Given `SoLo-Hrhsbntobdmt1080.mp4`, when the workflow runs, then it is
   reported as unparsed and stays in place.
9. Given an existing file at the destination, when the workflow runs with
   `--confirm`, then neither file changes and a conflict is reported.
10. Given a release folder holding a file other than the video and tracker
    files, when its video is moved, then the folder and that file remain.
11. Given `--adult` with `--merge`, or a destination inside SOURCE, when the
    command runs, then it is refused with a clear message and no files change.
12. Given a move that fails, when the run ends, then the source remains, the
    failure is reported and the command exits non-zero.

## Dependencies and decisions

- [ADR-003](../../adr/003-filesystemSafetyBoundary.md) and
  [REQ-007](007-filesystemSafety.md): the move and recovery boundary.
- [REQ-041](041-rugbyVideoFiling.md): the same `media organise --<kind>` shape.
- [REQ-042](042-storagePathsAndCamelCaseNames.md): the new config keys are
  camelCase.
- Naming convention chosen by the user on 2026-11-21. Studio folders, skipping
  unparsed names and quarantining tracker files are defaults the user has not
  yet confirmed.

## Verification

- Unit tests for each name form, the performer split, date order and safe
  names.
- Workflow tests in temporary trees for dry-run, confirmed moves, tracker
  cleanup, conflicts, unparsed names and failures.
- CLI tests for the option, defaults, refusal cases and exit status.
- A dry-run plan from the real download folder reviewed by the user.

## Change history

- 2026-11-21: completed — confirmed run filed 34 scenes from the real download
  folder with no errors or conflicts.
- 2026-11-21: separate `adultSource` and `adultDestination` config values,
  at the user's request.
- 2026-11-21: created — user request to file `/mnt/video/toMove` into
  `/mnt/myVideo/decrypted/Pron/toMove`.
