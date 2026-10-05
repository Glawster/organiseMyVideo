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
- `media clean` for incoming/staging cleanup only.

Keep mutation commands dry-run by default and require `--confirm` before
changes. Preserve `media scan --all`, `media scan --show NAME`, source
resolution and catalogue refresh.

Enforce canonical TV season destinations everywhere media is organised:
`Season N` with no leading zeroes. `S01E02` remains a valid episode filename
representation, but its directory is `Season 1`, never `Season 01`. Existing
padded season directories are scan findings and organise-normalisation
candidates rather than a reason to create more padded folders.

Add media-integrity reporting for zero-byte video files. Any recognised video
extension with size zero must be reported during scan with the path, byte count
and a clear `redownload required`/operator-repair action. Zero-byte source video
must not be moved into the organised library. Do not classify unrelated
zero-byte non-video marker or metadata files as broken media.

Add regression tests proving that `media scan` cannot invoke media mutation
operations even if a compatibility `--confirm` flag is supplied, that TV moves
use unpadded season folders, and that movie/TV zero-byte video files are
reported and refused by organise. Update CLI documentation to state the command
model: **scan = observe, organise = arrange, clean = prepare/clean incoming
media**.

Verify with `pytest`, `runLinter` and `git diff --check`.
