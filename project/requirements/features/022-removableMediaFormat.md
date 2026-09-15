# REQ-022 — Removable media format and recycle

## Outcome

Provide an explicit, guarded workflow for wiping a numbered removable medium only
after its latest inventoried contents are known to be safely archived, then recreate
its durable identity and persist a fresh empty inventory snapshot.

The operator commands are:

```bash
organiseMyVideo camera inventory --format card18
organiseMyVideo camera inventory --format card18 -y
```

The first form is dry-run. The confirmed form is destructive.

## Canonical read/report commands

The removable-media CLI should have one normal report form for all cards and one for
a specific card:

```bash
organiseMyVideo camera inventory --list
organiseMyVideo camera inventory --card 18
organiseMyVideo camera import --list
organiseMyVideo camera import --card 18
```

`camera inventory --card ID` shows the full useful card record rather than duplicating
it behind `--list --full`. `camera import --card ID`, when no source is supplied, shows
the full per-file manifest history for that card. With `-s/--source`, `--card ID`
remains an identity assertion for a new import.

`--brand`, `--location`, `--set-location`, `--reassign`, `--format`, and similar flags
remain metadata/action overrides rather than report-format switches.

## One-card report

The card report must include current lifecycle state, location, snapshot count, latest
successful archive date, previous successful archive dates, and the latest inventory
metadata. It must omit transient mount details such as source path and current volume
name from the normal human-facing report.

Displayed timestamps use `yyyy/mm/dd hh:mm`; date-only capture ranges use
`yyyy/mm/dd`.

The inventory portion includes card ID, brand, physical type, capacity/free/content
sizes, capture-date range, detected camera, media counts, content analysis and
content-derived keywords when available.

Archive dates are historical successful import dates for the physical card. They are
not the same as the latest-snapshot archived flag used to decide whether current
content is safe to wipe.

## Format behaviour

- Parse `card18`, `card018`, or `18` as durable card ID 18.
- Resolve the currently mounted medium by its `organiseMyVideo.018` identity file.
- Refuse if no inventory snapshot exists.
- Refuse if the card has an active location, including `missing`.
- If the latest inventory contains content, refuse unless that exact latest snapshot
  has a successful import manifest proving all recorded assets were copied or already
  present.
- Refuse ambiguous duplicate mounted identities.
- Refuse non-removable block devices.
- Preserve the existing supported filesystem family (`exfat` or `vfat`) when
  formatting.
- Set the filesystem volume label to `Card18` for card 18.
- Recreate the durable `organiseMyVideo.018` identity through the normal inventory
  persistence path.
- Persist a new inventory snapshot immediately after formatting.
- The new empty snapshot is not itself archived; therefore the current card state is
  `empty` after the confirmed format.
- Historical inventory snapshots and import manifests remain unchanged. The one-card
  report continues to show `Last archived` and `Previous archives` for prior content.

## Lifecycle semantics

Archive evidence about the **latest inventory snapshot** is distinct from the card's
historical archive dates.

```text
in use
  -> to archive       latest content not yet archived
  -> available        latest content archived; safe to wipe/reuse
  -> empty            format completed and fresh empty snapshot persisted
  -> in use
```

After an available/empty card is reused, the catalogue cannot know that new content
exists until inventory runs again. A new non-empty inventory snapshot therefore has
no matching current archive evidence and, without a location, status becomes
`to archive`. Previous archive dates remain history only.

## Safety

Formatting is outside the historical read-only scope of REQ-009 and is introduced
only by this requirement. It must remain opt-in and dry-run by default. No formatting
must occur merely from inventory, list, import, or discovery commands.

## Acceptance criteria

1. Given card 18 whose latest non-empty snapshot is completely archived and has no
   active location, dry-run `camera inventory --format card18` resolves the mounted
   removable device and reports `Card18` as the new volume label without mutation.
2. Given the same card and `-y`, the filesystem is reformatted, remounted, labelled
   `Card18`, the durable card identity is recreated, and a fresh empty inventory
   snapshot is persisted.
3. After criterion 2, `camera inventory --card 18` reports `Status: empty`, retains
   the historical last archive date, and shows the newly recorded inventory time.
4. Given latest content without successful archive evidence, confirmed or dry-run
   format is refused before any destructive command.
5. Given a card with a current location, formatting is refused.
6. Given a mounted target that resolves to a non-removable device or an unsupported
   filesystem, formatting is refused.
7. Re-inventorying a card with new non-empty content creates a new latest snapshot,
   which means old archive evidence does not carry forward to that new content.
8. `camera inventory --list` lists all cards; `camera inventory --card ID` shows one
   detailed card report without requiring `--list` or `--full`.
9. `camera import --list` lists all import summaries; `camera import --card ID` shows
   the full per-file manifest history for that card without requiring `--full`.
