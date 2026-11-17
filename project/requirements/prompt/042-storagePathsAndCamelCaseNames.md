# Storage paths and camelCase names implementation

Implement [REQ-042](../features/042-storagePathsAndCamelCaseNames.md). The
requirement is authoritative for scope, exclusions and all acceptance criteria.

Deliver the storage path changes first, because the hard-coded `By Date` folder
affects the next SLR import. The standard is `<root>/YYYY/MM/<original filename>`, and camera folders keep
`YYYY/MM/DD`. Keep the config rename backwards compatible: existing
snake_case keys must keep working until OMV next saves that value. Do not edit the
owner's `config.json`, move media or change public CLI flag spellings.

Read and write config through one shared lookup rather than repeating key fallbacks
in `video.py`, `videoRescan.py` and `mainLegacy.py`. Check each snake_case name
against its source before renaming it, because fields from external packages and
provider responses must keep their spelling.

The documentation already describes the target layout. Follow the master and root
terms in `organiseMediaStudio/documentation/mediaLibraryOrganisation.md`. Update CLI
help, remove the pending REQ-042 notes from `README.md` and
`documentation/cameraImport.md`, change the config example there to the new key
names, and add regression tests using temporary config
files and trees. Verify with `python -m pytest`, `runLinter` and
`manageProject check`. Hand off with evidence for each acceptance criterion. Any
confirmed run on real media needs the owner's approval.
