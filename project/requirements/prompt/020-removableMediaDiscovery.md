Role: refine, implement, and verify

Read REQ-020 together with REQ-004, REQ-009, REQ-010, REQ-015, REQ-016,
ADR-008, and ADR-009.

Implement removable-media discovery as importable Python catalogue/query
services first. Support listing/show, search, lifecycle derivation, device
association lookup, device registry, physical card placement, MIA/recovery, and
card recommendation without depending on argparse or Qt.

Key behaviours:

- Search numbered SD cards and USB volumes by ID, date/range, filename,
  keywords/content summary, camera/device metadata, and file type.
- Include non-media files such as installers/packages, documents, and archives
  in searchable USB-volume inventory.
- Derive safe operational lifecycle state from latest inventory plus verified
  import evidence; never infer safe-to-recycle from age or free space alone.
- Keep content lifecycle separate from physical availability/location.
- Physical states must distinguish at least `LOADED`, `UNLOADED`, and `MIA`.
- `MIA` is an explicit operator assertion that the card cannot currently be
  accounted for; do not infer it merely from age or lack of recent inventory.
- Exclude MIA cards from recommendations even when their content state is safe
  and free space is sufficient.
- Recommend cards by lifecycle safety, physical availability, and requested
  free-space threshold; prefer the oldest suitable empty/recyclable card to
  rotate physical media.
- Preserve historical inventory snapshots for audit, rotation calculations,
  device-association history, physical placement history, and missing/recovery
  history.
- Report duplicate locations when durable identity/digest evidence permits it.
- Keep search/list/show/recommend/status operations non-mutating.
- Keep removable-media lifecycle/discovery under the `camera` command; movie/TV
  organisation remains under `media`.
- Provide `camera show --card ID` for one removable-volume detail view and
  `camera show --all` for the complete known inventory. Require exactly one of
  `--card` or `--all` and fail validation before querying when both or neither
  are supplied.
- Make `camera show --card ID` answer “what is on this card?”, “what device is
  this card associated with?”, and “where is this card currently located?”.
- Make `camera show --all` include card ID, device/volume kind, physical state,
  current placement when known, capacity/free space, lifecycle status, and
  latest inventory date; MIA cards should be visually obvious.
- Maintain a registry of known cameras/devices with stable local identity,
  type/class, make/model, serial when known, and active/retired state.
- Support device add and remove/retire operations. Retiring a device must not
  delete historical inventory or placement evidence.
- Support explicit card placement with `camera load --card ID --camera DEVICE`
  and removal with `camera unload --card ID`.
- Support `camera mia --card ID` to mark a known card missing and
  `camera found --card ID` to close the missing interval when it is recovered.
- Record placement and MIA/found transitions with timestamps and retain history.
- A card can have only one current physical state/placement. Loading it into a
  device closes a previous placement or MIA interval.
- `camera found --card ID` returns a missing card to `UNLOADED` unless a new
  load establishes a device placement.
- Support optional slot identity for devices with multiple removable-media
  slots and prevent incompatible double assignment to the same slot.
- Treat explicit placement as stronger evidence for current physical location
  than inferred content type, while retaining historical content-derived device
  associations.
- Include camera manufacturer/model/serial and latest source/mount/location
  evidence when available.
- If a card has historical use across multiple device classes or evidence is
  insufficient, preserve and show that ambiguity/history instead of inventing
  a single association.

Candidate CLI examples:

```bash
organiseMyVideo camera add --name gopro9 --type gopro --model "HERO9 Black"
organiseMyVideo camera add --name drone --type dji
organiseMyVideo camera add --name dashcam --type dashcam
organiseMyVideo camera remove --name gopro9
organiseMyVideo camera load --card 4 --camera gopro9
organiseMyVideo camera load --card 7 --camera drone
organiseMyVideo camera unload --card 4
organiseMyVideo camera mia --card 4
organiseMyVideo camera found --card 4
organiseMyVideo camera show --card 4
organiseMyVideo camera show --all
```

Use synthetic test fixtures for multiple card/USB histories and verify direct
service use independently of any CLI/UI adapter. Include tests for GoPro,
DJI/drone, dash cam, USB, unknown, and mixed historical associations, plus
add/remove device lifecycle, load/unload placement transitions, MIA/recovery,
and recommendation exclusion for missing cards. The CLI adapter must remain
thin and call the same structured services used by direct Python callers.
