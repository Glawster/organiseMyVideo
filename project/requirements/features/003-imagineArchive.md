# 003: Imagine API archive

## Status

Completed

## Outcome

As an operator, I need to generate images and videos through the official xAI
Imagine API, persist them with `storage_options`, then list and download those
stored files so that my Imagine library is retrievable without logging into
grok.com.

## Context

The previous Grok integration scraped `grok.com/imagine/saved` with Playwright
and a Firefox session. That path was removed from the public CLI, left an
inactive `grok.py` module, and cannot retrieve a durable library. The supported
replacement is the xAI Imagine API authenticated with `XAI_API_KEY`. Default
generation URLs are ephemeral; `storage_options` persists each asset in the
Files API so it can be listed and downloaded later.

This requirement covers only assets created through this application. It does
not retrieve media previously created in the grok.com consumer gallery.

## Scope

- CLI commands to generate an image or video with `storage_options` always set.
- CLI commands to list stored Imagine media and download it locally.
- Persist a local catalog of prompt, model, kind, and `file_id` for generated
  assets.
- Authenticate with `XAI_API_KEY`; fail fast when the key is missing.
- Keep generate and download behind `--confirm`; default to dry-run.
- Keep the existing organiser flags working.

## Out of scope

- Image editing, video extension, public URL sharing, and bulk delete.
- A desktop gallery UI.
- Replacing `--grok` saved-gallery download; that remains the path for media
  already created on grok.com.

## Acceptance criteria

1. Given `XAI_API_KEY` is unset, when `python -m organiseMyVideo grok generate`
   runs, then the command fails fast without calling the Imagine API.
2. Given dry-run (no `--confirm`), when generate or download is requested, then
   no API generation, catalog write, or local file write occurs.
3. Given `--confirm` and a prompt, when `grok generate` runs, then the Imagine
   API is called with `storage_options.filename` set and the returned `file_id`
   is recorded in the local catalog.
4. Given `--confirm` and `--kind video`, when `grok generate` runs, then the
   video model is used and the result is persisted with `storage_options`.
5. Given stored Files API media, when `grok list` runs, then image and video
   files are listed and non-media files are omitted.
6. Given `--confirm`, when `grok download` runs, then stored media is written
   under the configured download directory and existing files are skipped.
7. Given `python -m organiseMyVideo --help`, when help is shown, then the
   `grok` API subcommand remains discoverable.

`--grok` gallery download was restored separately: it is the path for media
already created on grok.com.


## Dependencies and decisions

- [ADR-001: Preserve the packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-005: Use the official Imagine API with storage_options](../../adr/005-imagineApiStorage.md)
- [ADR-002](../../adr/002-cliCompatibility.md) remains proposed; this
  requirement adds a new `grok` subcommand without removing legacy organiser
  flags.

## Verification

- `pytest tests/test_grok.py tests/test_organiseMyVideo.py -q` — 289 passed on 2026-08-23.
- `git diff --check` — passed on 2026-08-23.

## Traceability

- Implementation: `organiseMyVideo/grok.py`, `organiseMyVideo/__main__.py`,
  `organiseMyVideo/constants.py`
- Tests: `tests/test_grok.py`; existing grok CLI rejection tests in
  `tests/test_organiseMyVideo.py`
- Documentation: `documentation/imagineArchive.md`, `README.md`
- Pull request: pending
- Agent runs: None

## Change history

- 2026-08-23: created — replace inactive grok.com scraping with the official
  Imagine API archive workflow.
