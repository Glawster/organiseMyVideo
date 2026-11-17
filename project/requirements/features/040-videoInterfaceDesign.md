# 040: Video interface design

## Status

ToDo

## Outcome

As a Video user, I need Qt and TUI applications designed and implemented to
mirror Media Center Master's useful library-management experience as closely as
practical, while preserving organiseMyVideo's CLI and its catalogue/safety rules.
The design must also maximise practical interoperability with MCM operating
under Wine, so either application can manage the same library without forcing
an incompatible layout or discarding the other's useful metadata and artwork.

## Context

organiseMyVideo currently provides a scriptable CLI. Its existing REQ-002
(Qt media-library browser) already covers an MCM-inspired browsing slice;
ADR-004 proposes Qt architecture and ADR-008 establishes the catalogue as the UI
record. This OMV record owns the broader application design and implementation,
including the terminal surface and staged functional coverage. REQ-002 remains
the initial browsing slice; broader editing/automation work must have explicit
acceptance through this record's agreed delivery matrix or a separately scoped
OMV requirement, not a silent change to REQ-002.

The same-named [OMS REQ-012](https://github.com/Glawster/organiseMediaStudio/blob/feature/012-videoInterfaceDesign/project/requirements/features/012-videoInterfaceDesign.md)
owns mediaStudio dispatch, shared configuration handoff, optional provider
discovery and generic media integration. The branch link becomes available when
published; its authoritative repository path is
project/requirements/features/012-videoInterfaceDesign.md. OMV requirement IDs
are local: 012 is already allocated, so this counterpart uses the next ID, 040.

Video baseline inspected: revision `4c2e96aabe922881a2941318a9c445420c9ca078`.
MCM's official overview, gallery and feature comparison were reviewed on
2026-10-25; inspect actual gallery screenshots when producing the design.
Functional resemblance is the goal, using original suite styling and assets.

The user reports that MCM can run under Wine and perform its media-management
duties there. Treat it as a working interoperability partner, not only a visual
reference. Record the actual MCM/Wine versions, configuration and observed
capabilities during design verification; Wine compatibility has not been tested
as part of capturing this requirement.

## Scope

- Produce `documentation/videoInterfaceDesign.md` with the proposed information
  architecture, annotated Qt/TUI wireframes, user journeys and feature matrix.
- Review MCM's library overview, collection navigation, results, artwork/details,
  menus, context actions, metadata editing/fetching, task status and preferences.
  Map observed reference behaviour to Video services, delivery slices, gaps and
  explicit retain/adapt/defer decisions, with evidence and reasons.
- Cover the following functional groups in the matrix; inclusion here requires
  a design decision, not automatic implementation of every MCM capability:

| Group | Required design assessment |
| --- | --- |
| Collections | Movies, TV series/seasons/episodes; retain Video-specific Home Video, camera/removable volumes, Audio, Audiobooks and Ebooks. |
| Browsing | Cached catalogue loading, list/grid alternatives, search, filtering, sorting, selection and detail inspection. |
| Metadata | Identification/matching, provider selection, fetch/refetch, review/edit, provenance and sidecar/export formats. |
| Artwork | Posters, backgrounds, banners, thumbnails, artwork selection and missing-artwork states. |
| Organisation | Rename/move proposals, folders, cleanup, duplicates, conflicts and recovery through existing safety services. |
| Technical inspection | Available codecs, duration, dimensions, tracks and subtitle information. |
| Jobs | Queued/background work, progress, cancellation, retries, logs and per-item results. |
| Integrations | Assess existing Video download/import automation plus MCM-style subtitles, trailers, post-processing, media-server and provider integrations; map supported work and explicitly record gaps/deferred scope. |
| MCM under Wine | Shared library roots, Wine drive/path mappings, naming conventions, metadata/sidecar formats, artwork and safe handoff between MCM and Video. |

- Specify `mediaStudio video` for Qt and `mediaStudio video --ui` for Textual,
  with shared Studio settings and optional `--config`. Keep the existing
  `organiseMyVideo` commands, arguments, automation and exit semantics supported.
- Design a visually rich Qt browser and a keyboard-driven TUI for catalogue
  queries, inventory, job status and safe action review. Define artwork/visual
  handoffs where the terminal cannot provide equivalent inspection.
- Read library collections through Video's catalogue/query services. Catalogue
  refresh is an explicit background service action; opening or filtering a view
  must not perform an organising scan or mutate media.
- Map Home Video capture-date evidence/correction and removable-media inventory
  into the layout rather than losing those workflows in an MCM-only clone.
- Design for MCM and Video to operate on the same library as compatibly as
  practical. Map Wine-visible drive/UNC paths to native paths without storing
  Wine-specific assumptions in media identity. Assess filename case, Unicode,
  permissions and offline/mounted roots against the actual shared filesystem.
- Inventory the metadata, sidecar and artwork conventions MCM actually uses in
  the target installation. Define which values Video can read, preserve and
  write compatibly, including stable title/provider identities and unrecognised
  fields. Specify round-trip and conflict rules rather than silently replacing
  MCM output with an incompatible format or requiring library reorganisation.
- Define a safe handoff: detect changes made by the other application, refresh
  Video's catalogue, and revalidate pending edits/operation plans. State whether
  concurrent writers are supported; if not, specify a sequential workflow and
  actionable conflict handling. Do not assume Wine supplies cross-application
  locking or that MCM knows about Video's locks.
- Design and implement the actual Qt and TUI applications in the OMV package
  over framework-independent catalogue/query and operation services. Own the
  screens, collections, details, artwork views, metadata review, jobs and action
  adapters; keep scanning/provider calls and media mutation out of UI handlers.
- Package independently invocable Qt/TUI providers conforming to OMS REQ-012's
  agreed contract. Consume the shared config path and selected surface, establish
  OMV logging and own the event loop, exit codes, worker cancellation and shutdown.
  Preserve the standalone organiseMyVideo CLI, arguments, automation and default
  preview behaviour with no mandatory UI or Wine dependency.
- Reuse OMS settings and media services through application adapters; OMV owns
  configuration mapping, catalogue paths, MCM schemas/artwork conventions, Wine
  path translation and safe operation execution. Do not implement the Studio
  dispatcher or copy missing generic media engines into OMV views.
- Implement the approved delivery matrix in verifiable slices: catalogue-backed
  browsing first, then explicitly scoped management and compatibility features.
  Define service/provider and worker architecture before dependent code;
  coordinate the OMS launch ADR and retain consumer catalogue/policy ownership.

## Out of scope

- Unconditionally implementing every MCM integration in the first release, or
  removing existing Video CLI commands. The reviewed matrix controls staged scope.
- Reusing MCM code/assets or assuming its Windows-only integrations are portable.
- Requiring Wine or MCM for normal Video operation, changing MCM itself, or
  claiming every MCM/provider integration works under every Wine configuration.
- Enabling file mutation, metadata writes, downloads or post-processing solely
  because a reference screenshot contains a related control.
- Replacing Video REQ-002 or changing its browsing-only scope without explicit
  change control. Delivery of editing/automation needs separately owned criteria.
- Replacing the SQLite catalogue with a live directory walk or a suite database.

## Acceptance criteria

1. The feature matrix cites reviewed official references and maps each group
   above to observed behaviour, Video capability/requirement, Qt/TUI treatment,
   implementation slice or a reasoned deferral. Missing features are visible.
2. Annotated Qt designs cover collection navigation, results, artwork/details,
   metadata review, context actions and job/status feedback with an explicit
   comparison to the MCM reference. Differences required by supported platforms,
   original suite styling or safety policy are explained rather than accidental.
3. The TUI design covers catalogue navigation/search, details, operational
   actions and jobs, with explicit visual handoffs and keyboard/exit behaviour.
   It follows the established Studio field, checkbox and spacing conventions.
4. Launch/configuration and optional-dependency contracts are specified for both
   interfaces. A regression plan demonstrates that existing Video CLI workflows
   and non-interactive automation remain available independently of either UI.
5. Every proposed mutating/network action names its owning service, permission/
   confirmation boundary, plan revalidation, partial failure, retry/cancellation
   and recovery. Browsing remains observational; missing data is not fabricated.
6. The design reconciles Video REQ-002, catalogue/home-video/removable-volume
   requirements and ADR-004/008, identifying which implementation records need
   refinement or new criteria without claiming their acceptance is already met.
7. The delivery plan defines an initial catalogue-backed browsing slice, then
   separately testable feature groups prioritised toward MCM functional coverage.
   Deferred capabilities have explicit reasons and revisit conditions; all MCM
   features are not silently excluded behind a permanent read-only shell.
8. Ownership and packaging decisions keep the media core headless and preserve
   one-way consumer dependencies. OMV provides the UI executables; OMS owns only
   dispatch and shared contracts. Agree worker/provider decisions before coding
   without adding a reverse core dependency.
9. The compatibility matrix records the tested MCM/Wine environment and maps
   shared roots, path translations, naming, metadata/sidecar formats, artwork
   and provider identities to supported, partial or unsupported behaviour.
   Each limitation has a reason, workaround where feasible and revisit condition.
10. The design includes bidirectional fixture scenarios: MCM creates or updates
    metadata/artwork that Video reads and preserves, and Video produces proposed
    outputs that MCM can consume. Specify semantic round-trip expectations,
    preservation of unrecognised data and detection of external renames/edits;
    distinguish observed compatibility from capabilities requiring implementation.
11. A documented shared-library handoff prevents stale Video plans from
    overwriting MCM changes. Concurrent-write support is demonstrated or
    explicitly excluded in favour of sequential use. Video's standalone CLI and
    Qt/TUI operation do not depend on Wine or MCM being installed.

12. Real OMV Qt/TUI providers launch independently and via the actual OMS
    commands with shared default settings or the supplied --config override.
    Missing optional providers/dependencies and startup errors are actionable;
    tests verify config paths containing spaces, exit codes and interruption.
13. The first catalogue-backed slice works with real temporary SQLite records,
    existing query services and media fixtures. Browsing/filtering are read-only;
    refresh is an explicit cancellable service action that respects REQ-029.
    Later delivered slices have working controls and acceptance evidence, not
    wireframes or a launch-only shell presented as complete functionality.
14. Qt/TUI actions use real headless OMV services and OMS media adapters.
    Confirmed mutations revalidate sources/destinations and preserve matched
    metadata/artwork, recoverable originals and audit history. Retry, partial
    failure and cancellation leave no unverified publication or orphaned worker.
15. Every delivered feature group has real UI-to-service integration evidence,
    keyboard/scale checks, CLI regression coverage and optional/headless install
    evidence. MCM/Wine compatibility claims include disposable-library round-trip
    evidence in the recorded environment; unavailable environments remain
    explicitly unverified. A design document alone does not complete this record.

## Dependencies and decisions

- [OMS REQ-012: Video interface design](https://github.com/Glawster/organiseMediaStudio/blob/feature/012-videoInterfaceDesign/project/requirements/features/012-videoInterfaceDesign.md): Studio launch/provider and shared-service integration.
- [REQ-002](002-qtMediaLibraryBrowser.md): initial Qt browsing acceptance;
  [REQ-010](010-sqliteMediaCatalogue.md), [REQ-014](014-homeVideoCatalogue.md) and
  [REQ-015](015-usbVolumeInventory.md): catalogue and collection contracts.
- [REQ-006](006-cliArchitecture.md), [REQ-007](007-filesystemSafety.md),
  [REQ-022](022-sharedMediaProcessing.md), [REQ-029](029-nonDestructiveMediaScan.md),
  [REQ-024](024-cameraCaptureTimeCorrection.md),
  [REQ-033](033-cameraFolderCaptureCorrection.md) and
  [REQ-035](035-movieIdentityConflictDetection.md) retain their own behaviour
  and acceptance; refine a dependency where new UI work changes its contract.
- [ADR-003](../../adr/003-filesystemSafetyBoundary.md),
  [ADR-004](../../adr/004-qtApplicationArchitecture.md),
  [ADR-008](../../adr/008-sqliteMediaCatalogue.md) and
  [ADR-010](../../adr/010-sharedMediaProcessingBoundary.md).
  Resolve proposed UI architecture and the joint launch/worker contract before
  implementing the affected optional application adapters.

## Verification

- Review actual official MCM gallery images and feature evidence; record reference
  URLs, review date and what was observed versus inferred. Avoid treating the
  feature comparison as a complete interaction specification.
- Trace existing Video services/CLI commands to the matrix and wireframe flows.
- Review Qt/TUI navigation, representative sizes, empty/offline/error states,
  background jobs and cancellation with synthetic catalogue examples.
- Execute CLI regressions and actual Qt/TUI-to-service integration tests per
  implemented slice, including configuration mapping, catalogue reads, explicit
  plan review, failed/stale operations, cancellation and clean worker shutdown.
- Package and launch both real providers through OMS with temporary configs and
  fixtures. Verify headless/CLI-only installs independently of the UI extras.
- Follow the repository testing process: golden expectations, boundary tests,
  representative platform/display sizes, and clean-state catalogue reconstruction
  where persistence changes. Mocks alone do not prove operational composition.
- Use a disposable fixture library with the target MCM installation under Wine
  to assess metadata/artwork exchange, native/Wine path mapping, external-change
  discovery and sequential handoff. Preserve before/after evidence and report
  unavailable environments as unverified, not compatible by assumption.
- Run the OMV development environment's suite, lint/format and project checks,
  plus `git diff --check`; report dependency skips and unavailable Wine evidence.

## Sources

- [MCM overview](https://www.mediacentermaster.com/): metadata, artwork and organisation capability reference.
- [MCM gallery](https://www.mediacentermaster.com/gallery/): visual/interaction reference to inspect during design.
- [MCM feature comparison](https://licensing.mediacentermaster.com/Compare_Versions.aspx): feature coverage checklist, not an implementation commitment.

## Change history

- 2026-10-26: created as OMV's same-named design and implementation counterpart
  to OMS REQ-012; retains MCM-like functionality and practical Wine/shared-library
  compatibility while placing launch/shared-service work in OMS.
