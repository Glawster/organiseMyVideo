# Requirements

Next available number: 038

Requirements created after adoption of the managed process are recorded here.
Historical behaviour is not assigned invented retrospective requirements.

| Req ID | Requirement | Description | Status | Agent Prompt | Architecture Decisions |
| --- | --- | --- | --- | --- | --- |
| 001 | [Standards adoption governance](features/001-standardsAdoption.md) | Establish traceable governance for the standards migration. | Completed | [Prompt](prompt/001-standardsAdoption.md) | [ADR-001](../adr/001-packagedCliLayout.md), [ADR-002](../adr/002-cliCompatibility.md), [ADR-003](../adr/003-filesystemSafetyBoundary.md) |
| 002 | [Qt media-library browser](features/002-qtMediaLibraryBrowser.md) | Browse movie, television, audio, audiobook, and ebook libraries in a desktop interface. | ToDo | [Refinement prompt](prompt/002-qtMediaLibraryBrowser.md) | [ADR-004](../adr/004-qtApplicationArchitecture.md) |
| 003 | [Imagine API archive](features/003-imagineArchive.md) | Generate, list, and download Imagine images and videos through the official xAI API with `storage_options`. | Completed | [Prompt](prompt/003-imagineArchive.md) | [ADR-005](../adr/005-imagineApiStorage.md) |
| 004 | [Camera media import](features/004-cameraMediaImport.md) | Safely import GoPro and DJI originals through Python services and a camera import subcommand. | InProgress | [Prompt](prompt/004-cameraMediaImport.md) | [ADR-006](../adr/006-cameraImportArchitecture.md) |
| 005 | [Reproducible packaging and installation](features/005-reproduciblePackaging.md) | Make package installation, execution, tests, and hooks reproducible. | Completed | [Prompt](prompt/005-reproduciblePackaging.md) | [ADR-001](../adr/001-packagedCliLayout.md) |
| 006 | [Entry-point and CLI architecture](features/006-cliArchitecture.md) | Use established logging and provide canonical commands with legacy compatibility. | Completed | [Prompt](prompt/006-cliArchitecture.md) | [ADR-001](../adr/001-packagedCliLayout.md), [ADR-002](../adr/002-cliCompatibility.md) |
| 007 | [Central filesystem safety](features/007-filesystemSafety.md) | Route mutations through a dry-run-aware, recoverable operation boundary. | Completed | [Prompt](prompt/007-filesystemSafety.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md) |
| 008 | [CLI simplification](features/008-cliSimplification.md) | Replace overlapping Grok commands and remove obsolete interaction flags. | Completed | [Prompt](prompt/008-cliSimplification.md) | Not required |
| 009 | [Camera card inventory](features/009-cameraCardInventory.md) | Catalogue a numbered SD card's dates, size, and thumbnail-derived content in SQLite. | InProgress | [Prompt](prompt/009-cameraCardInventory.md) | [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-007](../adr/007-cameraInventoryPersistence.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 010 | [SQLite media catalogue](features/010-sqliteMediaCatalogue.md) | Store movies, TV, and camera cards in one SQLite catalogue that scans update and the UI reads. | Completed | [Prompt](prompt/010-sqliteMediaCatalogue.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 011 | [Dash cam card support](features/011-dashcamCardSupport.md) | Inventory dash-cam SD cards with the same numeric card-ID routine as GoPro and DJI. | Completed | [Prompt](prompt/011-dashcamCardSupport.md) | [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 012 | [Camera card ID file](features/012-cameraCardIdFile.md) | Write a machine-readable card ID onto the SD card on confirmed inventory. | Completed | [Prompt](prompt/012-cameraCardIdFile.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-007](../adr/007-cameraInventoryPersistence.md) |
| 013 | [Camera card ID reassign](features/013-cameraCardIdRetie.md) | Explicit confirmed action to change the numeric ID bound on an SD card. | Completed | [Prompt](prompt/013-cameraCardIdRetie.md) | Not required |
| 014 | [Home video catalogue](features/014-homeVideoCatalogue.md) | Present `/mnt/myVideo/Video` as a logical Home Video timeline with capture-date provenance, audit issues, sidecars, duplicate candidates, and camera-import provenance. | ToDo | [Prompt](prompt/014-homeVideoCatalogue.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md), [ADR-010](../adr/010-sharedMediaProcessingBoundary.md) |
| 015 | [USB volume inventory](features/015-usbVolumeInventory.md) | Inventory USB thumb drives with the same numeric ID, size, and free space as SD cards. | ToDo | [Prompt](prompt/015-usbVolumeInventory.md) | [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 016 | [Catalogue media identities](features/016-catalogueMediaIdentities.md) | Prepare external identities, home-video rows, and removable-volume kinds with safe schema upgrades. | Completed | [Prompt](prompt/016-catalogueMediaIdentities.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md), [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 017 | [Merge duplicate TV and movie folders](features/017-mergeDuplicateTvFolders.md) | Merge provider-identified duplicate TV and movie folders into the most complete existing folder. | Completed | [Prompt](prompt/017-mergeDuplicateTvFolders.md) | Not required |
| 018 | [TV show folder leading articles](features/018-tvShowFolderArticles.md) | Store ``The Show`` folders as ``Show, The`` and repair existing library folders. | Completed | [Prompt](prompt/018-tvShowFolderArticles.md) | Not required |
| 019 | [Catalogue metadata resolution](features/019-catalogueMetadataResolution.md) | Resolve the best already-known movie, series and episode metadata offline while preserving durable provider IDs. | Completed | [Prompt](prompt/019-catalogueMetadataResolution.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 020 | [Combined media scan command](features/020-combinedMediaScan.md) | Expose the original movie/TV scan as `media scan`, using the configured source by default with a `--source` override. | InProgress | [Prompt](prompt/020-combinedMediaScan.md) | Not required |
| 021 | [Removable media discovery and lifecycle](features/021-removableMediaDiscovery.md) | Search numbered SD/USB volumes, recommend suitable cards, and derive safe-to-recycle status from inventory and verified import evidence. | ToDo | [Prompt](prompt/021-removableMediaDiscovery.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md), [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 022 | [Shared media processing platform](features/022-sharedMediaProcessing.md) | Use `organiseMediaStudio` as the shared headless image/video processing platform for `organiseMyVideo` and `organiseMyPhotos`. | InProgress | [Prompt](prompt/022-sharedMediaProcessing.md) | [ADR-010](../adr/010-sharedMediaProcessingBoundary.md) |
| 023 | [Removable media format and recycle](features/023-removableMediaFormat.md) | Safely format only archived numbered media, recreate its identity, and persist a fresh empty snapshot. | InProgress | Not required | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 024 | [Camera capture-time correction](features/024-cameraCaptureTimeCorrection.md) | Correct current media capture times through repeatable transformations with immutable audit history and recoverable execution. | Completed | Not required | [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-011](../adr/011-cameraCaptureCorrectionJournal.md) |
| 025 | [Media keywords and tagging](features/025-mediaKeywords.md) | Add descriptive keywords to media without changing date-based filesystem organisation. | ToDo | Not required | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 026 | [Camera archive normalisation](features/026-cameraArchiveNormalisation.md) | Normalise legacy GoPro, Drone, and Dashcam archive layouts into the canonical numeric date hierarchy. | ToDo | Not required | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-006](../adr/006-cameraImportArchitecture.md) |
| 027 | [SLR card import](features/027-slrCardImport.md) | Import mixed SLR photo/video cards by media type beneath `By Date/YYYY/MM/DD`. | Completed | [Prompt](prompt/027-slrCardImport.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-007](../adr/007-cameraInventoryPersistence.md) |
| 028 | [Camera history reconciliation](features/028-cameraHistoryReconciliation.md) | Verify import history against the current archive and reconcile moved files without losing original destination evidence. | Completed | [Prompt](prompt/028-cameraHistoryReconciliation.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 029 | [Non-destructive media scan](features/029-nonDestructiveMediaScan.md) | Make `media scan` observational only; move renames/moves/merges to `media organise` and deletions to `media clean`. | ToDo | [Prompt](prompt/029-nonDestructiveMediaScan.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 030 | [Operational run audit](features/030-operationalRunAudit.md) | Retain verification evidence and per-run reports. | ToDo | Not required | Not required |
| 031 | [Media structure discovery](features/031-mediaStructureDiscovery.md) | Discover and review media-library structures. | ToDo | Not required | Not required |
| 032 | [Application-wide CLI Tab completion](features/032-cliTabCompletion.md) | Complete commands, options, paths and contextual local values consistently across the public CLI. | ToDo | [Prompt](prompt/032-cliTabCompletion.md) | Pending |
| 033 | [Camera folder capture-time correction](features/033-cameraFolderCaptureCorrection.md) | Correct existing camera folders without prior import history using frozen folder evidence and verified relocation. | Completed | [Prompt](prompt/033-cameraFolderCaptureCorrection.md) | [ADR-011](../adr/011-cameraCaptureCorrectionJournal.md) |
| 034 | [Catalogue location reconciliation](features/034-catalogueLocationReconciliation.md) | Reconcile movie and TV catalogue locations with authoritatively scanned roots without dropping an unscanned disk. | Completed | Not required | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 035 | [Movie identity conflict detection](features/035-movieIdentityConflictDetection.md) | Flag title and release-year identity changes instead of routine movie renames, make canonical names filesystem-safe, and classify existing targets without overwriting. | Completed | [Prompt](prompt/035-movieIdentityConflictDetection.md) | Not required |
| 036 | [Incoming media preparation workflow](features/036-incomingMediaPreparation.md) | Restrict `media clean` to incoming/staging hygiene and define the clean -> scan -> organise workflow. | ToDo | [Prompt](prompt/036-incomingMediaPreparation.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md) |
| 037 | [Media storage redistribution](features/037-mediaStorageRedistribution.md) | Rebalance movie and TV stores by utilisation percentage using persisted dry-run plans and confirmed whole-folder moves. | ToDo | Not required | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |

## Prompt index

<!-- OMP-PROMPT-INDEX-BEGIN -->
- [001-standardsAdoption](prompt/001-standardsAdoption.md)
- [002-qtMediaLibraryBrowser](prompt/002-qtMediaLibraryBrowser.md)
- [003-imagineArchive](prompt/003-imagineArchive.md)
- [004-cameraMediaImport](prompt/004-cameraMediaImport.md)
- [005-reproduciblePackaging](prompt/005-reproduciblePackaging.md)
- [006-cliArchitecture](prompt/006-cliArchitecture.md)
- [007-filesystemSafety](prompt/007-filesystemSafety.md)
- [008-cliSimplification](prompt/008-cliSimplification.md)
- [009-cameraCardInventory](prompt/009-cameraCardInventory.md)
- [010-sqliteMediaCatalogue](prompt/010-sqliteMediaCatalogue.md)
- [011-dashcamCardSupport](prompt/011-dashcamCardSupport.md)
- [012-cameraCardIdFile](prompt/012-cameraCardIdFile.md)
- [013-cameraCardIdRetie](prompt/013-cameraCardIdRetie.md)
- [014-homeVideoCatalogue](prompt/014-homeVideoCatalogue.md)
- [015-usbVolumeInventory](prompt/015-usbVolumeInventory.md)
- [016-catalogueMediaIdentities](prompt/016-catalogueMediaIdentities.md)
- [017-mergeDuplicateTvFolders](prompt/017-mergeDuplicateTvFolders.md)
- [018-tvShowFolderArticles](prompt/018-tvShowFolderArticles.md)
- [019-catalogueMetadataResolution](prompt/019-catalogueMetadataResolution.md)
- [020-combinedMediaScan](prompt/020-combinedMediaScan.md)
- [021-removableMediaDiscovery](prompt/021-removableMediaDiscovery.md)
- [022-sharedMediaProcessing](prompt/022-sharedMediaProcessing.md)
- [027-slrCardImport](prompt/027-slrCardImport.md)
- [028-cameraHistoryReconciliation](prompt/028-cameraHistoryReconciliation.md)
- [029-nonDestructiveMediaScan](prompt/029-nonDestructiveMediaScan.md)
- [032-cliTabCompletion](prompt/032-cliTabCompletion.md)
- [033-cameraFolderCaptureCorrection](prompt/033-cameraFolderCaptureCorrection.md)
- [035-movieIdentityConflictDetection](prompt/035-movieIdentityConflictDetection.md)
- [036-incomingMediaPreparation](prompt/036-incomingMediaPreparation.md)
<!-- OMP-PROMPT-INDEX-END -->
