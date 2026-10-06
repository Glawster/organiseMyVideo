"""Pure incoming release-name and ancillary-media classification rules."""

import re
from pathlib import Path

from .constants import _PREFIX_REGEX

_SAMPLE_TOKEN = re.compile(r"(?:^|[\s._-])sample(?:$|[\s._-])", re.IGNORECASE)
_MULTIPART_TOKEN = re.compile(r"(?:[\s._-])part[\s._-]*(\d+)$", re.IGNORECASE)
_DOWNLOADED_FROM_TEXT = re.compile(r"^downloaded\s+from\b", re.IGNORECASE)
_RELEASE_MARKERS = {"rarbg.com", "rarbg", "www.rarbg.com"}


def incomingNameNormalise(name: str) -> str:
    """Return the established prefix cleanup without inspecting the filesystem."""
    if not _PREFIX_REGEX.match(name):
        return name
    return _PREFIX_REGEX.sub("", name, count=1).strip()


def mediaNameIsAncillary(name: str) -> bool:
    """Recognise bounded sample tokens and explicit release-marker filenames."""
    return bool(_SAMPLE_TOKEN.search(Path(name).stem)) or (
        Path(name).stem.casefold() in _RELEASE_MARKERS
    )


def mediaNameIsDisposableJunk(name: str) -> bool:
    """Return True for known release-note files that add no library value."""
    path = Path(name)
    return path.suffix.casefold() == ".txt" and bool(
        _DOWNLOADED_FROM_TEXT.match(path.stem.strip())
    )


def mediaNameIsSample(name: str) -> bool:
    """Recognise sample folder names without matching words such as resampled."""
    return bool(_SAMPLE_TOKEN.search(name))


def mediaNameMultipartSuffix(name: str) -> str:
    """Return a stable part suffix so another part cannot take part one's name."""
    match = _MULTIPART_TOKEN.search(Path(name).stem)
    return f"-part{int(match.group(1))}" if match else ""
