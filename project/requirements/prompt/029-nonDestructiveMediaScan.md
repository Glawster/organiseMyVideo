# 029: Non-destructive media scan — implementation prompt

## Assignment

Implement and verify all acceptance criteria in
[REQ-029](../features/029-nonDestructiveMediaScan.md) on its own feature
branch.

Make `media scan` observational with respect to user-owned media. It may
refresh derived catalogue/application state but must not rename, move, merge,
delete, rewrite embedded metadata, or perform repair writes.

Move reusable repair behaviour to the explicit mutation commands:

- `media organise` for arrangement, rename, move and merge;
- `media clean` for deletion/cleanup.

Keep mutation commands dry-run by default and require `--confirm` before
changes. Preserve `media scan --all`, `media scan --show NAME`, source
resolution and catalogue refresh.

Add regression tests proving that `media scan` cannot invoke media mutation
operations even if a compatibility `--confirm` flag is supplied. Update CLI
documentation to state the command model: **scan = observe, organise = arrange,
clean = remove**.

Verify with `pytest`, `runLinter` and `git diff --check`.
