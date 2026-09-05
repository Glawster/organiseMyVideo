# Requirement: 007 — project/requirements/features/007-filesystemSafety.md

Role: implement and verify

Read REQ-007, ADR-003, repository instructions, and the testing process. Create
one Python filesystem-operation boundary and migrate production mutations to
it. Preserve dry-run behavior, reject collisions, use atomic temporary writes,
verify cross-filesystem moves before source removal, and quarantine cleanup
instead of permanently deleting it.

Quarantine belongs on the source filesystem. Content becomes purge-eligible
after 30 days but must not be automatically purged. Application-state writes
remain allowed where their owning workflows already authorize them and must be
classified and atomic.

Use temporary test paths only. Verify focused failure paths, the full suite,
pre-commit, whitespace, and a direct-mutation audit. Do not implement camera
import or a permanent purge command.
