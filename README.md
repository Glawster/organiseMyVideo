# organiseMyVideo

Moves video files from a staging directory to organised storage locations.

- **Movies** → `/mnt/movie<n>/Title (Year)/`
- **TV shows** → `/mnt/video<n>/TV/Show Name/Season NN/`

---

## Usage

```bash
python organiseMyVideo.py --source /path/to/staging \
                          --movieDirs /mnt/movie1 /mnt/movie2 \
                          --videoDirs /mnt/video1 /mnt/video2
```

Add `--confirm` to execute changes (default is dry-run).

---

## Interactive Prompts

When processing each file the tool shows the detected name and asks for confirmation.

### Main confirmation prompt

```
TV Show detected: 'Breaking Bad'
Is this correct?  (y/n/q/t/m or enter new name):
```

| Input | Action |
|-------|--------|
| `y` / `yes` / Enter | Accept the detected name and move the file |
| `n` / `no` | Open the rename sub-prompt (see below) |
| `q` / `quit` | Exit the program |
| `t` | Switch type to **TV show** and prompt for show name |
| `m` | Switch type to **Movie** and prompt for title |
| Any other text | Use that text as the name directly |

### Rename sub-prompt (after pressing `n`)

```
Enter new name (blank for default, enter 'quit' to skip):
```

| Input | Action |
|-------|--------|
| Enter (empty) | Use the default detected name |
| Whitespace only | Use the default detected name |
| `quit` | Skip this file (leave it in staging) |
| Any other text | Use that text as the new name |

---

## Requirements

```bash
pip install -r requirements.txt
```

Python 3.10+ required.
