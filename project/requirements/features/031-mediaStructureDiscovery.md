# 031: Media structure discovery and organisation review

## Status

ToDo

## Outcome

As a media-library operator, I need organiseMyVideo to discover how an existing personal-media library is organised, classify the apparent role and purpose of its contents, and present the evidence in a review UI so that I can establish organisation policy without OMV imposing one user's historical folder structure on every library.

Discovery is advisory and non-destructive. Filesystem changes remain the responsibility of a separate confirmed organisation operation.

## Architecture

Follow the organise-suite `Discovery before configuration` principle defined in organiseMediaStudio:

```text
DISCOVER -> INFER -> REVIEW -> POLICY -> PLAN -> APPLY
```

Where media-discovery primitives are genuinely reusable by video and photo workflows, prefer implementing them in organiseMediaStudio rather than duplicating them in OMV and OMP.

## Classification model

OMV shall distinguish between two dimensions.

### Media/file role

- `original` — original camera, phone, capture, or transferred media.
- `derivative` — transcoded, enhanced, stabilised, rendered, or otherwise derived media where supported by evidence.
- `production` — finished media intended for viewing or sharing.
- `project` — editing-project or working material.
- `duplicate` — content identity established safely; filename similarity alone is insufficient.
- `unknown` — insufficient evidence.

### Collection purpose

- `date`
- `source`
- `subject`
- `event`
- `project`
- `production`
- `mixed`
- `unknown`

A folder's collection purpose must not force every contained file to have the same media role.

## Discovery

Evidence may include catalogue identities and digests, duplicate relationships, media metadata and capture dates, filename families, directory patterns, recognised project/sidecar formats, original/derivative relationships, import/card provenance, dominant conventions elsewhere in the library, and prior user-confirmed classifications.

Folder names may be supporting evidence but must not be universal rules. In particular, the current archive's `Home Video`, `Extension`, `Evelyn`, `Video8`, `VideoDV`, and `Video/Video` names are motivating examples only.

Discovery should identify dominant conventions and structural outliers and retain enough evidence to explain each inferred classification. Uncertain cases remain uncertain.

## User policy

Discovery answers `What appears to exist now?`; policy answers `How does this user want media of these roles and purposes organised?`.

OMV must not assume universal destinations such as `Home Video`, `Archive`, `Projects`, or `By Date`. Confirmed classifications and policy choices should be persisted so later scans refine the model rather than repeatedly asking the same questions.

Configuration records policy and overrides rather than restating reliably discoverable facts.

## Media Organisation Review UI

Provide a Qt review UI over the same application services used by the CLI. Discovery/classification logic must not live in Qt widgets.

The UI shall show the library tree, inferred collection purpose and media roles, certainty/evidence, counts, duplicates, structural anomalies, confirmed/proposed conventions, and organisation policy. The user can accept or correct classifications before an organisation plan is produced.

Low-confidence or `unknown` classifications must not become automatic organise actions.

## Brand

The UI shall use the established FMSAT CSS/QSS colour scheme and visual language as the default organise-suite brand theme. This is not a screen-local colour choice. Presentation colours must live in theme/stylesheet definitions rather than business logic, and reusable theme definitions should be shared through organiseMediaStudio where practical.

## Safety

`media scan`, discovery, inference, review, and planning remain non-destructive. Move, rename, consolidation, and duplicate removal belong to `media organise` or an equivalent explicitly confirmed operation and pass through the filesystem-safety boundary.

## Acceptance criteria

1. OMV can classify arbitrary library structures without requiring the development archive's folder names.
2. Folder collection purpose and individual file roles are represented independently.
3. Subject/event/source/project/production/mixed structures can be proposed from evidence and reviewed by the user.
4. Confirmed duplicates require safe content-identity evidence rather than name similarity alone.
5. Dominant library conventions and structural outliers can be reported with supporting evidence.
6. Low-confidence/unknown inference cannot create an automatic destructive action.
7. User confirmations and policy can be persisted and reused.
8. CLI and Qt consume common application services.
9. The review UI is non-destructive and uses the FMSAT brand theme.
10. Shared discovery primitives are placed in OMS where reusable by OMV and OMP.
11. Tests use synthetic temporary trees representing multiple user structures.
12. Changes to the discovery model consider OMS, OMP, and OMPR impacts as applicable.

## Dependencies

- REQ-002: Qt media-library browser
- REQ-007: Filesystem safety
- REQ-010: SQLite media catalogue
- REQ-014: Home video catalogue
- REQ-016: Catalogue media identities
- REQ-029: Non-destructive media scan
- REQ-030: Operational run audit

## Change history

- 2026-09-27: created — generic media structure discovery, user-reviewed organisation policy, review UI, and FMSAT suite-brand requirement.
