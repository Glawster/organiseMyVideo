# Standards adoption audit — 2026-08-04

## Purpose

Assess `organiseMyVideo` against the shared release 0.3 process and development
standards before implementation work begins. This is a point-in-time review,
not a requirement record or an assertion that all shared conventions should be
applied mechanically to established public interfaces.

## Evidence collected

- Read the complete managed agent, repository-layout, and requirements guides,
  plus the repository-specific instructions and existing project guidelines.
- Ran `createProject --update` as a dry-run and then
  `createProject --update --confirm` to observe actual scaffold behaviour.
- Ran `pytest -q`: 278 tests passed.
- Ran `git diff --check`: no whitespace errors were reported.
- Ran Black in check mode with a 30-second limit. It reported four files that
  would be reformatted before the limit expired: `video.py`, `video_move.py`,
  `video_rescan.py`, and `tests/test_OrganiseMyVideo.py`.
- Attempted the deployed GUI naming linter. It could not start in the sandbox
  because importing `organiseMyProjects` attempts to create a log file under
  `~/.local/state/createProject/` as an import side effect.
- Coverage could not be measured because no coverage tool is declared or
  installed. Passing test count is therefore not evidence of the required
  coverage threshold.
- Inspected repository layout, CLI parsing, logging setup, dependencies,
  filesystem mutations, configuration writes, module/function sizes, public
  docstrings, and type annotations.

## Current strengths

- The primary application is already a package with the supported
  `python -m organiseMyVideo` entry point.
- Destructive media operations default to dry-run and generally guard writes
  behind `self.dryRun` or `--confirm`.
- File-oriented tests use isolated temporary paths rather than real media
  mounts.
- The suite has broad behavioural coverage by test count and currently passes
  all 278 tests.
- Public workflow methods generally have docstrings, and companion metadata
  handling is covered by regression tests.
- User configuration is stored under
  `~/.config/organiseMyVideo/config.json`, consistent with the shared pattern.

## Findings

### 1. Scaffold update is not project-role aware — critical

The confirmed update treated this packaged CLI as a new standalone UI project.
It created a generic root `main.py`, `src/__init__.py`, and an iCloud-oriented
`src/globalVars.py`. These conflict with the real package entry point and are
not appropriate additions to this repository.

It also overwrote project-owned `.env`, `.pre-commit-config.yaml`, and
`pytest.ini`. The generated pytest file uses `[tool:pytest]` in an INI file;
pytest consequently falls back to defaults rather than applying the intended
settings. Managed and project-owned configuration are not sufficiently
distinguished.

The deployed linter files are first overwritten as managed copies and then
checked as project-owned missing-only templates in the same update. That is a
contradictory ownership policy.

### 2. Process traceability is absent — high

There is no `project/requirements/` index, requirement template, feature
record, durable agent prompt, ADR index, or roadmap. Existing work therefore
cannot meet the new requirement-to-implementation/test/documentation
traceability rules. Adoption should begin with one migration requirement; it
should not attempt to reconstruct fictional requirements for all historical
commits.

### 3. Packaging and environments do not meet the standard — high

The repository has no `pyproject.toml` or `environment.yml`, and it declares
only `mutagen` in `requirements.txt` even though the application requires
`organiseMyProjects.logUtils` at runtime. There is no declared console-script
entry point or package version. The generated pre-commit hook assumes a
`runLinter` command but does not declare how the hook environment obtains the
package that provides it.

The `.gitignore` has malformed patterns containing spaces (`. eggs/`,
`*. egg-info/`, `.installed. cfg`, `*. log`, `. coverage`) and does not ignore
the existing `.venv/` spelling.

### 4. Entry-point and logging ownership are inconsistent — high

`organiseMyVideo/__init__.py` calls `setApplication()` during package import.
The standard assigns logging initialization to the application entry point,
and import-time initialization makes library imports produce filesystem side
effects through the upstream logging package. Tests hide the real dependency
behind a module stub, so the production import path is not exercised.

`__main__.py` contains a manual console-handler workaround and directly
formats handlers, indicating the shared logging API is not providing the
required entry-point behaviour cleanly. `rugbyAudit.py` separately uses
standard-library logging and `basicConfig()`, contrary to the shared policy.

### 5. CLI structure and validation are incomplete — high

The primary CLI exposes many unrelated top-level mode flags rather than
subcommands, has no `--version`, `--verbose`, or `--quiet`, and does not make
mutually exclusive modes explicit in the parser. `main()` is approximately
200 lines and mixes parsing, configuration, logging, orchestration, and
summary rendering. Source paths are mostly validated after object creation,
and error-to-exit-code behaviour is not consistently defined.

A subcommand migration must preserve aliases for the documented legacy flags
for an agreed compatibility period; this is a public-interface decision and
should be recorded in an ADR.

### 6. Filesystem safety is distributed — high

Mutations are spread across `video.py`, `video_move.py`, `video_rescan.py`,
`torrent.py`, `metadata.py`, and `__main__.py`. The code uses direct rename,
unlink, `shutil.rmtree`, copying, directory creation, and writes rather than a
central reusable file-operation boundary. Most media changes are dry-run
guarded, but destructive torrent-folder and empty-folder deletion are not
recoverable operations.

Application-state writes during dry-run (metadata cache, saved preferences,
ignored duplicate choices, and summaries) need to be classified explicitly
and documented so they follow the shared exception for preference persistence
without surprising users.

### 7. Module and function size substantially exceed thresholds — medium

The main mixin classes range from 716 to 2,275 lines, with `VideoMixin` itself
spanning about 2,275 lines. Several workflow functions exceed 100 lines, and
the CLI `main()` is about 200 lines. `tests/test_OrganiseMyVideo.py` is 6,692
lines with 277 top-level tests. These sizes make domain ownership, ordering,
and focused verification difficult.

The shared `domainAction` naming convention is not consistently followed.
Changing names mechanically would create unnecessary API churn; naming and
module decomposition should be handled incrementally at touched boundaries,
with compatibility wrappers where public names exist.

### 8. Type, formatting, and verification policy is incomplete — medium

Public workflow methods are documented, but none of the audited package public
functions met a strict fully-annotated signature check. Black reports four
non-conforming files. There is no type checker, coverage dependency, coverage
configuration, or CI evidence enforcing the stated thresholds. Tests do not
mirror the source modules because nearly all behaviour is in one test file.

### 9. Repository layout and documentation need classification — medium

The root contains `rugbyAudit.py` and a real-looking media XML record. The
audit utility should be classified as part of this product, moved under
`scripts/`, or split into its own project boundary. The XML should become a
sanitized fixture under `data/` or `tests/fixtures/`, or be removed if it is
accidental user data.

`documentation/projectGuidelines.md` is a stale GUI-focused guide for a CLI
repository. It references Python 3.9, unavailable root files, manual log
punctuation that conflicts with `logUtils`, and widget rules irrelevant to the
current product. It should be retired or replaced by accurate contributor
guidance rather than retained as a living guide.

The inactive `grok.py` module is intentionally detached from the public
application but remains 880 lines. Its ownership, dependencies, security
surface, and retention should be decided explicitly.

## Upstream `createProject` follow-up

Record a separate requirement in `organiseMyProjects` covering:

1. Make update behaviour project-role aware (library, packaged CLI,
   standalone application, optional UI) and never infer a UI from absence of
   metadata.
2. Keep `--confirm` as the safe execution gate, but document
   `createProject --update --confirm` as the command that applies changes.
3. Make dry-run messages say `would create`/`would update` and finish with an
   unambiguous simulated-update summary.
4. Do not add `main.py`, `src/globalVars.py`, UI templates, or source layout to
   an established packaged CLI unless explicitly requested.
5. Remove product-specific iCloud defaults from shared templates.
6. Treat existing pytest, pre-commit, environment, editor, and dependency
   files as project-owned; create them only when missing or merge narrowly
   through an explicit managed block.
7. Generate valid `[pytest]` INI configuration and test that its settings are
   actually loaded by pytest.
8. Give every deployed file one ownership policy: managed overwrite,
   managed-block merge, or project-owned missing-only.
9. Avoid import-time log-file creation so commands and deployed linters can be
   imported in read-only or sandboxed environments.
10. Add integration fixtures representing an established packaged CLI such as
    this repository and assert that an update is idempotent and preserves its
    entry point, package layout, test discovery, and local configuration.
11. Align scaffold output with the same managed standards: generate
    `pyproject.toml`, `environment.yml`, and requirements/ADR bootstrap when
    applicable, or explicitly document why these remain opt-in.

## Proposed remediation plan

### Phase 0 — establish a safe baseline

- Remove the inappropriate generated `main.py` and `src/` scaffold from this
  packaged CLI.
- Restore or deliberately revise `.env`, `.pre-commit-config.yaml`, and
  `pytest.ini` as project-owned configuration rather than accepting blind
  template replacement.
- Retain the managed process files and the repository-specific package-layout
  exception.
- Verify the existing 278 tests and capture a reproducible baseline.

### Phase 1 — bootstrap governance

- Create the requirements index, approved requirement template, prompt
  adapter(s), ADR index, and roadmap in the prescribed `project/` locations.
- Create one `standardsAdoption` requirement and prompt covering this phased
  migration. Do not backfill invented historical requirements.
- Record ADRs for packaged-CLI layout, CLI compatibility/subcommand migration,
  and the file-operation safety boundary before dependent implementation.

### Phase 2 — make installation and execution reproducible

- Add `pyproject.toml` with Python support, runtime/development dependencies,
  version metadata, package discovery, and a console-script entry point.
- Add `environment.yml`, document Conda-first editable installation, and keep
  requirements files only as deliberate compatibility exports if needed.
- Correct `.gitignore`, secret/config handling, pytest configuration, and
  pre-commit installation so each tool runs in a clean environment.

### Phase 3 — repair entry-point and CLI architecture

- Move all `setApplication()` responsibility to the executable entry point and
  make importing `organiseMyVideo` free of log-file side effects.
- Split parser construction, validation, mode selection, orchestration, and
  summary rendering into focused typed functions.
- Introduce discoverable subcommands with legacy flag aliases and explicit
  deprecation behaviour approved by ADR; add universal options and reliable
  exit statuses.

### Phase 4 — centralize safe filesystem behaviour

- Introduce a tested filesystem-operation service for copy, move, rename,
  create, write, and removal operations with a single dry-run contract.
- Prefer recoverable removal or quarantine for torrent/download cleanup where
  practical, and define cross-device recovery semantics.
- Classify application-state writes that are allowed during dry-run and expose
  them clearly in help and summaries.

### Phase 5 — refactor by domain without changing behaviour

- Decompose the large mixins into metadata providers/cache, media parsing,
  destination planning, transfers, cleanup, rescans, prompts, and reporting.
- Apply type hints, domain-first names, alphabetical section ordering, and
  Black formatting as each boundary is touched.
- Preserve supported public methods through compatibility wrappers until a
  separately agreed breaking change.

### Phase 6 — make verification enforceable

- Split tests to mirror source domains while preserving behavioural coverage.
- Add coverage tooling and establish the measured baseline before enforcing
  the shared >90% core and 100% critical thresholds.
- Add production-import, CLI help/exit-code, dry-run mutation, path validation,
  cross-device transfer, and failure-recovery tests.
- Run Black and the naming linter through reproducible pre-commit and CI jobs.

### Phase 7 — finish layout and documentation adoption

- Decide and document ownership of `rugbyAudit.py`, the root XML artifact, and
  inactive Grok code; move or remove them according to that decision.
- Replace stale GUI guidance with accurate contributor/developer documentation
  and keep the README documentation index complete.
- Record final acceptance evidence in the requirement and update the roadmap,
  ADRs, and living documentation together.

## Recommended sequencing

Phases 0 and 1 should be the next change. Phases 2–4 protect reproducibility,
public CLI behaviour, and user data and therefore precede broad style or
naming work. Phases 5–7 should be delivered as small requirements with
criterion-to-test traceability rather than one repository-wide rewrite.

## Decisions required before implementation

- Whether `rugbyAudit.py` belongs to this product, a maintenance `scripts/`
  area, or a separate project.
- Whether the root XML is sanitized test data or accidental user data.
- How long legacy top-level CLI flags must remain supported after subcommands
  are introduced.
- Whether destructive cleanup should use trash/quarantine, and what retention
  policy applies.
- Whether inactive Grok functionality is retained, moved, or removed.
