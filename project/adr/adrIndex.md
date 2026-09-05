# Architecture decisions

Architecture decision records capture consequential choices separately from
requirements. Identifiers and file paths are permanent; superseded records stay
in place and link to their replacements.

| ADR | Decision | Status | Requirements |
| --- | --- | --- | --- |
| 001 | [Preserve the packaged CLI layout](001-packagedCliLayout.md) | Accepted | [REQ-001](../requirements/features/001-standardsAdoption.md) |
| 002 | [Migrate the CLI with compatibility](002-cliCompatibility.md) | Accepted | [REQ-001](../requirements/features/001-standardsAdoption.md), [REQ-006](../requirements/features/006-cliArchitecture.md) |
| 003 | [Centralise filesystem safety](003-filesystemSafetyBoundary.md) | Accepted | [REQ-001](../requirements/features/001-standardsAdoption.md), [REQ-007](../requirements/features/007-filesystemSafety.md) |
| 004 | [Qt application architecture](004-qtApplicationArchitecture.md) | Proposed | [REQ-002](../requirements/features/002-qtMediaLibraryBrowser.md) |
| 005 | [Use the official Imagine API with storage_options](005-imagineApiStorage.md) | Accepted | [REQ-003](../requirements/features/003-imagineArchive.md) |
| 006 | [Implement camera workflows as Python services with subcommand adapters](006-cameraImportArchitecture.md) | Accepted | [REQ-004](../requirements/features/004-cameraMediaImport.md), [REQ-009](../requirements/features/009-cameraCardInventory.md) |
| 007 | [Persist camera-card inventory in SQLite under local state](007-cameraInventoryPersistence.md) | Accepted | [REQ-009](../requirements/features/009-cameraCardInventory.md) |
| 008 | [Use one SQLite catalogue as the UI record](008-sqliteMediaCatalogue.md) | Accepted | [REQ-002](../requirements/features/002-qtMediaLibraryBrowser.md), [REQ-010](../requirements/features/010-sqliteMediaCatalogue.md), [REQ-011](../requirements/features/011-dashcamCardSupport.md), [REQ-014](../requirements/features/014-homeVideoCatalogue.md) |
| 009 | [Numbered removable volumes share one inventory](009-numberedRemovableVolumes.md) | Accepted | [REQ-009](../requirements/features/009-cameraCardInventory.md), [REQ-015](../requirements/features/015-usbVolumeInventory.md) |

Use `Proposed`, `Accepted`, `Rejected`, `Deprecated`, or `Superseded` as the
status. Accept a proposed ADR before implementation becomes costly to unwind.
