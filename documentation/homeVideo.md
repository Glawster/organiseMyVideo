# Home video archive

## Status

Agreed catalogue plan for
[REQ-014](../project/requirements/features/014-homeVideoCatalogue.md).
Indexing is not implemented yet. Camera import into this tree remains
[REQ-004](../project/requirements/features/004-cameraMediaImport.md).

## Outcome

Personal video under `/mnt/myVideo/Video` is a catalogue collection of its
own. GoPro, Drone, and Dashcam archives are folders inside that collection,
not movie or TV titles.

## Root

```text
/mnt/myVideo/Video/
```

TV for the organiser stays at `/mnt/myVideo/TV` and `/mnt/video<n>/TV`.
Do not scan those as home video.

## First-level folders (observed)

| Folder | Role |
| --- | --- |
| `GoPro` | Camera originals, mostly `YYYY-MM-DD` directories, plus some loose AVI |
| `Drone` | Flat DJI MP4 files |
| `Home Video` | Tape transfers (`Video8`, `VideoDV`) |
| `By Date` | Family footage by year/month |
| `Extension`, `Evelyn`, `Cycling`, `Singapore` | Topic/event folders |
| `Rugby`, `Footy`, `Music` | Personal recordings, not the TV library |
| `Video` | Nested dump (GOPR AVIs and mixed files); cleanup candidate |
| `Captures`, `Favourites`, `Skeptic` | Empty or tiny leftovers |

New camera imports continue to land at:

```text
GoPro/YYYY/MM/DD/
Drone/YYYY/MM/DD/
Dashcam/YYYY/MM/DD/
```

## Rearrangement

Do not wrap the tree in a new `Camera/` or `Recorded/` parent. That would
move more than a terabyte solely to change navigation. The UI can group by
the first-level folder name.

Leave these to existing or later dry-run migrations:

- REQ-004 `camera migrate` — GoPro `YYYY-MM-DD` → `YYYY/MM/DD`, flat
  Drone files into dated folders.
- Nested `Video/Video` GOPR dumps versus the GoPro root.
- Empty `Home Video/GoPro`.
- Loose `GOPR*.avi` sitting in the GoPro root beside dated folders.

Ambiguous or conflicting items stay put until a confirmed migrate plan
names them.

## Catalogue

`library rescan` replaces `homeVideoItem` rows from this root. The UI
reads `catalogueHomeVideoList()`. Each row keeps the first-level kind so
GoPro/Drone footage can be filtered without a second library.

## Verification

Tests use temporary trees. They must not depend on the real
`/mnt/myVideo/Video` mount.
