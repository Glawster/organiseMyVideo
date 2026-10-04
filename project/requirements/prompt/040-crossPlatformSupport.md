# Requirement: 040 — cross-platform application support

Role: refine, implement, and verify in stages.

Read REQ-007, REQ-022, REQ-029, REQ-035, REQ-036, REQ-037, REQ-040, ADR-003 and ADR-010 together with organiseMediaStudio REQ-007.

Make organiseMyVideo portable across Linux, macOS, and Windows 11 without duplicating generic platform behaviour owned by organiseMediaStudio.

Implement non-destructive workflows first: configured roots, catalogue paths, media scan, lookup, identity/conflict reporting and dry-run planning. Only then enable and verify destructive organise/move/rename workflows, followed by platform-native removable-media discovery.

Preserve non-destructive scan semantics, filesystem safety, collision handling and identity conflict detection. Do not hard-code `/mnt`, drive letters, shell utilities, or package-manager-specific tool paths.

Verify with focused platform tests, the full regression suite, supported OS CI/smoke tests, and `git diff --check`.
