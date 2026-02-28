# organiseMyVideo

A Python script to automatically organize video files from a staging directory into structured movie and TV show libraries.

## Features

- **Automatic Detection**: Parses filenames to detect movies vs TV shows
- **Flexible Storage**: Scans `/mnt/movie<n>` and `/mnt/video<n>` directories for storage locations
- **Smart Organization**: 
  - Movies → `/mnt/movie<n>/Title (Year)/`
  - TV Shows → `/mnt/video<n>/TV/Show Name/Season NN/`
- **User Confirmation**: Interactive prompts when filenames are ambiguous
- **Dry Run Mode**: Safe default — preview changes before executing (use `--confirm` to apply)
- **Space Management**: Automatically selects storage with most free space for new content
- **Comprehensive Logging**: All operations logged to `organiseMyVideo.log`

## File Naming Conventions

### TV Shows
Expected format: `show. SnnEnn.title.ext`
- `show`: Show name (dots or spaces)
- `Snn`: Season number (S01, S02, etc.)
- `Enn`: Episode number (E01, E02, etc.)
- `title`: Episode title
- `ext`: File extension

Example: `The. Office.S02E15.Boys.and.Girls.mkv`

### Movies
Expected formats: 
- `Title (Year).ext`
- `Title.Year.ext`

Example: `The Matrix (1999).mp4`

## Usage

### Basic Usage (Dry Run — default, no changes made)
```bash
python organiseMyVideo.py
```

### Confirm Execution (actually make changes)
```bash
python organiseMyVideo.py --confirm
```

### Custom Source Directory
```bash
python organiseMyVideo.py --source /path/to/files
```

### Non-Interactive Mode
```bash
python organiseMyVideo.py --non-interactive
```

### Set Logging Level
```bash
python organiseMyVideo.py --log-level DEBUG
```

## Requirements

- Python 3.6+
- Standard library only (no external dependencies)

## Installation

1. Clone this repository: 
```bash
git clone https://github.com/Glawster/organiseMyVideo.git
cd organiseMyVideo
```

2. Make the script executable:
```bash
chmod +x organiseMyVideo.py
```

3. Run it:
```bash
./organiseMyVideo.py
```

## Storage Structure

The script expects the following directory structure: 

```
/mnt/
├── video2/
│   └── toFile/          # Source directory (configurable)
├── movie1/              # Movie storage
│   └── Title (Year)/    # Individual movie folders
├── movie2/              # Additional movie storage
├── video1/              # TV storage
│   └── TV/
│       └── Show Name/
│           └── Season 01/
└── video2/              # Additional TV storage
    └── TV/
```

## How It Works

1. **Scan**: Discovers all `/mnt/movie<n>` and `/mnt/video<n>/TV` directories
2. **Parse**: Analyzes filenames to determine content type and metadata
3. **Confirm**:  Prompts user if filename cannot be automatically parsed
4. **Locate**: Searches for existing show/movie directories
5. **Move**: Transfers files to appropriate locations, creating directories as needed

## Examples

### TV Show Processing
```
File: Breaking. Bad.S01E01.Pilot.mkv
Detected:  Breaking Bad, Season 1, Episode 1
Destination: /mnt/video1/TV/Breaking Bad/Season 01/Breaking. Bad.S01E01.Pilot.mkv
```

### Movie Processing
```
File: Inception (2010).mp4
Detected: Inception (2010)
Destination: /mnt/movie1/Inception (2010)/Inception (2010).mp4
```

## Logging

All operations are logged to `organiseMyVideo.log` in the current directory. Log messages follow the format: 
- `...doing something` - action being initiated
- `...something done` - action completed
- Error messages use Sentence Case

## Development

### Code Style
- **Naming**: camelCase for functions/variables, PascalCase for classes
- **Formatting**: Follow PEP 8 guidelines
- **Documentation**: Docstrings for all public functions and classes
- **Type Hints**: Used throughout for better code clarity

### Testing
```bash
# Run tests (when implemented)
pytest
```

## License

MIT License - feel free to use and modify as needed. 