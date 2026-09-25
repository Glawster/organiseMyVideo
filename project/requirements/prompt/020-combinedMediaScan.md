# 020: Combined media scan command — implementation prompt

Role: implement and verify

Add `organiseMyVideo media scan` as the canonical form of the existing combined
movie/TV rescan. Do not split movie and TV in the new command. Resolve the source
from the application config when `--source` is omitted, while allowing
`--source PATH` as a one-run override. Reuse the existing rescan service and
preserve legacy scan interfaces for compatibility. Update help, README, CLI
documentation, and production-path CLI tests.
