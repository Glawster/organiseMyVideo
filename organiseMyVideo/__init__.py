"""organiseMyVideo — video-file organiser package.

Public surface
--------------
``VideoOrganizer``   The main class.  Assembles :class:`~organiseMyVideo.video.VideoMixin`,
                     :class:`~organiseMyVideo.torrent.TorrentMixin`, via
                     multiple inheritance.

Imagine generation, listing, and download live in :mod:`organiseMyVideo.grok`
as a Python service. The ``grok`` CLI command handles the Firefox-backed Grok
gallery workflow. Camera-card inventory lives in
:mod:`organiseMyVideo.cameraInventory` and is exposed as ``camera inventory``.
None of these concerns is mixed into :class:`VideoOrganizer`.
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
from .filesystemOperations import FilesystemOperations
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
        useCurses: bool = True,
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
        self.filesystem = FilesystemOperations(dryRun=dryRun)
        self.stateFilesystem = FilesystemOperations(dryRun=False)
        self.refreshMetadataLibrary = refreshMetadataLibrary
        self.useCurses = useCurses
        self._promptHelpDisplayed = False
        self._promptDecisionCache = {}
        self._moveProgressDisplayWidth = 0
        self._metadataLibraryCache = None
        self._metadataLibraryLoadState = "missing"
        self._metadataMovieLogStarted = False
        self._metadataShowLogStarted = False
        self._tvMetadataFetcher = None
        self._movieMetadataFetcher = None
        self.tvdbApiKeyPrompt = None
        self._tvdbApiKeyPromptAttempted = False
        self.summaryReportPath = None
        self.summaryReportMode = None
        self._summaryTransfers = []
        self._summaryRenames = []
        self._summaryCleanupTasks = []
        self._summaryDuplicateTvShows = []
        self._resetIgnoredDuplicateTvShowGroups = None
