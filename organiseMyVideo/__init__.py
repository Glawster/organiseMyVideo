"""organiseMyVideo — video-file organiser package.

Public surface
--------------
``VideoOrganizer``   The main class.  Assembles :class:`~organiseMyVideo.video.VideoMixin`,
                     :class:`~organiseMyVideo.torrent.TorrentMixin`, and
                     :class:`~organiseMyVideo.grok.GrokMixin` via multiple inheritance.

All module-level constants (``VIDEO_EXTENSIONS``, ``GROK_SESSION_FILE``, etc.)
are re-exported here so that external code can import them directly from the
top-level package.
"""

import shutil  # re-exported so patch("organiseMyVideo.shutil.move") still works in tests
from pathlib import Path  # re-exported so patch("organiseMyVideo.Path") still works in tests

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import (
    VIDEO_EXTENSIONS,
    GROK_MEDIA_EXTENSIONS,
    GROK_USER_CONTENT_DOMAINS,
    GROK_CREDENTIALS_FILE,
    GROK_SESSION_FILE,
    _PLAYWRIGHT_BROWSER_ARGS,
    _PLAYWRIGHT_USER_AGENT,
    _PLAYWRIGHT_INIT_SCRIPT,
    PREFIX_PATTERNS,
    _PREFIX_REGEX,
)
from .grok import GrokMixin, sync_playwright  # noqa: F401 — re-exported for tests
from .torrent import TorrentMixin
from .video import VideoMixin

logger = getLogger("organiseMyVideo")


class VideoOrganizer(VideoMixin, TorrentMixin, GrokMixin):
    """Organise video files into structured movie and TV show directories.

    Combines all domain-specific mixins into a single class:

    * :class:`~organiseMyVideo.video.VideoMixin` — parse filenames, move files,
      clean names and empty folders.
    * :class:`~organiseMyVideo.torrent.TorrentMixin` — remove stale torrent files
      and clean torrent-site name prefixes.
    * :class:`~organiseMyVideo.grok.GrokMixin` — scrape Grok saved Imagine media,
      import Firefox cookies, manage Grok credentials.
    """

    def __init__(self, sourceDir: str = "/mnt/video2/toFile", dryRun: bool = True):
        """Initialise the video organizer.

        Args:
            sourceDir: Source directory containing files to organise.
            dryRun: If ``True``, show what would be done without making changes.
        """
        self.sourceDir = Path(sourceDir)
        self.dryRun = dryRun
