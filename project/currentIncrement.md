# Current increment

## Objective and scope

Fix targeted TV scan selection so normalized partial filters select physical
folder names and catalogue show titles across storage roots. Preserve all paths
sharing a canonical title and share one selection across duplicate handling and
episode discovery.

## Acceptance work

Retain the unchanged catalogue identity regression and add full-title/partial
selection coverage, unrelated-folder exclusion, Path comparison and one catalogue
read per targeted scan.

## Verification result

- `pytest tests/test_targetedTVCatalogueIdentity.py -vv`: 1 passed; test file
  unchanged and expected stats remain `{"renamed": 0, "skipped": 2, "errors": 0}`.
- `pytest`: 512 passed.
- `git diff --check`: clean.

## Immediate next action

Implementation and verification complete; ready for review.
