# organiseMyVideo

Moves video files from a staging directory to organised storage locations and can also clean torrent downloads.

- **Movies** → `/mnt/movie<n>/Title (Year)/`
- **TV shows** → `/mnt/video<n>/TV/Show Name/Season NN/`
- **Default staging/source folder** → `/mnt/video2/toFile`
- **Torrent download folder** → sibling `Downloads` folder next to the source directory, e.g. `/mnt/video2/Downloads`

---

## Usage

### Organise video files

```bash
python organiseMyVideo.py
python organiseMyVideo.py --source /path/to/staging
python organiseMyVideo.py --source /path/to/staging --confirm
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
| `--clean` | Clean the source directory, or when combined with `--torrent`, also clean prefixed `.torrent` names |
| `--non-interactive` | Skip prompts for files that cannot be auto-detected |
| `--torrent` | Run torrent cleanup against the `Downloads` folder that sits next to the source directory |

---

## Interactive prompts

When processing each file the tool shows the detected name and asks for confirmation.

### Main confirmation prompt

```
TV Show detected: 'Breaking Bad'
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
