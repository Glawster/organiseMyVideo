Requirement: 002 — project/requirements/features/002-qtMediaLibraryBrowser.md
Role: refine and design

Read the authoritative requirement, ADR-001, proposed ADR-004, the standards
audit, and all applicable repository instructions before changing anything.
Resolve the requirement's open product questions with the stakeholder and turn
each agreed answer into observable acceptance criteria or an explicit
exclusion. Do not start GUI implementation while material questions or ADR-004
remain unresolved.

Inspect the named `organiseAIMediaStudio` branch/commit supplied by the
stakeholder. Report concrete processing modules, supported formats, data
contracts, dependencies, and tests. Do not assume that its React/FastAPI starter
implements audio, audiobook, or ebook processing and do not introduce a runtime
dependency on a sibling checkout.

Use Media Center Master's official overview, feature comparison, and screenshot
gallery only as functional design references. Produce original project styling
and assets; do not copy proprietary UI assets or expand scope into downloads,
metadata editing, or playback.

Limit changes during refinement to requirement, ADR, prompt, roadmap, and design
documentation. If refinement produces independently deliverable outcomes,
allocate separate requirements and link them rather than enlarging REQ-002.

Verify the refined documentation with:

- local Markdown-link and requirements-index consistency checks;
- an acceptance-criteria review for normal, empty, loading, and failure states;
- an architecture review proving core library/query behaviour remains
  framework-independent; and
- a traceable `organiseAIMediaStudio` source assessment.

Handoff with:

- decisions made and questions still open;
- requirement/ADR files changed and why;
- acceptance-criterion-to-planned-evidence mapping;
- inspected cross-repository branch/commit and findings; and
- assumptions, risks, and implementation blockers.
