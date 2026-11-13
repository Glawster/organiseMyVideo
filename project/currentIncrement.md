# Current increment

## Objective and scope

Deliver REQ-043, removing stale catalogue locations on the following scan and
retiring dropped configured roots, with the REQ-035 correction for hour-only
MCM runtimes, on `bugfix/043-catalogueStaleAndMovieRuntime`. Guard `media clean`
against library stores on `bugfix/036-mediaCleanLibraryGuard`.

## Acceptance and verification

REQ-043 acceptance criteria are covered by `tests/test_catalogueStaleRemoval.py`
and `tests/test_catalogueLocationReconciliation.py`. The runtime correction is
covered by `tests/test_movieIdentitySuspectMetadata.py`.

## Verification still required

Run two library scans on the real catalogue, then confirm the old disk rows have
gone and `media locate` no longer reports them.

## Next

Commit and merge the branch, then complete REQ-043. REQ-042 follows, and REQ-040
remains ToDo.
