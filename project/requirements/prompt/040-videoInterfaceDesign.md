# 040: Video interface design and implementation prompt

## Assignment

Refine, design and implement [REQ-040](../features/040-videoInterfaceDesign.md).
Coordinate with OMS REQ-012 for dispatch, provider/configuration and lifecycle
integration. Existing OMV REQ-002 remains the initial Qt browsing slice.

## Delivery sequence and boundaries

Deliver annotated Qt/TUI designs, the MCM functional coverage matrix and the
worker/provider decisions first. Implement the real catalogue-backed local
browser, package both providers and verify actual OMS launches. Continue in
explicitly scoped management/compatibility slices with working service adapters.
OMV owns SQLite queries, screens, job execution, confirmations, recovery,
MCM metadata/artwork formats and Wine path mapping; OMS owns generic media and
settings services plus Studio launch integration. Keep every existing CLI
workflow usable without the new optional interfaces, Wine or MCM.

## Verification and handoff

Use synthetic media, temporary catalogues/configs and real Qt/TUI-to-service
paths. Exercise installed OMS/OMV launches, config/exit/interruption handling,
headless installs, read-only browsing, stale plans and recoverable failures.
Inspect official MCM references and use a disposable library for actual Wine
round trips, recording versions and observed limitations; do not claim support
from UI similarity or unavailable tests. Run the OMV suite, required lint/project
and diff checks. Report criterion-level evidence, matrix parity, dependency
revisions and deferred slices. Keep transient status in currentIncrement.md.
