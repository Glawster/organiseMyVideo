# Home video archive

## Status

Agreed catalogue plan for
[REQ-014](../project/requirements/features/014-homeVideoCatalogue.md).
Indexing is not implemented yet. Camera import into this tree remains
[REQ-004](../project/requirements/features/004-cameraMediaImport.md).
Generic structure discovery, classification, organisation review, and its UI
are specified by
[REQ-031](../project/requirements/features/031-mediaStructureDiscovery.md).

## Outcome

Personal video under `/mnt/media/homeVideo` is a catalogue collection of its
own. GoPro, Drone, and Dashcam archives are folders inside that collection,
not movie or TV titles.

The current physical tree is historical evidence, not a canonical layout that
OMV should impose on other users. OMV discovers the organisation patterns in
each library and allows the user to confirm or correct them before policy is
applied.

## Location

```text
/mnt/media/homeVideo/         Video Master
/mnt/media/homeVideo/byDate/  Video Root
```

Master and root are defined in
[Media library organisation](../../organiseMediaStudio/documentation/mediaLibraryOrganisation.md#master-and-root).
This catalogue covers the whole master, not only the root.

TV for the organiser stays in the configured TV locations, currently
`/mnt/video/TV` and `/mnt/raid/TV`. Do not scan those as home video.

## First-level folders (observed)

| Folder | Observed content / current interpretation |
| --- | --- |
| `GoPro` | Camera originals, mostly dated directories, plus some loose AVI |
| `Drone` | DJI source media |
| `Dashcam` | Dash camera media |
| `byDate` | Personal/family footage organised primarily by date |
| `Video8`, `VideoDV` | Named for tape formats; contents need discovery/review |
| `Productions` | Finished or production material; needs discovery/review |
| `Extension`, `Evelyn`, `Cycling`, `Singapore`, `Meghan In Moldova`, `M & J Wedding`, `Misc` | Topic, subject, event, project, or production-oriented collections requiring discovery/review |
| `Rugby`, `Footy`, `Music` | Personal recordings, not the TV library |
| `Captures`, `Favourites` | Described as empty or tiny leftovers before the move; recheck during discovery |

These descriptions document this archive only. The folder names must not be
encoded as universal classification rules.

New camera imports continue to land in the source-specific dated structures
defined by REQ-004. Their physical destination is user/configuration policy,
not a universal Home Video layout.

## Discovery and policy

REQ-031 separates media/file role from collection purpose. A folder can be
source-, date-, subject-, event-, project-, production-, mixed-, or
unknown-oriented while individual files retain roles such as original,
derivative, production, project, duplicate, or unknown.

Discovery answers `What appears to exist now?`; policy answers `How does this
user want media of these roles and purposes organised?`. OMV may use names as
supporting evidence but must infer from metadata, identities, relationships,
and dominant library patterns rather than hard-code this archive's names.

Confirmed classifications and policy should be retained so later scans refine
the model rather than repeatedly asking the same questions.

## Organisation review UI

REQ-031 provides a Media Organisation Review UI exposing the library tree,
classifications, evidence, duplicate relationships, structural anomalies, and
emerging policy before an organisation plan is produced.

The UI uses the established FMSAT CSS/QSS colour scheme and visual language as
the default organise-suite brand theme. Presentation colours remain in shared
theme/stylesheet definitions rather than business logic.

## Rearrangement

Do not wrap the tree in a new `Camera/` or `Recorded/` parent merely to make
the current archive fit a proposed model. Large-scale rearrangement must be
justified by confirmed user policy and handled through the filesystem-safe
organisation workflow.

Leave these to existing or later dry-run migrations/organisation plans:

- REQ-004 `camera migrate` for camera-import normalisation;
- loose `GOPR*.avi` sitting beside dated camera folders;
- editing/project files mixed with finished productions;
- confirmed duplicate copies.

Ambiguous or conflicting items stay put until a confirmed organisation plan
names them. Low-confidence or unknown classifications must not become
automatic destructive actions.

## Catalogue

`library rescan` replaces `homeVideoItem` rows from this root. The UI reads
`catalogueHomeVideoList()`. Each row keeps the first-level kind so historical
GoPro/Drone footage can be filtered without requiring a second library.

REQ-031 may add discovered role, collection-purpose, evidence, certainty, and
user-confirmed policy data to the catalogue/application model. The catalogue
remains independent of the physical spelling of historical folders.

## Verification

Tests use temporary trees. They must not depend on the real
`/mnt/media/homeVideo` mount. REQ-031 tests should include multiple synthetic
layouts so implementation cannot accidentally learn this archive's folder
names as universal rules.
