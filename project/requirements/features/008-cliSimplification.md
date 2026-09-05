# 008: CLI simplification

## Status

Completed

## Outcome

As a command-line user, I need one concise Grok command and fewer interaction
switches so that the supported invocation is easy to remember and document.

## Context

The Phase 3 compatibility surface exposed overlapping Grok gallery and Imagine
API commands. The operator selected a single option-based Grok interface and
requested removal of two interaction controls.

## Scope

- Remove `--non-interactive` and `--no-curses` from all parser levels.
- Retain `--auto` as the unattended media-organisation mode.
- Expose `grok` with exactly one of `--import-firefox`, `--reset`, or `--scan`.
- Remove the superseded top-level Grok flags and gallery/API CLI forms.
- Keep the official Imagine archive available as a Python service.
- Align help, README, living CLI documentation, and tests.

## Out of scope

- Removing the Imagine archive Python service.
- Changing Grok gallery discovery or download algorithms.
- Changing media prompt implementation.

## Acceptance criteria

1. Given either removed interaction option, parsing fails with status 2.
2. Given `grok` without an action or with multiple actions, parsing fails.
3. Given each supported Grok action, the corresponding gallery workflow runs.
4. Given `media organise --auto`, processing remains unattended.
5. Given public documentation, only the supported Grok CLI syntax is presented.

## Dependencies and decisions

- [REQ-006: Entry-point and CLI architecture](006-cliArchitecture.md)
- No new ADR required.

## Verification

- CLI parser and dispatch tests
- Full `pytest`
- `pre-commit run --all-files`
- `git diff --check`

## Change history

- 2026-09-03: created and started — operator-requested CLI simplification.
- 2026-09-03: completed — parser, dispatch, tests, help, README, and living
  documentation aligned with the selected interface.
