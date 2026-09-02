# ADR-005: Use the official Imagine API with storage_options

## Status

Accepted — 2026-08-23

## Context

Operators want a Python workflow that retrieves Grok-created images and videos.
Two paths exist: scrape the grok.com Imagine gallery with a browser session, or
use the documented xAI Imagine and Files APIs. The repository previously kept
an inactive Playwright scraper and rejected `--grok` on the public CLI.

Default Imagine URLs expire. The Files API can list and download assets only
when generation used `storage_options`.

## Options considered

1. Restore grok.com login scraping and download from the consumer gallery.
2. Use the official Imagine API, always persist with `storage_options`, and
   list/download through the Files API.
3. Keep Grok functionality out of this repository and create a new project.

## Decision

Use option 2 inside `organiseMyVideo` as a `grok` subcommand. Authenticate with
`XAI_API_KEY`. Always pass `storage_options` on generate. Do not scrape
grok.com or store grok.com passwords or session cookies.

This archive contains only assets generated through this application after
persistence is enabled. It does not reconstruct a grok.com gallery.

## Rationale

The Imagine and Files APIs are documented, testable with a fake client, and
safe to dry-run. Browser login scraping is brittle and was already removed
from the public CLI.

## Consequences

- `organiseMyVideo/grok.py` becomes an API client rather than a Playwright
  mixin.
- `xai-sdk` is a runtime dependency for live grok commands; tests inject a
  fake client and must not require a network or API key.
- Existing organiser flags remain the default invocation.
- Media already created on grok.com is out of scope.

## Related requirements

- [REQ-003: Imagine API archive](../requirements/features/003-imagineArchive.md)
