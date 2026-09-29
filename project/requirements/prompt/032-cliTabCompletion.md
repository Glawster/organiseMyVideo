# Implement REQ-032: Application-wide CLI Tab completion

## Governing requirement

Implement [REQ-032](../features/032-cliTabCompletion.md). Read repository agent
instructions and the requirements, layout and testing process guides first.
The requirement is authoritative; this prompt does not redefine its scope.

## Preparation and design

- Inspect all public parsers, dispatchers, installed/module entry points and
  initialisation side effects before choosing an integration mechanism.
- Produce the complete argument/provider matrix required by REQ-032.
- Review the linked CLI, packaging, catalogue and camera requirements and ADRs.
- Evaluate parser-integrated completion options and record the architectural
  decision, including safe early completion entry and Bash activation.
- Keep source-folder filename completion conditional on an existing supported
  command; do not implement folder capture-time correction as part of this work.

## Implementation boundaries

Keep shared completion providers and shell adaptation in the application
package. Reuse read-only catalogue/history interfaces where safe, and avoid
workflow dispatch, implicit state creation, media processing or network access.
Preserve normal CLI behaviour and parser ownership of commands and choices.
Keep dependencies in `pyproject.toml` and align compatibility exports if changed.

## Acceptance and handoff

Cover every acceptance criterion with provider tests, real installed-command
Bash integration, mutation sentinels, failure/cancellation cases and a measured
latency benchmark. Run the full relevant suite and repository checks. Update
user activation/removal instructions, argument coverage matrix, requirement
lifecycle metadata and current increment according to the repository process.
Report supported shells/invocations, tests, measured latency, known limitations
and any pre-existing check failures. Do not claim untested shell support.
