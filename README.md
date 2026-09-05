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
- [Media catalogue](documentation/mediaCatalogue.md)
- [Home video archive](documentation/homeVideo.md)
- [Command-line interface](documentation/commandLineInterface.md)

- **Movies** → `/mnt/movie<n>/Title (Year)/`
- **TV shows** → `/mnt/video<n>/TV/Show Name/Season NN/` (`The Name` folders are stored as `Name, The`)
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
organiseMyVideo media clean /path/to/staging
organiseMyVideo library rescan /path/to/staging --target movies
organiseMyVideo torrent maintain /path/to/staging --clean-names
organiseMyVideo grok --import-firefox --confirm
organiseMyVideo grok --scan --confirm
organiseMyVideo grok --reset --confirm
organiseMyVideo camera inventory /media/card --card 12
organiseMyVideo camera inventory /media/card --card 12 --confirm
organiseMyVideo camera inventory --card 12
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
| `grok --scan` | Scan and download your generated Imagine media to `~/Downloads/Grok` |
| `grok --reset` | Quarantine saved grok.com session files so the next scan logs in again |

### Download generated grok.com Imagine media

This retrieves **your** Imagine library (workspace assets and Imagine
conversations). It does not download the public explore feed.

```bash
# 1. Log into grok.com in Firefox
organiseMyVideo grok --import-firefox --confirm
# 2. Download your generated images and videos into ~/Downloads/Grok
organiseMyVideo grok --scan
organiseMyVideo grok --scan --confirm
# Reset the saved session when required
organiseMyVideo grok --reset --confirm
```

Dry-run is the default. Exactly one Grok action is required per invocation.

The metadata library is saved in `~/.config/organiseMyVideo/metadataLibrary.json` and reused on later runs. Use `--refresh` when you want to rescan the existing movie and TV storage roots and rebuild that cache.

`--auto` reuses the normal organiser logic without prompts and appends a plain-text summary in `~/.config/organiseMyVideo/summary.yyyymmdd.txt`, including whether each entry was a dry-run or an actual run plus any file moves, renames, cleanup tasks, and possible duplicate TV show folders found that day.

`--rescan` scans the existing movie and TV library roots. Use `--rescan --movie` when you only need movie metadata/name repair, and `--rescan --video` when you only need the TV episode pass. For movies it refreshes or creates MCM-style `movie.xml` and `mcm_id__*.dvdid.xml` files when metadata is available, fetches missing artwork from configured providers, and renames stored movie files/folders to the canonical `Title (Year)` shape when safe. For TV it normalises retitled episodes to the newer space-style show/title fragments, capitalises lowercase TV show folders when needed, and only falls back to scraper lookups when the current filename suffix still looks like release noise or is missing. It also warns when multiple show folders share the same stored SeriesID so likely duplicates are easier to spot, and interactive runs can prompt to merge those duplicate folders while choosing which one remains the master. If you answer that a prompted group is not a duplicate, that choice is saved in `~/.config/organiseMyVideo/config.json` and future runs suppress the same warning. When an episode is retitled, matching same-stem `.xml` and `.jpg` companion files are renamed with it. Console output is otherwise limited to `rescanning: ...` lines plus any actual rescan rename lines.

---

## Interactive prompts

When processing each file the tool shows the detected name and asks for confirmation.

### Main confirmation prompt

```
TV Show detected: 'Breaking Bad'
Episode Title: Pilot
Is this correct?  (y/n/q/t/m or enter new name):
```

| Input | Action |
|-------|--------|
| `y` / `yes` / Enter | Accept the detected name and move the file |
| `n` / `no` | Open the rename sub-prompt |
| `q` / `quit` | Exit the program |
| `t` | Switch type to **TV show** and prompt for show name |
| `m` | Switch type to **Movie** and prompt for title |
| Any other text | Use that text as the name directly |

The main menu choices (`y`, `n`, `t`, `m`, `q`, and Enter to confirm) are
handled as single key presses with curses. Text entry prompts such as rename,
show title, movie title, season, and year use normal line input. Use `--auto`
for unattended organisation.

### Rename sub-prompt

```
Enter new name (blank for default, enter 'quit' to skip):
```

| Input | Action |
|-------|--------|
| Enter (empty) | Use the default detected name |
| Whitespace only | Use the default detected name |
| `quit` | Skip this file and leave it in staging |
| Any other text | Use that text as the new name |

---

## Requirements

Python 3.10 or newer and Conda are required for the primary development setup.

### Conda development environment

```bash
conda env create -f environment.yml
conda activate application
```

The environment installs this repository in editable mode with its development
extra. If the environment already exists, refresh the editable installation:

```bash
python -m pip install -e ".[dev]"
```

`pyproject.toml` is the authoritative package and dependency definition.
`requirements.txt` and `dev-requirements.txt` are retained as compatibility
exports for tools that still consume requirements files.

### Running the installed command

Both supported entry points call `organiseMyVideo.__main__:main`:

```bash
python -m organiseMyVideo --help
organiseMyVideo --help
```
