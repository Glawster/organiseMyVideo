"""organiseMyVideo — video-file organiser package.

Public surface
--------------
``VideoOrganizer``   The main class.  Assembles :class:`~organiseMyVideo.video.VideoMixin`,
                     :class:`~organiseMyVideo.torrent.TorrentMixin`, via
                     multiple inheritance.

The retained Grok code lives in :mod:`organiseMyVideo.grok`, but it is no
longer wired into the main application package or CLI.
"""

import shutil  # re-exported so patch("organiseMyVideo.shutil.move") still works in tests
from pathlib import (
    Path,
)  # re-exported so patch("organiseMyVideo.Path") still works in tests

from organiseMyProjects.logUtils import getLogger, setApplication  # type: ignore

thisApplication = Path(__file__).parent.name
setApplication(thisApplication)

from .constants import (
    VIDEO_EXTENSIONS,
    METADATA_LIBRARY_FILE,
    TVDB_API_BASE_URL,
    PREFIX_PATTERNS,
    _PREFIX_REGEX,
)
from .metadata import MetadataMixin
from .torrent import TorrentMixin
from .video import VideoMixin

logger = getLogger()


class VideoOrganizer(MetadataMixin, VideoMixin, TorrentMixin):
    """Organise video files into structured movie and TV show directories.

    Combines all domain-specific mixins into a single class:

    * :class:`~organiseMyVideo.video.VideoMixin` — parse filenames, move files,
      clean names and empty folders.
    * :class:`~organiseMyVideo.torrent.TorrentMixin` — remove stale torrent files
      and clean torrent-site name prefixes.
    """

    def __init__(
        self,
        sourceDir: str = "/mnt/video2/toFile",
        dryRun: bool = True,
        refreshMetadataLibrary: bool = False,
        useCurses: bool = False,
    ):
        """Initialise the video organizer.

        Args:
            sourceDir: Source directory containing files to organise.
            dryRun: If ``True``, show what would be done without making changes.
            refreshMetadataLibrary: Rebuild the saved metadata library from
                storage before processing files.
            useCurses: Use curses-based single-key prompts when interactive.
        """
        self.sourceDir = Path(sourceDir)
        self.dryRun = dryRun
        self.refreshMetadataLibrary = refreshMetadataLibrary
        self.useCurses = useCurses
        self._promptHelpDisplayed = False
        self._promptDecisionCache = {}
        self._metadataLibraryCache = None
        self._metadataMovieLogStarted = False
        self._metadataShowLogStarted = False
        self._tvMetadataFetcher = None
