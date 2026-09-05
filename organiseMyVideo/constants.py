"""Module-level constants shared across all organiseMyVideo sub-modules."""

import os
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
MUSIC_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}
MUSIC_FOLDER_NAMES = {"music"}
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
GROK_IMAGE_MODEL = "grok-imagine-image-2.0"
GROK_VIDEO_MODEL = "grok-imagine-video-1.5"
GROK_CATALOG_FILE = Path.home() / ".config" / "organiseMyVideo" / "grokCatalog.json"
GROK_DOWNLOAD_DIR = Path.home() / "Downloads" / "Grok"
GROK_USER_CONTENT_DOMAINS = {"imagine-public.x.ai", "images-public.x.ai"}
GROK_CREDENTIALS_FILE = (
    Path.home() / ".config" / "organiseMyVideo" / "grokCredentials.json"
)
GROK_SESSION_FILE = Path.home() / ".config" / "organiseMyVideo" / "grokSession.json"
_PLAYWRIGHT_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
_GROK_SAVED_URL = "https://grok.com/imagine/saved"
METADATA_LIBRARY_FILE = (
    Path.home() / ".config" / "organiseMyVideo" / "metadataLibrary.json"
)
APP_CONFIG_FILE = Path.home() / ".config" / "organiseMyVideo" / "config.json"
GROK_VISION_MODEL = "grok-4.6"


def applicationStateDirectory() -> Path:
    """Return the XDG local-state directory for this application."""

    configured = os.environ.get("XDG_STATE_HOME")
    if configured:
        return Path(configured) / "organiseMyVideo"
    return Path.home() / ".local" / "state" / "organiseMyVideo"


MEDIA_CATALOGUE_DATABASE = applicationStateDirectory() / "mediaCatalogue.sqlite"
CAMERA_INVENTORY_DATABASE = MEDIA_CATALOGUE_DATABASE
CAMERA_CARD_LABEL_PREFIX = "organiseMyVideo."
CAMERA_CARD_LABEL_LEGACY_FILENAME = "organiseMyVideo.cardId"


def cameraCardLabelFilename(cardId: int) -> str:
    """Return ``organiseMyVideo.001`` for card ID 1."""

    if isinstance(cardId, bool) or not isinstance(cardId, int) or cardId < 1:
        raise ValueError("card ID must be a positive integer")
    return f"{CAMERA_CARD_LABEL_PREFIX}{cardId:03d}"


TVDB_API_BASE_URL = "https://api4.thetvdb.com/v4"
TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/original"

# Known torrent/index prefixes to strip from file and directory names
PREFIX_PATTERNS = [
    r"^\s*www\.UIndex\.org\s*-\s*",
    r"^\s*www\.Torrenting\.com\s*-\s*",
]

# Compiled regex combining all known prefixes (built once at module load)
_PREFIX_REGEX = re.compile("|".join(PREFIX_PATTERNS), re.IGNORECASE)
