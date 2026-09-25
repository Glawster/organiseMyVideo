# Current increment

## Objective

Resolve the requirement-link and status failures reported by `manageProject --check`
on `integrate/camera-foundation`.

## Scope

- Align requirement links, headings, prompt references and IDs with canonical files.
- Repair the malformed index row and align lifecycle statuses with requirement records.
- Restore the camera-history reconciliation requirement and prompt from Git history
  as REQ-028, resolving the merged collision with REQ-027 SLR card import.
- Advance the next available requirement ID to 029 and complete prompt navigation.

## Status

Complete. The project check reports zero failures and zero warnings.

## Verification

- `manageProject --check`: passed.
- `git diff --check`: passed.
- Changes affect documentation and requirement metadata only; pytest was not rerun.

## Immediate next action

Review the documentation changes. No reported check failures remain.
