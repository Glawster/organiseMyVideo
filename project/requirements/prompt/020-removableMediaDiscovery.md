Role: refine, implement, and verify

Read REQ-020 together with REQ-004, REQ-009, REQ-010, REQ-015, REQ-016,
ADR-008, and ADR-009.

Implement removable-media discovery as importable Python catalogue/query
services first. Support listing/show, search, lifecycle derivation, and card
recommendation without depending on argparse or Qt.

Key behaviours:

- Search numbered SD cards and USB volumes by ID, date/range, filename,
  keywords/content summary, camera/device metadata, and file type.
- Include non-media files such as installers/packages, documents, and archives
  in searchable USB-volume inventory.
- Derive safe operational lifecycle state from latest inventory plus verified
  import evidence; never infer safe-to-recycle from age or free space alone.
- Exclude ambiguous, conflicted, failed, unknown, or unverified content from
  safe recommendations.
- Recommend cards by lifecycle safety and requested free-space threshold;
  prefer the oldest suitable empty/recyclable card to rotate physical media.
- Preserve historical inventory snapshots for audit and rotation calculations.
- Report duplicate locations when durable identity/digest evidence permits it.
- Keep all search/list/show/recommend/status operations non-mutating.
- Keep removable-media lifecycle/discovery under the `camera` command; movie/TV
  organisation remains under `media`.
- Provide `camera show --card ID` for one removable-volume detail view and
  `camera show --all` for the complete known inventory. Require exactly one of
  `--card` or `--all` and fail validation before querying when both or neither
  are supplied.

Use synthetic test fixtures for multiple card/USB histories and verify direct
service use independently of any CLI/UI adapter. The CLI adapter must remain
thin and call the same structured query services used by direct Python callers.
