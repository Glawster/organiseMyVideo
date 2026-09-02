# 002: Qt media-library browser

## Status

ToDo

## Outcome

As a media-library owner, I need a Qt desktop interface that presents my movie,
television, audio, audiobook, and ebook files as browsable collections so that
I can inspect all supported media and its available metadata without navigating
the storage hierarchy manually.

## Context

The existing application is command-line driven. The requested interface takes
functional inspiration from Media Center Master for Windows: persistent media
collection navigation, artwork-led browsing, quick filtering and sorting, and
a detailed view of the selected title. This is a design reference rather than
a requirement to copy proprietary visuals or reproduce every Media Center
Master feature.

Media Center Master's official site describes a collection-management
interface with metadata search/editing, posters and other artwork, cached
collections, filtering, and sorting. Its official gallery is the visual
reference to review during design:

- [Media Center Master overview](https://www.mediacentermaster.com/)
- [Media Center Master screen-capture gallery](https://www.mediacentermaster.com/gallery/)
- [Media Center Master feature comparison](https://licensing.mediacentermaster.com/Compare_Versions.aspx)

The user identified `organiseAIMediaStudio` as a possible source of audio,
audiobook, and ebook processing. Inspection of its checked-out `main` branch on
2026-08-04 found a minimal FastAPI root endpoint and React/Material UI starter,
but no media-processing implementation or domain model. Relevant work may
exist elsewhere, but reuse is unconfirmed and must be investigated before a
cross-repository dependency is introduced.

For this requirement, **audio** is a provisional collection name that includes
music. Whether music and other audio need separate navigation is an open product
decision below.

## Scope

- A Qt desktop application surface integrated with this repository's existing
  packaged application rather than a separate web frontend.
- Top-level collection navigation for Movies, TV, Audio, Audiobooks, and Ebooks.
- Artwork-led grid browsing with a useful list/table alternative where artwork
  is unavailable or dense file information is preferred.
- A selected-item details area showing available identity, file, storage,
  artwork, and media-specific metadata without fabricating missing values.
- Search, filtering, and sorting within the active collection.
- Refresh/loading progress, completion status, empty states, unavailable-path
  states, and recoverable metadata-error states.
- Keyboard-accessible navigation and operation at common desktop display scales.
- A framework-independent library/query model so the Qt layer orchestrates and
  renders rather than implementing scanning or metadata business rules.
- Headless automated tests for the presentation model and appropriate Qt tests
  for navigation, selection, filtering, state handling, and responsiveness.
- An explicit integration assessment for any reusable processing or domain
  model found later in `organiseAIMediaStudio`.

## Out of scope

- A pixel-for-pixel copy of Media Center Master, reuse of its proprietary
  assets, or replication of unrelated download/torrent features.
- Editing metadata, renaming, moving, deleting, or otherwise processing media
  through the UI; these require separately agreed commands and safety criteria.
- Built-in media, audiobook, or ebook playback/readers.
- AI creation/editing features or adopting the existing React frontend from
  `organiseAIMediaStudio`.
- Merging repositories or taking a runtime dependency on another checkout.
- Replacing the supported CLI workflows.

## Acceptance criteria

1. Given configured libraries containing supported media, when the Qt
   application opens, then Movies, TV, Audio, Audiobooks, and Ebooks are
   available as distinct top-level collections and selecting one displays only
   items classified in that collection.
2. Given an item with partial or complete metadata, when it is displayed in the
   active collection, then the browser shows its title or filename, media type,
   location, available artwork or a consistent placeholder, and the most useful
   type-specific summary fields without inventing absent data.
3. Given a displayed item, when the user selects it, then a details area shows
   the available file and media-specific metadata and clearly distinguishes
   missing, invalid, and successfully loaded values.
4. Given a populated collection, when the user searches, filters, or changes
   sort order, then visible results update consistently; clearing those controls
   restores the full active collection without rescanning storage.
5. Given library loading or refresh work, when it is in progress, then the UI
   remains responsive, reports progress or indeterminate activity and status,
   and presents either the refreshed results or an actionable failure state.
6. Given an empty collection, unavailable configured path, unreadable file, or
   malformed metadata record, when that state is encountered, then the UI
   remains usable, identifies the affected collection/item, and continues to
   show unaffected media.
7. Given normal browsing, searching, sorting, filtering, selection, and refresh
   actions, when they complete, then no media file, companion file, metadata
   cache, or configured library path is renamed, moved, deleted, or rewritten.
8. Given keyboard-only operation, when focus moves through collection
   navigation, browser controls, results, and details, then every browsing
   action is reachable, focus is visible, and selection is communicated without
   relying on colour alone.
9. Given the UI implementation, when architecture and tests are reviewed, then
   scanning/classification/query behaviour is independent of Qt, Qt widgets
   contain no filesystem mutation logic, and core behaviour is testable without
   constructing the GUI.
10. Given Media Center Master as the design reference, when the implemented UI
    is reviewed, then it provides the requested collection navigation,
    artwork-led results, filtering/sorting, selected-item details, and status
    feedback while using original project styling and assets.
11. Given a proposed dependency or code transfer from `organiseAIMediaStudio`,
    when integration is considered, then the source branch/commit, available
    behaviour, ownership boundary, data contract, dependencies, and test
    evidence are documented; unverified code is not treated as delivered
    processing capability.

## Open questions

- Should Audio be one collection, or should Music and other audio be separate?
- Which metadata fields and artwork types are essential for each media type?
- Which storage roots/configuration keys identify audiobook and ebook libraries?
- Is the first release browsing-only as scoped, or are selected safe processing
  actions required in a separately linked requirement?
- Should the application use PySide6 or another Qt binding? ADR-004 proposes
  PySide6 but remains unaccepted pending dependency and licensing review.
- Does relevant `organiseAIMediaStudio` work exist on another branch or remote
  that was not present in the inspected local checkout?

## Dependencies and decisions

- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-004: Qt application architecture](../../adr/004-qtApplicationArchitecture.md)
- Phase 2 packaging work must provide a reproducible optional Qt dependency and
  executable entry point before implementation is considered ready.
- Phase 3 entry-point work must preserve CLI operation while adding a GUI entry
  point or explicit GUI command.
- `organiseAIMediaStudio` integration assessment: pending confirmation of the
  relevant branch, commit, and actual processing implementation.

## Verification

- Headless unit tests for collection classification, query state, filtering,
  sorting, selection, placeholders, and partial/error data.
- Qt tests for collection navigation, keyboard access, focus, selected-item
  details, loading/error states, and background refresh responsiveness.
- Filesystem snapshots proving acceptance criterion 7 for every browsing action.
- Manual visual review against the functional design reference using original
  styling and assets.
- Documented cross-repository assessment before any reuse.

## Traceability

- Implementation: pending
- Tests: pending
- Documentation: this requirement; living UI guide pending implementation
- Pull request: pending
- Agent runs: 2026-08-04 — Codex, capture and initial refinement, current
  branch `chore/adopt-process-standards`

## Change history

- 2026-08-04: created — requested a Qt media browser inspired by Media Center
  Master and recorded the unconfirmed `organiseAIMediaStudio` dependency.
