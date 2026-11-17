# Cross-platform application support implementation

Refine, implement and verify [REQ-045](../features/045-crossPlatformSupport.md)
in the stages it defines. The requirement is authoritative for scope, safety
rules, exclusions and all acceptance criteria.

Read REQ-007, REQ-022, REQ-029, REQ-035, REQ-036, REQ-037, REQ-040, REQ-042,
ADR-003 and ADR-010, together with organiseMediaStudio REQ-007.

Make organiseMyVideo portable across Linux, macOS and Windows 11 without
duplicating generic platform behaviour owned by organiseMediaStudio. Deliver
REQ-042 first, or confirm it is delivered, because it removes the fixed storage
roots.

Implement non-destructive workflows first: configured roots, catalogue paths,
`media scan`, lookup, identity and conflict reporting, and dry-run planning. Only
then enable and verify destructive organise, move and rename workflows, followed
by platform-native removable-media discovery.

Preserve non-destructive scan semantics, filesystem safety, collision handling
and identity-conflict detection. Do not hard-code `/mnt`, drive letters, shell
utilities or package-manager-specific tool paths.

Verify with focused platform tests, the full regression suite, supported OS CI or
smoke tests, `python -m pytest`, `manageProject --check` and `git diff --check`.
