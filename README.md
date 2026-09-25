# organiseMyVideo

Moves video files from a staging directory to organised storage locations and can also clean torrent downloads.

## Documentation

The README is the canonical entry point for repository documentation. The living guides are:

- [Project coding guidelines](documentation/projectGuidelines.md)
- [Master agent instructions](.github/agent-instructions.md)
- [Copilot compatibility instructions](.github/copilot-instructions.md)
- [Repository layout](documentation/repositoryLayout.md)
- [Requirements management](documentation/requirementsManagement.md)
- [Repository-specific agent instructions](.github/additional-instructions.md)
- [Requirements index](project/requirements/requirementsIndex.md)
- [Architecture decisions](project/adr/adrIndex.md)
- [Standards adoption roadmap](project/roadmap.md)
- [Filesystem safety and quarantine](documentation/filesystemSafety.md)
- [Point-in-time reviews](project/reviews/reviewsIndex.md)
- [Imagine API archive](documentation/imagineArchive.md)
- [Camera media import development plan](documentation/cameraImport.md)
- [Camera card inventory](documentation/cameraInventory.md)
- [Removable media user guide](documentation/removableMediaUserGuide.md)
- [Media catalogue](documentation/mediaCatalogue.md)
- [Home video archive](documentation/homeVideo.md)
- [Command-line interface](documentation/commandLineInterface.md)

- **Movies** → `/mnt/movie<n>/Title (Year)/` (`The Title` folders are stored as `Title, The (Year)`; the title stays `The Title`)
- **TV shows** → `/mnt/video<n>/TV/Show Name/Season NN/` (`The Name` folders are stored as `Name, The`; the show title stays `The Name`)
- **Home video** → `/mnt/myVideo/Video/` (GoPro, Drone, tape transfers, and other personal folders)
- **Default staging/source folder** → `/mnt/video2/toFile`
- **Torrent download folder** → sibling `Downloads` folder next to the source directory, e.g. `/mnt/video2/Downloads`

---

## Usage

### Canonical commands

Use the object/action command hierarchy for new invocations:

```bash
organiseMyVideo media organise /path/to/staging
organiseMyVideo media organise /path/to/staging --confirm
organiseMyVideo media organise --merge
organiseMyVideo media organise --merge --confirm
organiseMyVideo media clean /path/to/staging
organiseMyVideo media scan
organiseMyVideo media scan --source /path/to/staging
organiseMyVideo media scan --show Farscape
organiseMyVideo media scan --all
organiseMyVideo library rescan /path/to/staging --target movies
organiseMyVideo torrent maintain /path/to/staging --clean-names
organiseMyVideo grok --import-firefox --confirm
organiseMyVideo grok --scan --confirm
organiseMyVideo grok --reset --confirm

organiseMyVideo camera list
organiseMyVideo camera show --card 12
organiseMyVideo camera scan -s /media/card --card 12
organiseMyVideo camera scan -s /media/card --card 12 --confirm
organiseMyVideo camera archive -s /media/card --card 12
organiseMyVideo camera archive -s /media/card --card 12 --confirm
organiseMyVideo camera history --card 12
organiseMyVideo camera location --card 12
organiseMyVideo camera location --card 12 --set CarBMW
organiseMyVideo camera format --card 12
organiseMyVideo camera format --card 12 --confirm
```

Run `organiseMyVideo --help` or append `--help` at any command level. See the
[command-line interface guide](documentation/commandLineInterface.md) for the
complete syntax and compatibility policy.

### Organise video files

```bash
python -m organiseMyVideo
python -m organiseMyVideo --source /path/to/staging
python -m organiseMyVideo --source /path/to/staging --confirm
python -m organiseMyVideo --source /path/to/staging --auto --confirm
python -m organiseMyVideo --rescan --confirm
python -m organiseMyVideo --debug
```

By default the script runs in **dry-run** mode. Add `--confirm` to actually make changes.

Use `organiseMyVideo media scan` for the normal existing-library scan. It scans
both movie and TV libraries together; there is no movie/video selector on this
canonical command. The normal source comes from the `source` setting in
`~/.config/organiseMyVideo/config.json`; `--source PATH` is an explicit override.
The normal TV scan checks show-level identity metadata and only descends into shows
that need repair. Use `--show NAME` for a focused repair across all TV roots,
matching normalized partial physical folder names or catalogue show titles, and
`--all` for the exhaustive episode-by-episode integrity scan and catalogue refresh.

The `media organise`, `media clean`, `library rescan`, and `torrent maintain`
commands accept a positional source or `-s`/`--source PATH`. An explicit source
option takes precedence when both are supplied.

### Clean source-folder names and remove empty folders

```bash
python -m organiseMyVideo --clean
python -m organiseMyVideo --clean --confirm
```

`--clean` by itself works on the video source folder:

- cleans source-folder names
- removes empty subfolders
- treats folders with only sample content as empty

### Clean torrent downloads

```bash
python -m organiseMyVideo --torrent
python -m organiseMyVideo --torrent --clean
python -m organiseMyVideo --torrent --clean --confirm
```

`--torrent` switches the script to torrent cleanup mode and uses the sibling `Downloads` folder for the current source path.

- `--torrent` deletes `.torrent` files for media already found in the library
- `--torrent --clean` also renames prefixed `.torrent` files such as `www.Torrenting.com - Example.torrent`
- only `.torrent` files are renamed; download directories are **not** renamed
- if a matching `.torrent` file is inside a download subdirectory and the movie/show is already in the library, the whole download folder is deleted

---

## Command-line options

| Option | Description |
|--------|-------------|
| `--source PATH` | Source directory containing files to organize. Default: `/mnt/video2/toFile` |
| `--confirm` | Execute changes. Without this flag the script runs as a dry-run |
| `--auto` | Run organisation without prompts and append the day’s actions to `~/.config/organiseMyVideo/summary.yyyymmdd.txt` |
| `--clean` | Clean the source directory, or when combined with `--torrent`, also clean prefixed `.torrent` names |
| `--refresh` | Rebuild the saved metadata library from storage before processing files |
| `--rescan` | Scan existing movie and TV libraries, repair movie metadata/artwork, canonicalise movie names, and rename TV episodes whose filename title still looks like release noise |
| `--movie` | With `--rescan`, limit repairs to movies |
| `--video` | With `--rescan`, limit repairs to TV/video episodes |
| `--torrent` | Run torrent cleanup against the `Downloads` folder that sits next to the source directory |
| `--debug` | Enable debug logging, including TVDB title payload debug lines |
| `--quiet` | Show errors only |
| `--version` | Display the installed package version |
| `grok --import-firefox` | Import grok.com cookies from Firefox after logging in |
