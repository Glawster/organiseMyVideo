# Requirements

Next available number: 027

Requirements created after adoption of the managed process are recorded here.
Historical behaviour is not assigned invented retrospective requirements.

| Req ID | Requirement | Description | Status | Agent Prompt | Architecture Decisions |
| --- | --- | --- | --- | --- | --- |
| 001 | [Standards adoption governance](features/001-standardsAdoption.md) | Establish traceable governance for the standards migration. | Completed | [Prompt](prompt/001-standardsAdoption.md) | [ADR-001](../adr/001-packagedCliLayout.md), [ADR-002](../adr/002-cliCompatibility.md), [ADR-003](../adr/003-filesystemSafetyBoundary.md) |
| 002 | [Qt media-library browser](features/002-qtMediaLibraryBrowser.md) | Browse movie, television, audio, audiobook, and ebook libraries in a desktop interface. | ToDo | [Refinement prompt](prompt/002-qtMediaLibraryBrowser.md) | [ADR-004](../adr/004-qtApplicationArchitecture.md) |
| 003 | [Imagine API archive](features/003-imagineArchive.md) | Generate, list, and download Imagine images and videos through the official xAI API with `storage_options`. | Completed | [Prompt](prompt/003-imagineArchive.md) | [ADR-005](../adr/005-imagineApiStorage.md) |
| 004 | [Camera media import](features/004-cameraMediaImport.md) | Safely import GoPro and DJI originals through Python services and a camera import subcommand. | In progress | [Prompt](prompt/004-cameraMediaImport.md) | [ADR-006](../adr/006-cameraImportArchitecture.md) |
| 005 | [Reproducible packaging and installation](features/005-reproduciblePackaging.md) | Make package installation, execution, tests, and hooks reproducible. | Completed | [Prompt](prompt/005-reproduciblePackaging.md) | [ADR-001](../adr/001-packagedCliLayout.md) |
| 006 | [Entry-point and CLI architecture](features/006-cliArchitecture.md) | Use established logging and provide canonical commands with legacy compatibility. | Completed | [Prompt](prompt/006-cliArchitecture.md) | [ADR-001](../adr/001-packagedCliLayout.md), [ADR-002](../adr/002-cliCompatibility.md) |
| 007 | [Central filesystem safety](features/007-filesystemSafety.md) | Route mutations through a dry-run-aware, recoverable operation boundary. | Completed | [Prompt](prompt/007-filesystemSafety.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md) |
| 008 | [CLI simplification](features/008-cliSimplification.md) | Replace overlapping Grok commands and remove obsolete interaction flags. | Completed | [Prompt](prompt/008-cliSimplification.md) | Not required |
| 009 | [Camera card inventory](features/009-cameraCardInventory.md) | Catalogue a numbered SD card's dates, size, and thumbnail-derived content in SQLite. | Completed | [Prompt](prompt/009-cameraCardInventory.md) | [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-007](../adr/007-cameraInventoryPersistence.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 010 | [SQLite media catalogue](features/010-sqliteMediaCatalogue.md) | Store movies, TV, and camera cards in one SQLite catalogue that scans update and the UI reads. | Completed | [Prompt](prompt/010-sqliteMediaCatalogue.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 011 | [Dash cam card support](features/011-dashcamCardSupport.md) | Inventory dash-cam SD cards with the same numeric card-ID routine as GoPro and DJI. | Completed | [Prompt](prompt/011-dashcamCardSupport.md) | [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 012 | [Camera card ID file](features/012-cameraCardIdFile.md) | Write a machine-readable card ID onto the SD card on confirmed inventory. | Completed | [Prompt](prompt/012-cameraCardIdFile.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-007](../adr/007-cameraInventoryPersistence.md) |
| 013 | [Camera card ID reassign](features/013-cameraCardIdRetie.md) | Explicit confirmed action to change the numeric ID bound on an SD card. | Completed | [Prompt](prompt/013-cameraCardIdRetie.md) | Not required |
| 014 | [Home video catalogue](features/014-homeVideoCatalogue.md) | Present `/mnt/myVideo/Video` as a logical Home Video timeline with capture-date provenance, audit issues, sidecars, duplicate candidates, and camera-import provenance. | ToDo | [Prompt](prompt/014-homeVideoCatalogue.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md), [ADR-010](../adr/010-sharedMediaProcessingBoundary.md) |
| 015 | [USB volume inventory](features/015-usbVolumeInventory.md) | Inventory USB thumb drives with the same numeric ID, size, and free space as SD cards. | ToDo | [Prompt](prompt/015-usbVolumeInventory.md) | [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 016 | [Catalogue media identities](features/016-catalogueMediaIdentities.md) | Prepare external identities, home-video rows, and removable-volume kinds with safe schema upgrades. | Completed | [Prompt](prompt/016-catalogueMediaIdentities.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md), [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 017 | [Merge duplicate TV and movie folders](features/017-mergeDuplicateTvFolders.md) | Merge provider-identified duplicate TV and movie folders into the most complete existing folder. | Completed | [Prompt](prompt/017-mergeDuplicateTvFolders.md) | Not required |
| 018 | [TV show folder leading articles](features/018-tvShowFolderArticles.md) | Store ``The Show`` folders as ``Show, The`` and repair existing library folders. | Completed | [Prompt](prompt/018-tvShowFolderArticles.md) | Not required |
| 019 | [Catalogue metadata resolution](features/019-catalogueMetadataResolution.md) | Resolve the best already-known movie, series and episode metadata offline while preserving durable provider IDs. | In progress | [Prompt](prompt/019-catalogueMetadataResolution.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 020 | [Removable media discovery and lifecycle](features/020-removableMediaDiscovery.md) | Search numbered SD/USB volumes, recommend suitable cards, and derive safe-to-recycle status from inventory and verified import evidence. | ToDo | [Prompt](prompt/020-removableMediaDiscovery.md) | [ADR-008](../adr/008-sqliteMediaCatalogue.md), [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 021 | [Shared media processing platform](features/021-sharedMediaProcessing.md) | Use `organiseMediaStudio` as the shared headless image/video processing platform for `organiseMyVideo` and `organiseMyPhotos`. | In progress | [Prompt](prompt/021-sharedMediaProcessing.md) | [ADR-010](../adr/010-sharedMediaProcessingBoundary.md) |
| 022 | [Removable media format and recycle](features/022-removableMediaFormat.md) | Safely format only archived numbered media, recreate its identity, and persist a fresh empty snapshot. | In progress | Not required | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-009](../adr/009-numberedRemovableVolumes.md) |
| 023 | [Camera capture-time correction](features/023-cameraCaptureTimeCorrection.md) | Correct known camera-clock errors while preserving original timestamp evidence and elapsed-time relationships. | Planned | Not required | [ADR-006](../adr/006-cameraImportArchitecture.md) |
| 024 | [Media keywords and tagging](features/024-mediaKeywords.md) | Add descriptive keywords to media without changing date-based filesystem organisation. | Planned | Not required | [ADR-008](../adr/008-sqliteMediaCatalogue.md) |
| 025 | [Camera archive normalisation](features/025-cameraArchiveNormalisation.md) | Normalise legacy GoPro, Drone, and Dashcam archive layouts into the canonical numeric date hierarchy. | Planned | Not required | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-006](../adr/006-cameraImportArchitecture.md) |
| 026 | [SLR card import](features/026-slrCardImport.md) | Import mixed SLR photo/video cards by media type beneath `By Date/YYYY/MM/DD`. | Completed | [Prompt](prompt/026-slrCardImport.md) | [ADR-003](../adr/003-filesystemSafetyBoundary.md), [ADR-006](../adr/006-cameraImportArchitecture.md), [ADR-007](../adr/007-cameraInventoryPersistence.md) |

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
- [020-removableMediaDiscovery](prompt/020-removableMediaDiscovery.md)
- [021-sharedMediaProcessing](prompt/021-sharedMediaProcessing.md)
- [026-slrCardImport](prompt/026-slrCardImport.md)
<!-- OMP-PROMPT-INDEX-END -->