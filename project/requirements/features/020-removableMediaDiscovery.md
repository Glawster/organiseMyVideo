# 020: Removable media discovery and lifecycle

## Status

ToDo

## Outcome

As a media-library operator, I need to search, assess, locate, and select numbered SD
cards and USB volumes from the catalogue so that I can find stored content,
identify what device a card belongs to, choose an appropriate card before going out,
and know when a card is safe to recycle.

## Context

The camera-card inventory already records numbered removable media, including
size, free space, capture dates, camera/device metadata, file counts, and a
content summary. REQ-009 is extended to persist the complete relative filename
inventory for every confirmed snapshot. USB-volume inventory is planned to use
the same numbered volume model. Camera import will add verified archive outcomes.

The catalogue should use those records as operational knowledge rather than
only as historical snapshots. Typical questions include:

- Which card should I take with me?
- Which empty card has gone unused for the longest time?
- Which card has enough free space for the planned recording?
- Where is card 4 and what device is it associated with?
- Is card 4 currently loaded in the GoPro, drone, dash cam, stored loose, or MIA?
- Which cards are currently marked missing?
- Which card is currently loaded in a particular camera?
- Is card 4 a GoPro card, drone card, dash-cam card, or general USB volume?
- Which camera make/model was most recently associated with a numbered card?
- Where is footage from a particular date or event?
- Which numbered volume contains a named file, software package, document, or
  other non-media content?
- What exact files were on card 4 at its latest inventory?
- Which cards still contain unique or unimported content?
- Which cards are safe to reuse or format?

## Scope

- Search known removable-volume inventory by card/volume ID, date or date
  range, filename, content-summary text, keywords, camera/device metadata, and
  file type.
- Search non-media inventory as well as camera media so numbered USB volumes
  can locate software installers/packages, documents, archives, and other
  stored files.
- List known removable volumes with current capacity, free space, most recent
  inventory date, content date range, volume kind, device/camera association,
  physical placement, and derived lifecycle status.
- Show a detailed view of one numbered removable volume with
  `camera show --card ID`.
- Show the complete removable-volume inventory with `camera show --all`.
- Treat `--card` and `--all` as mutually exclusive selectors for `camera show`.
- Support `camera show --card ID --full` to display the complete stored relative
  filename/path inventory from the card's latest snapshot without rescanning
  the physical card.
- Keep persisted filename inventory complete, while allowing presentation rules
  to suppress low-value entries by default.
- Hide known operating-system/system clutter by default in `--full` output.
- Support an explicit override such as `--show-system` to include entries hidden
  by the default system-file visibility rule.
- Treat display filtering as presentation only; it must never delete or omit
  entries from persisted historical snapshot data.
- Keep `camera show --all` as a concise cross-card summary rather than expanding
  every card's complete file inventory by default.
- Maintain a registry of known cameras/devices, including at least a stable
  local device ID/name, device class, manufacturer/model, serial number when
  known, and active/inactive state.
- Support adding a known camera/device to that registry and retiring/removing it
  from active use without deleting historical card-placement or inventory
  evidence.
- Support explicitly loading a numbered card into a registered camera/device.
- Support explicitly unloading/removing a card from a registered camera/device.
- Support marking a numbered card `MIA` when its physical location is unknown
  and the operator cannot currently account for it.
- Support clearing `MIA` when the card is found, preserving when it was marked
  missing and when it was recovered.
- Record card-placement and location-state transitions with timestamps so
  current placement and historical device/location use can both be queried.
- Enforce one current placement for a card. Loading a card into a new device
  closes its previous placement or MIA state rather than leaving two current
  locations.
- Where a device can have more than one card slot, support an optional slot
  identifier so current placement is unambiguous.
- For a numbered card, report the best-known device association from both
  explicit placement history and inventory evidence, distinguishing at least
  GoPro/camera, DJI/drone, dash cam, and general USB/removable storage.
- Explicit placement is stronger evidence for current physical location than
  inferred content type; historical inventory still contributes device-use
  history.
- Include recorded manufacturer/model/serial information when available, and
  report the latest known source/mount identity or other location evidence that
  helps the operator identify the physical volume.
- Preserve uncertainty: when a card has been used by multiple device classes or
  the latest evidence is insufficient, report that history/ambiguity rather
  than inventing a single association.
- Recommend cards for use according to free space, lifecycle state, and physical
  availability. Cards marked `MIA` are never recommendation candidates.
- Prefer the oldest suitable empty/recyclable card when several equivalent
  cards are available, so physical cards are rotated rather than repeatedly
  using the same one.
- Support a requested minimum free-space threshold.
- When sufficient recording-rate information is available, allow selection by
  expected recording duration; otherwise report that free-space selection is
  the available evidence rather than inventing a duration estimate.
- Derive operational status from catalogue/import evidence rather than storing
  a manually maintained status where possible.
- Distinguish at least the following content lifecycle concepts: ready to use,
  contains unarchived/current content, archived/safe to recycle, needs review,
  and insufficient space.
- Track physical availability separately from content lifecycle, including at
  least loaded, unloaded/accounted-for, and MIA/missing.
- Identify content that has not been successfully imported and verified.
- Identify import conflicts, failures, unknown content, or other evidence that
  prevents a safe-to-recycle decision.
- Detect likely duplicate content recorded on more than one removable volume
  where digest/identity evidence permits it.
- Keep historical inventory snapshots; selection/search should normally use
  the latest snapshot while retaining older evidence for audit, device-use
  history, placement history, missing/recovery history, file-inventory history,
  and lifecycle calculations.
- Expose the capability through importable Python catalogue/query services
  before adding CLI or Qt presentation layers.

## Out of scope

- Automatically formatting, erasing, or ejecting cards or USB volumes.
- Physically detecting that a card has been inserted into or removed from a
  powered-off camera unless a later hardware integration supplies that evidence.
- Automatically declaring a card MIA merely because it has not been inventoried
  recently; MIA is an explicit operator assertion unless stronger hardware
  evidence is introduced later.
- Declaring a card safe to erase solely because its free space is low or its
  content is old.
- Guessing that content was archived when there is no verification evidence.
- Guessing a device association when inventory and placement evidence are
  ambiguous.
- Deleting historical device or placement records when a camera is retired.
- Defining all future filename suppression categories beyond the initial
  default system-file rule.
- Replacing the camera-import verification/manifest process.
- Requiring every removable volume to contain camera media.

## Candidate operator interface

Removable-media lifecycle and discovery remain under the `camera` command,
while movie/TV organisation remains under `media`.

```bash
organiseMyVideo camera show --card 6
organiseMyVideo camera show --card 6 --full
organiseMyVideo camera show --card 6 --full --show-system
organiseMyVideo camera show --all
organiseMyVideo camera find --date 2026-09-12
organiseMyVideo camera find --keyword hillsborough
organiseMyVideo camera recommend --free 100GB
organiseMyVideo camera status --card 12

organiseMyVideo camera add --name gopro9 --type gopro --model "HERO9 Black"
organiseMyVideo camera add --name drone --type dji
organiseMyVideo camera add --name dashcam --type dashcam
organiseMyVideo camera remove --name gopro9
organiseMyVideo camera load --card 4 --camera gopro9
organiseMyVideo camera load --card 7 --camera drone
organiseMyVideo camera unload --card 4
organiseMyVideo camera mia --card 4
organiseMyVideo camera found --card 4
```

For devices with multiple media slots, `camera load` may additionally accept a
slot identifier, for example `--slot 2`.

For `camera show`, exactly one of `--card ID` or `--all` is required. A single
card view should answer both “what is on this card?” and “where is this card
now?”. `--full` expands a single card view to the latest stored relative file
listing; known system files remain hidden unless `--show-system` is supplied.
A device view/query should likewise make it possible to answer “which card is
currently in the GoPro?”. `camera show --all` should make MIA cards visually
obvious. The service layer must not depend on these exact CLI spellings.

## Lifecycle model

Initial derived content states are:

- `READY`: empty or otherwise verified safe for immediate reuse.
- `IN_USE`: contains current content that has not yet been fully archived and
  verified.
- `ARCHIVED`: known content has been imported and verified and no unique
  remaining files prevent reuse.
- `NEEDS_REVIEW`: unknown files, failed imports, conflicts, missing verification,
  or other ambiguity prevents an automatic recycle decision.
- `FULL`: insufficient useful free space for the requested use; this may be a
  query result layered on top of the underlying content lifecycle state rather
  than a permanently stored status.

Physical location/availability is tracked separately:

- `LOADED`: explicitly recorded in a known camera/device, optionally in a named
  slot.
- `UNLOADED`: accounted for but not currently loaded in a registered device.
- `MIA`: explicitly reported missing / whereabouts unknown.

A card can therefore be `READY` + `MIA`, `ARCHIVED` + `UNLOADED`, or `IN_USE` +
`LOADED`. `MIA` does not change the content-safety judgement, but it does make
the card physically unavailable and excludes it from recommendations.

## Acceptance criteria

1. Given multiple inventoried removable volumes, when the operator asks for a
   suitable card without further constraints, then cards not safe for reuse or
   physically unavailable/MIA are excluded and the oldest suitable
   empty/recyclable card is preferred.
2. Given a minimum free-space requirement, when recommendation runs, then only
   safe, physically available cards meeting that threshold are returned,
   ordered deterministically.
3. Given no safe available card meeting the requested space, when recommendation
   runs, then the result explicitly reports that no suitable card is available
   and does not recommend a card with unverified content or MIA status.
4. Given a date or date range, when search runs, then matching removable-volume
   snapshots/content are returned with the numbered volume ID and enough
   context to locate the physical card.
5. Given text or keywords, when search runs, then filename, stored content
   summary, relevant metadata, and indexed non-media file information can
   contribute matches.
6. Given a numbered USB volume containing a software installer/package,
   document, archive, or other non-camera file, when searched by identifying
   filename/type/keyword, then the volume can be located without requiring it
   to be classified as camera media.
7. Given a card whose relevant files were imported and verified successfully,
   with no unique unknown/unverified content remaining, when lifecycle status
   is derived, then it can be reported as safe to recycle independently of
   whether its physical availability is loaded, unloaded, or MIA.
8. Given any failed import, destination conflict, unknown unique file, or
   missing verification affecting content on a card, when lifecycle status is
   derived, then the card is not reported safe to recycle and the blocking
   evidence is shown.
9. Given repeated inventory snapshots for the same numbered volume, when
   search/recommendation runs, then the latest snapshot supplies current
   capacity/content state while historical snapshots remain available for
   audit, rotation, device-association, placement, MIA/recovery, and file-list
   history.
10. Given digest or durable identity evidence showing the same content on more
    than one removable volume, when queried, then duplicate locations can be
    reported without deleting either copy.
11. Given `camera show --card ID`, when the ID exists, then the latest detailed
    record for that removable volume is shown, including volume kind, best-known
    device class, current physical placement or MIA state, camera
    manufacturer/model/serial when known, latest location evidence, free space,
    lifecycle state, and content summary.
12. Given a card whose inventory consistently identifies one device class, when
    `camera show --card ID` runs, then it reports that association (for example
    GoPro, DJI/drone, or dash cam); given conflicting historical device evidence,
    then it reports the ambiguity/history rather than silently choosing one.
13. Given `camera show --all`, then all known removable volumes are shown in a
    deterministic summary including card ID, volume/device kind, current
    placement or MIA state, capacity/free space, lifecycle status, and latest
    inventory date.
14. Given `camera show` with both `--card` and `--all`, or with neither, then
    argument validation fails before a catalogue query is executed.
15. Given `camera show --card ID --full`, when the card has a persisted filename
    inventory, then the latest snapshot's stored relative paths are displayed
    without requiring the physical card to be mounted or rescanned.
16. Given known operating-system/system clutter is present in a stored filename
    inventory, when `--full` is used, then those entries are hidden by default;
    when the explicit system-file override is supplied, those same stored
    entries are displayed.
17. Given display filtering hides an entry, then the underlying persisted
    snapshot remains unchanged and later queries can still access that entry.
18. Given a camera/device is added, then it receives a stable local identity and
    can subsequently be used as a load target.
19. Given an active camera/device is removed/retired, then it is no longer
    offered as a normal load target, but its historical card placements and
    inventory associations remain queryable.
20. Given `camera load --card ID --camera DEVICE`, when both exist and the
    placement is valid, then the card is recorded as currently loaded in that
    device with a timestamp; loading it elsewhere closes the previous current
    placement or MIA state.
21. Given a multi-slot device and a slot identifier, when a card is loaded, then
    the current placement records that slot and prevents an incompatible second
    current card assignment to the same slot.
22. Given `camera unload --card ID`, when the card is currently loaded, then the
    placement is closed with a timestamp and the card becomes `UNLOADED` while
    its placement history is retained.
23. Given `camera mia --card ID`, when the card exists, then its current physical
    state becomes `MIA` with a timestamp and its last known placement/location
    remains available as history.
24. Given `camera found --card ID`, when the card is currently `MIA`, then the
    MIA interval is closed with a recovery timestamp and the card becomes
    `UNLOADED` unless a simultaneous/new `load` operation establishes a camera
    placement.
25. Given a card marked `MIA`, when recommendation runs, then that card is never
    offered even if its content lifecycle is `READY` or `ARCHIVED` and it has
    sufficient free space.
26. Given `camera show --card ID` after load, unload, MIA, or found operations,
    then current physical state reflects the latest explicit transition and all
    prior placement/missing history remains available for audit.
27. Given the Python query/recommendation/device-placement services are called
    directly, then they return structured results without depending on argparse,
    console parsing, or the Qt UI.
28. Search, recommendation, listing, show, and status queries do not mutate
    removable media or archive content. Device-registry and physical-state
    actions may update application catalogue state but never write to the
    physical card.

## Dependencies and decisions

- [REQ-004: Camera media import](004-cameraMediaImport.md)
- [REQ-009: Camera card inventory](009-cameraCardInventory.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-015: USB volume inventory](015-usbVolumeInventory.md)
- [REQ-016: Catalogue media identities](016-catalogueMediaIdentities.md)
- [ADR-008: SQLite media catalogue](../../adr/008-sqliteMediaCatalogue.md)
- [ADR-009: Numbered removable volumes](../../adr/009-numberedRemovableVolumes.md)

## Verification

- Unit tests with multiple synthetic card/USB snapshots covering empty,
  archived, unimported, conflicted, nearly full, and unknown-content states.
- Search tests for date ranges, keywords, filenames, camera metadata, and
  non-media file types.
- Full-file display tests proving latest stored snapshot paths are used without
  rescanning and that default system-file hiding can be explicitly overridden.
- Device-association tests covering GoPro, DJI/drone, dash cam, USB, unknown,
  and historically mixed-device cards.
- Device-registry tests covering add, retire/remove, stable identity, and
  retention of historical associations.
- Placement tests covering load, unload, reassignment, current placement,
  historical placement, optional multi-slot devices, MIA, and recovery.
- Recommendation tests proving minimum-space filtering, oldest-suitable-card
  rotation, and exclusion of MIA cards.
- `camera show` tests covering `--card ID`, `--card ID --full`, `--all`, device
  association, current placement/MIA state, latest location evidence,
  system-file visibility override, and mutual-exclusion/error handling.
- Safety tests proving ambiguous/unverified cards are never labelled safe to
  recycle and MIA cards are never recommended for immediate use.
- Direct service tests independent of CLI and Qt layers.
- `pytest`
- `git diff --check`

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: pending
- Pull request: pending
- Agent runs: None

## Change history

- 2026-09-12: created from operator use cases for choosing cards, locating
  content across numbered removable media, finding non-media files on USB
  volumes, and deriving safe-to-recycle lifecycle state from inventory and
  verified import evidence.
- 2026-09-12: refined CLI direction so removable-media discovery remains under
  `camera`; added `camera show --card ID` and `camera show --all`, with mutually
  exclusive selectors.
- 2026-09-12: added numbered-card device/location lookup so `camera show --card`
  reports whether a card is associated with GoPro, DJI/drone, dash cam, USB, or
  ambiguous historical use, together with available camera/device identity.
- 2026-09-12: added a persistent camera/device registry plus explicit card
  load/unload placement history so the catalogue can answer where a card is
  physically located and which card is currently in each camera.
- 2026-09-12: added explicit `MIA`/missing and recovery transitions, kept
  physical availability separate from content lifecycle, and excluded missing
  cards from recommendation results.
- 2026-09-12: added `camera show --card ID --full` using stored per-snapshot
  filename inventory; known system files are hidden by default with an explicit
  override, while persisted raw inventory remains complete.
