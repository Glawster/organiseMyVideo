# Unified media locate implementation

Implement [REQ-038](../features/038-movieLocate.md) as `media locate SEARCH`.
Search movie and TV catalogue rows together; remove the public `--movie` and
`--show` selectors, require one search term, rank exact matches before partial
matches, include movie years, identify each result as `Movie` or `TV`, and
preserve current/stale/unverified visibility. Update CLI help, README/docs and
regression tests. Verify the public CLI against a temporary mixed movie/TV
catalogue. Do not rescan or modify media.
