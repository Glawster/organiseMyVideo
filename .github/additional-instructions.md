# Additional agent instructions for organiseMyVideo

## Project-specific information

This repository contains a Python 3.10+ command-line application that organises
movies, TV episodes, music, and torrent downloads. The shared rules in
`.github/agent-instructions.md` take precedence. Repository layout and
requirements work follow `documentation/repositoryLayout.md` and
`documentation/requirementsManagement.md`.

The existing `organiseMyVideo/` package is this repository's source-package
directory. Keep its root launcher behaviour through `python -m organiseMyVideo`;
do not add a placeholder `main.py` or move the package solely to match the
generic layout example.

## Safety and file operations

- Dry-run is the default. User files may only be changed when `--confirm` is
  supplied.
- Preserve source media when an operation is ambiguous or cannot be completed
  safely.
- Keep path discovery and filesystem mutations testable with temporary paths;
  tests must not depend on the real `/mnt/movie<n>` or `/mnt/video<n>` stores.
- Matching media companion files such as XML metadata and artwork must remain
  aligned when a media file is renamed or moved.

## Development and verification

Install runtime and development dependencies with:

```bash
pip install -r requirements.txt -r dev-requirements.txt
```

Run the test suite with:

```bash
pytest
```

Keep public CLI help and `README.md` aligned whenever options or behaviour
change.
