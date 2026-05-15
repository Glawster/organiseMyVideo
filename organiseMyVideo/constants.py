"""Module-level constants shared across all organiseMyVideo sub-modules."""

import re
from pathlib import Path

# Video file extensions to process
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".m4v",
    ".mpg",
    ".mpeg",
}
GROK_MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".webm",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}
GROK_USER_CONTENT_DOMAINS = {"imagine-public.x.ai", "images-public.x.ai"}
GROK_CREDENTIALS_FILE = (
    Path.home() / ".config" / "organiseMyVideo" / "grokCredentials.json"
)
METADATA_LIBRARY_FILE = (
    Path.home() / ".config" / "organiseMyVideo" / "metadataLibrary.json"
)
APP_CONFIG_FILE = Path.home() / ".config" / "organiseMyVideo" / "config.json"
TVDB_API_BASE_URL = "https://api4.thetvdb.com/v4"
TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

# JavaScript snippet injected into every page of every context to remove the
# navigator.webdriver property that Playwright exposes by default.
_PLAYWRIGHT_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
# Playwright storage-state file (cookies + localStorage) persisted after login.
# When this file exists the browser starts already authenticated and no
# username/password interaction is needed.  Delete this file to force a fresh
# login (e.g. after a session expires or credentials change).
GROK_SESSION_FILE = Path.home() / ".config" / "organiseMyVideo" / "grokSession.json"
# URL of the Grok saved-images gallery — used both for navigation and as the
# post-login verification URL.
_GROK_SAVED_URL = "https://grok.com/imagine/saved"

# Known torrent/index prefixes to strip from file and directory names
PREFIX_PATTERNS = [
    r"^\s*www\.UIndex\.org\s*-\s*",
    r"^\s*www\.Torrenting\.com\s*-\s*",
]

# Compiled regex combining all known prefixes (built once at module load)
_PREFIX_REGEX = re.compile("|".join(PREFIX_PATTERNS), re.IGNORECASE)
