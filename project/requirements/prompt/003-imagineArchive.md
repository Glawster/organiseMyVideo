# Requirement: 003 — project/requirements/features/003-imagineArchive.md

Role: implement and verify

Read the authoritative requirement, ADR-005, and repository instructions
before changing anything. Deliver acceptance criteria 1–8 only.

Replace the inactive grok.com scraper with an official xAI Imagine API client
that always persists outputs through `storage_options`. Wire CLI subcommands:

```text
python -m organiseMyVideo grok generate "prompt"
python -m organiseMyVideo grok generate "prompt" --kind video
python -m organiseMyVideo grok list
python -m organiseMyVideo grok download --confirm
```

Keep `python -m organiseMyVideo` as the entry point. Do not call live xAI APIs
from tests; inject a fake client. Gallery download via `--grok` is a separate
path for media already created on grok.com.

Verify with:

- `pytest tests/test_grok.py tests/test_organiseMyVideo.py -q`
- `git diff --check`

Handoff with files changed, acceptance-criterion-to-evidence mapping, commands
run, and unresolved items.
