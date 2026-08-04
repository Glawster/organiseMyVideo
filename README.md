# organiseMyVideo

Moves video files from a staging directory to organised storage locations and can also clean torrent downloads.

- **Movies** → `/mnt/movie<n>/Title (Year)/`
- **TV shows** → `/mnt/video<n>/TV/Show Name/Season NN/` (`The Name` folders are stored as `Name, The`)
- **Default staging/source folder** → `/mnt/video2/toFile`
- **Torrent download folder** → sibling `Downloads` folder next to the source directory, e.g. `/mnt/video2/Downloads`

---

## Usage

### Organise video files

```bash
python organiseMyVideo.py
python organiseMyVideo.py --source /path/to/staging
python organiseMyVideo.py --source /path/to/staging --confirm
python organiseMyVideo.py --source /path/to/staging --auto --confirm
python organiseMyVideo.py --rescan --confirm
python organiseMyVideo.py --debug
```

By default the script runs in **dry-run** mode. Add `--confirm` to actually make changes.

### Clean source-folder names and remove empty folders

```bash
python organiseMyVideo.py --clean
python organiseMyVideo.py --clean --confirm
```

`--clean` by itself works on the video source folder:

- cleans source-folder names
- removes empty subfolders
- treats folders with only sample content as empty

### Clean torrent downloads

```bash
python organiseMyVideo.py --torrent
python organiseMyVideo.py --torrent --clean
python organiseMyVideo.py --torrent --clean --confirm
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
| `--non-interactive` | Skip prompts for files that cannot be auto-detected |
| `--refresh` | Rebuild the saved metadata library from storage before processing files |
| `--rescan` | Scan existing TV library files and rename episodes whose filename title still looks like release noise; when run interactively it can also prompt to merge duplicate show folders and choose the master folder |
| `--no-curses` | Use line-based prompts instead of the default curses single-key menus |
| `--torrent` | Run torrent cleanup against the `Downloads` folder that sits next to the source directory |
| `--debug` | Enable debug logging, including TVDB title payload debug lines |

The metadata library is saved in `~/.config/organiseMyVideo/metadataLibrary.json` and reused on later runs. Use `--refresh` when you want to rescan the existing movie and TV storage roots and rebuild that cache.

`--auto` reuses the normal organiser logic without prompts and appends a plain-text summary in `~/.config/organiseMyVideo/summary.yyyymmdd.txt`, including whether each entry was a dry-run or an actual run plus any file moves, renames, cleanup tasks, and possible duplicate TV show folders found that day.

`--rescan` scans the existing TV library roots, normalises retitled episodes to the newer space-style show/title fragments, capitalises lowercase TV show folders when needed, and only falls back to scraper lookups when the current filename suffix still looks like release noise or is missing. It also warns when multiple show folders share the same stored SeriesID so likely duplicates are easier to spot, and interactive runs can prompt to merge those duplicate folders while choosing which one remains the master. If you answer that a prompted group is not a duplicate, that choice is saved in `~/.config/organiseMyVideo/config.json` and future runs suppress the same warning. When an episode is retitled, matching same-stem `.xml` and `.jpg` companion files are renamed with it. Console output is otherwise limited to `rescanning: ...` lines plus any actual rescan rename lines.

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

By default, the main menu choices (`y`, `n`, `t`, `m`, `q`, and Enter to confirm) are handled as single key presses with curses. Text entry prompts such as rename, show title, movie title, season, and year still use normal line input. Use `--no-curses` to fall back to line-based menu prompts.

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

```bash
pip install -r requirements.txt
```

Python 3.10+ required.
