"""Module-level constants shared across all organiseMyVideo sub-modules."""

import re
from pathlib import Path

# Video file extensions to process
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg"}
GROK_MEDIA_EXTENSIONS = {".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
GROK_USER_CONTENT_DOMAINS = {"imagine-public.x.ai", "images-public.x.ai"}
GROK_CREDENTIALS_FILE = Path.home() / ".config" / "organiseMyVideo" / "grokCredentials.json"

# Browser launch arguments that suppress Playwright's automation fingerprint.
# Without these, X.ai's sign-in page detects the automated browser and returns
# 403 on background API calls before the user can log in.
_PLAYWRIGHT_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
# Realistic Chrome user-agent used for all Playwright contexts.  Playwright's
# default headless UA contains "HeadlessChrome" which bot-detection heuristics
# flag immediately.
_PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
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
