# 001: Standards adoption governance

## Status

Completed

## Outcome

As a maintainer, I need the standards migration governed by stable requirements,
architecture decisions, and a sequenced roadmap so that future changes remain
reviewable, testable, and traceable without rewriting project history.

## Context

The release 0.3 managed process documentation was adopted and a point-in-time
audit identified seven remediation phases. The repository had no requirements
index, prompt records, ADR process, project definition, or roadmap. This
requirement establishes that governance baseline before technical migration.

The audit is recorded at
`project/reviews/2026-08-04-standardsAudit.md`. Phase 0 removed inappropriate
scaffold output and established a reproducible 278-test baseline.

## Scope

- Define the project purpose, audience, scope, risks, and migration milestones.
- Create the requirements index, template, durable prompt, and agent adapters.
- Create the ADR index and record decisions needed before technical migration.
- Create a roadmap that sequences the audited remediation phases.
- Make governance and review records discoverable from the root README.
- Record this Phase 1 agent run and verification evidence.

## Out of scope

- Retrospectively inventing requirements for historical implementation.
- Implementing packaging, CLI, filesystem, refactoring, coverage, or final
  documentation-remediation work from Phases 2–7.
- Approving proposed ADRs whose product or safety trade-offs still need
  stakeholder agreement.
- Changing runtime application behaviour.

## Acceptance criteria

1. Given the managed requirements guide, when governance files are inspected,
   then a numbered index, approved template, stable feature record, durable
   prompt, and Codex/Copilot adapters exist at the prescribed paths.
2. Given the standards audit, when the roadmap and project definition are
   inspected, then every remediation phase, current status, principal risk,
   and next dependency is represented without inventing historical records.
3. Given the consequential layout, CLI-compatibility, and file-safety choices,
   when ADR records are inspected, then each has a permanent identifier,
   explicit status, alternatives, consequences, and a link to this requirement.
4. Given the root README, when a maintainer looks for governance information,
   then the requirements index, ADR index, roadmap, and reviews index are
   directly discoverable.
5. Given completion of Phase 1, when verification is run, then all existing
   tests pass, managed links resolve, index statuses agree, and the Git diff has
   no whitespace errors.

## Dependencies and decisions

- [Standards adoption audit](../../reviews/2026-08-04-standardsAudit.md)
- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-002: Migrate the CLI with compatibility](../../adr/002-cliCompatibility.md)
- [ADR-003: Centralise filesystem safety](../../adr/003-filesystemSafetyBoundary.md)

## Verification

- `pytest -q` — 278 tests passed on 2026-08-04.
- `git diff --check` — passed on 2026-08-04.
- A local link and index consistency check covers every governance Markdown
  link introduced by this requirement.
- Manual review confirms the roadmap maps Phases 0–7 from the audit and does
  not create retrospective requirements.

## Traceability

- Implementation: `project/project.yaml`, `project/requirements/`,
  `project/adr/`, `project/roadmap.md`, and `project/reviews/README.md`
- Tests: existing suite in `tests/test_OrganiseMyVideo.py`; no runtime behaviour changed
- Documentation: root `README.md` documentation index
- Pull request: pending
- Agent runs: 2026-08-04 — Codex, implementation and verification, current
  branch `chore/adopt-process-standards`

## Change history

- 2026-08-04: created and completed — implemented Phase 1 of the approved
  standards-adoption roadmap from the repository audit.
