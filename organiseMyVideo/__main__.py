#!/usr/bin/env python3
"""Entry point: ``python -m organiseMyVideo``."""

import argparse
import json
import logging
import os
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional, Sequence

from organiseMyProjects.logUtils import drawBox, getLogger, setApplication  # type: ignore

from .constants import APP_CONFIG_FILE
from .filesystemOperations import FilesystemOperations

thisApplication = Path(__file__).parent.name
setApplication(thisApplication)
logger = getLogger(includeConsole=False)

try:
    APP_VERSION = version("organiseMyVideo")
except PackageNotFoundError:
    APP_VERSION = "0.5.0"


def _getAppConfigPath() -> Path:
    """Return the persistent application config file path."""
    return APP_CONFIG_FILE


def _loadAppConfig(configPath: Path) -> dict:
    """Return config data from *configPath*, or an empty dict when unavailable."""
    if not configPath.exists():
        return {}
    try:
        loaded = json.loads(configPath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning("could not read app config %s: %s", configPath, error)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _saveAppConfig(configPath: Path, config: dict) -> None:
    """Write *config* JSON data to *configPath*."""
    FilesystemOperations(dryRun=False).writeText(
        configPath,
        json.dumps(config, indent=2, sort_keys=True),
        encoding="utf-8",
        stateKind="application-state",
    )


def _persistTvdbApiKey(key: str, configPath: Path) -> Optional[str]:
    """Persist a cleaned TVDB API key and return it, or ``None`` when blank."""
    cleaned = key.strip()
    if not cleaned:
        return None
    config = _loadAppConfig(configPath)
    config["tvdb_api_key"] = cleaned
    _saveAppConfig(configPath, config)
    os.environ["ORGANISEMYVIDEO_TVDB_API_KEY"] = cleaned
    logger.value("saved TVDB API key config", configPath)
    return cleaned


def _loadTvdbApiKeyFromConfig(configPath: Path) -> None:
    """Load a saved TVDB API key into the environment when one is not set."""
    if os.environ.get("ORGANISEMYVIDEO_TVDB_API_KEY"):
        return
    config = _loadAppConfig(configPath)
    configured = config.get("tvdb_api_key")
    if isinstance(configured, str) and configured.strip():
        os.environ["ORGANISEMYVIDEO_TVDB_API_KEY"] = configured.strip()


def _promptForTvdbApiKey(configPath: Path) -> Optional[str]:
    """Prompt the user for a TVDB API key and persist it when provided."""
    try:
        entered = input(
            "TVDB API key required for TVDB lookup. Enter key (blank to skip): "
        )
    except EOFError:
        return None
    return _persistTvdbApiKey(entered, configPath)


def _runGrokGalleryCommand(args, gallery, sessionFile: Path) -> None:
    """Run the selected Grok session or gallery operation."""
    if args.reset_grok:
        logger.doing("resetting grok session files")
        resetStats = gallery.resetGrokConfig()
        deletedList = (
            "\n".join(f"  {path}" for path in resetStats["deleted"]) or "  (none)"
        )
        notFoundList = (
            "\n".join(f"  {path}" for path in resetStats["notFound"]) or "  (none)"
        )
        summary = f"""RESET GROK SUMMARY
Deleted:
{deletedList}
Not found:
{notFoundList}
"""
        drawBox(summary)
        return
    if args.import_firefox_session:
        logger.doing("importing grok firefox session")
        ok = gallery.importFirefoxSession()
        if ok:
            summary = (
                f"FIREFOX SESSION IMPORTED\n"
                f"  Session file: {sessionFile}\n\n"
                f"Run 'organiseMyVideo grok --scan --confirm' to download media."
            )
        else:
            summary = (
                "FIREFOX SESSION IMPORT FAILED\n\n"
                "Make sure you are logged into grok.com in Firefox,\n"
                "then run 'organiseMyVideo grok --import-firefox' again."
            )
        drawBox(summary)
        return
    logger.doing("downloading generated grok.com imagine media")
    grokStats = gallery.downloadGeneratedMedia()
    summary = f"""GROK SUMMARY
Generated assets: {grokStats['assetsFound']}
Files handled:    {grokStats['downloaded']}
Already present:  {grokStats['skipped']}
Errors:           {grokStats['errors']}
Session file:     {sessionFile}
  (use 'organiseMyVideo grok --reset --confirm' to force re-login)
"""
    drawBox(summary)


def _getSummaryReportPath(sourcePath: str, mode: str) -> Path:
    """Return the summary-report path for auto/rescan runs."""
    del sourcePath, mode
    return APP_CONFIG_FILE.parent / f"summary.{datetime.now().strftime('%Y%m%d')}.txt"


def _buildSharedFlags(suppressDefaults: bool = False) -> argparse.ArgumentParser:
    """Return flags shared by the organiser and grok subcommands."""
    shared = argparse.ArgumentParser(
        add_help=False,
        argument_default=(argparse.SUPPRESS if suppressDefaults else None),
    )
    shared.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
        help="confirm execution — actually make changes (default is dry-run)",
    )
    shared.add_argument(
        "--debug",
        action="store_true",
        help="enable debug-level logging",
    )
    shared.add_argument("--quiet", action="store_true", help="show errors only")
    return shared


def _sourceArgumentsAdd(
    parser: argparse.ArgumentParser,
    *,
    dest: str = "source",
    default: Optional[str] = "/mnt/video2/toFile",
    helpText: str = "source directory",
) -> None:
    """Add positional SOURCE plus -s/--source alias to one action parser."""
    parser.add_argument(
        dest,
        nargs="?",
        default=default,
        metavar="SOURCE",
        help=helpText,
    )
    parser.add_argument(
        "-s",
        "--source",
        dest=f"{dest}Option",
        metavar="SOURCE",
        help=f"{helpText}; alternative to positional SOURCE",
    )


def _sourceAliasResolve(args: argparse.Namespace, dest: str) -> None:
    """Prefer an explicit -s/--source value over the positional source."""
    optionDest = f"{dest}Option"
    optionValue = getattr(args, optionDest, None)
    if optionValue is not None:
        setattr(args, dest, optionValue)


def buildParser() -> argparse.ArgumentParser:
    """Return the public CLI parser, including the grok subcommand."""
    parser = argparse.ArgumentParser(
        description="Organize video files into movies and TV show directories",
        parents=[_buildSharedFlags()],
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {APP_VERSION}"
    )
    parser.add_argument(
        "-s",
        "--source",
        default="/mnt/video2/toFile",
        help="Source directory containing files to organize (default: /mnt/video2/toFile)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="run without prompts and append a dated text summary in the application directory",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove empty sub-folders from source directory (folders with only sample content are treated as empty)",
    )
    parser.add_argument(
        "--refresh",
        dest="refresh_metadata_library",
        action="store_true",
        help="rebuild the saved metadata library from storage before processing",
    )
    parser.add_argument(
        "--rescan",
        action="store_true",
        help="scan existing movie and TV libraries for metadata and naming fixes",
    )
    parser.add_argument(
        "--movie",
        action="store_true",
        help="with --rescan, limit repairs to movies",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="with --rescan, limit repairs to TV/video episodes",
    )
    parser.add_argument(
        "--torrent",
        action="store_true",
        help="scan the torrent download directory for .torrent files and delete those already in the library (dry-run by default; use --confirm to delete)",
    )
    parser.add_argument(
        "--key",
        help="TVDB API key to save to ~/.config/organiseMyVideo/config.json",
    )
    parser.set_defaults(
        curses=True,
        grok=False,
        import_firefox_session=False,
        reset_grok=False,
    )
    subparsers = parser.add_subparsers(dest="command")
    mediaParser = subparsers.add_parser("media", help="organise or clean staged media")
    mediaSub = mediaParser.add_subparsers(dest="mediaAction", required=True)
    mediaOrganise = mediaSub.add_parser(
        "organise", parents=[_buildSharedFlags(True)], help="organise staged media"
    )
    _sourceArgumentsAdd(mediaOrganise, helpText="staging/source directory")
    mediaOrganise.add_argument("--auto", action="store_true")
    mediaOrganise.add_argument(
        "--refresh", dest="refresh_metadata_library", action="store_true"
    )
    mediaOrganise.add_argument(
        "--merge",
        action="store_true",
        help="merge provider-identified duplicate TV and movie folders into the most complete existing folder",
    )
    mediaClean = mediaSub.add_parser(
        "clean",
        parents=[_buildSharedFlags(True)],
        help="clean staged media names and folders",
    )
    _sourceArgumentsAdd(mediaClean, helpText="staging/source directory")

    libraryParser = subparsers.add_parser("library", help="maintain media libraries")
    librarySub = libraryParser.add_subparsers(dest="libraryAction", required=True)
    libraryRescan = librarySub.add_parser(
        "rescan", parents=[_buildSharedFlags(True)], help="rescan movie and TV metadata"
    )
    _sourceArgumentsAdd(libraryRescan, helpText="staging/source directory")
    libraryRescan.add_argument(
        "--target", choices=("both", "movies", "tv"), default="both"
    )

    torrentParser = subparsers.add_parser("torrent", help="maintain torrent downloads")
    torrentSub = torrentParser.add_subparsers(dest="torrentAction", required=True)
    torrentMaintain = torrentSub.add_parser(
        "maintain",
        parents=[_buildSharedFlags(True)],
        help="remove obsolete torrent files",
    )
    _sourceArgumentsAdd(torrentMaintain, helpText="staging/source directory")
    torrentMaintain.add_argument("--clean-names", action="store_true")

    cameraParser = subparsers.add_parser(
        "camera",
        help="inventory camera SD cards or import camera media",
    )
    cameraSub = cameraParser.add_subparsers(dest="cameraAction", required=True)
    cameraInventory = cameraSub.add_parser(
        "inventory",
        parents=[_buildSharedFlags(True)],
        help="catalogue a numbered camera SD card",
    )
    _sourceArgumentsAdd(
        cameraInventory,
        dest="inventorySource",
        default=None,
        helpText="mounted card or copied card directory",
    )
    cameraInventory.add_argument(
        "--card",
        type=int,
        help="numeric ID assigned to this SD card (required on first scan)",
    )
    cameraInventory.add_argument(
        "--reassign",
        action="store_true",
        help="allow --card to replace an existing on-card ID (requires --confirm)",
    )
    cameraInventory.add_argument(
        "--brand",
        help="SD card brand to store on the card, for example SanDisk",
    )
    grokParser = subparsers.add_parser(
        "grok",
        parents=[_buildSharedFlags(True)],
        help="import a Firefox session, reset it, or scan Grok Imagine media",
    )
    grokActions = grokParser.add_mutually_exclusive_group(required=True)
    grokActions.add_argument(
        "--import-firefox",
        dest="import_firefox_session",
        action="store_true",
        help="import the grok.com session from Firefox",
    )
    grokActions.add_argument(
        "--reset",
        dest="reset_grok",
        action="store_true",
        help="quarantine the saved grok.com session files",
    )
    grokActions.add_argument(
        "--scan",
        dest="grok",
        action="store_true",
        help="scan and download this account's generated Imagine media",
    )
    return parser


def _normalizeArguments(args: argparse.Namespace) -> argparse.Namespace:
    """Map canonical commands onto the established workflow argument shape."""
    command = getattr(args, "command", None)
    if command == "media":
        _sourceAliasResolve(args, "source")
        args.clean = args.mediaAction == "clean"
    elif command == "library":
        _sourceAliasResolve(args, "source")
        args.rescan = True
        args.movie = args.target == "movies"
        args.video = args.target == "tv"
    elif command == "torrent":
        _sourceAliasResolve(args, "source")
        args.torrent = True
        args.clean = bool(args.clean_names)
    elif command == "camera" and getattr(args, "cameraAction", None) == "inventory":
        _sourceAliasResolve(args, "inventorySource")
    return args


def _validateArguments(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    """Reject conflicting modes and invalid canonical source paths."""
    legacyModes = sum(
        bool(value)
        for value in (
            args.rescan,
            args.torrent,
            args.grok,
            args.import_firefox_session,
            args.reset_grok,
        )
    )
    if legacyModes > 1:
        parser.error("select only one workflow mode")
    if (
        args.command
        and legacyModes
        and args.command
        not in {
            "library",
            "torrent",
            "grok",
        }
    ):
        parser.error("do not combine a canonical command with a legacy mode flag")
    if args.command == "camera":
        if getattr(args, "cameraAction", None) == "inventory":
            cardId = getattr(args, "card", None)
            inventorySource = getattr(args, "inventorySource", None)
            if cardId is not None and cardId < 1:
                parser.error("--card must be a positive integer")
            if getattr(args, "reassign", False):
                if not inventorySource:
                    parser.error("--reassign requires SOURCE")
                if cardId is None or cardId < 1:
                    parser.error("--reassign requires --card with the new ID")
            if not inventorySource and (cardId is None or cardId < 1):
                parser.error("--card is required when SOURCE is omitted")
            if inventorySource:
                sourcePath = Path(inventorySource).expanduser()
                if not sourcePath.is_dir():
                    parser.error(f"source directory does not exist: {sourcePath}")
                args.inventorySource = str(sourcePath)
        return
    if args.command in {"media", "library", "torrent"}:
        sourcePath = Path(args.source).expanduser()
        if not sourcePath.is_dir():
            parser.error(f"source directory does not exist: {sourcePath}")
        args.source = str(sourcePath)


def _loggingLevel(args: argparse.Namespace) -> int:
    """Return the requested process logging level."""
    if args.quiet:
        return logging.ERROR
    if args.debug:
        return logging.DEBUG
    return logging.INFO


def _configureLogging(args: argparse.Namespace, dryRun: bool) -> None:
    """Configure the established application logger for CLI execution."""
    global logger
    logger = getLogger(
        includeConsole=True,
        dryRun=dryRun,
        level=_loggingLevel(args),
    )


def _selectedMode(args: argparse.Namespace) -> str:
    """Return the normalized organiser workflow mode."""
    if args.torrent:
        return "torrent"
    if args.rescan:
        return "rescan"
    if args.clean:
        return "clean"
    if getattr(args, "merge", False):
        return "merge"
    return "process"


def _runCameraWorkflow(args: argparse.Namespace, dryRun: bool) -> int:
    """Run camera-card inventory through the Python application service."""

    from . import constants
    from .cameraInventory import cameraInventoryRun, cameraInventorySummary

    logger.value("mode", "camera-inventory")
    source = getattr(args, "inventorySource", None)
    sourcePath = Path(source) if source else None
    try:
        record = cameraInventoryRun(
            cardId=args.card,
            source=sourcePath,
            dryRun=dryRun,
            databasePath=constants.CAMERA_INVENTORY_DATABASE,
            reassign=bool(getattr(args, "reassign", False)),
            brand=getattr(args, "brand", None),
        )
    except PermissionError as error:
        logger.error(
            f"camera inventory permission denied: {error.filename or sourcePath}; "
            "select the card mount itself and check its write permissions"
        )
        return 1
    except (OSError, RuntimeError, ValueError) as error:
        logger.error("%s", error)
        return 1
    persisted = True if sourcePath is None else not dryRun
    drawBox(
        cameraInventorySummary(
            record,
            persisted=persisted,
            databasePath=constants.CAMERA_INVENTORY_DATABASE,
        )
    )
    return 0


def _runGalleryWorkflow(args: argparse.Namespace, dryRun: bool) -> int:
    """Run a normalized legacy-gallery action."""
    from .grokGallery import GROK_SESSION_FILE, GrokGallery

    gallery = GrokGallery(dryRun=dryRun)
    logger.value("mode", "grok-gallery")
    try:
        _runGrokGalleryCommand(args, gallery, GROK_SESSION_FILE)
    except RuntimeError as error:
        logger.error("%s", error)
        return 1
    return 0


def _mergeSummary(stats, *, label: str) -> str:
    """Return the terminal summary for one library merge run."""

    return f"""{label} MERGE SUMMARY
Groups found:        {stats.groupsFound}
Groups merged:       {stats.groupsMerged}
Identity conflicts:  {stats.identityConflicts}
Files moved:         {stats.filesMoved}
Directories moved:   {stats.directoriesMoved}
Directories removed: {stats.directoriesRemoved}
Duplicates kept:     {stats.duplicates}
Conflicts kept:      {stats.conflicts}
Errors:              {stats.errors}
"""


def _seasonSummary(stats, *, label: str) -> str:
    """Return the terminal summary for TV library-folder normalisation."""

    return f"""{label} SUMMARY
Folders renamed:     {stats.renamed}
Files moved:         {stats.filesMoved}
Directories removed: {stats.directoriesRemoved}
Duplicates kept:     {stats.duplicates}
Conflicts kept:      {stats.conflicts}
Errors:              {stats.errors}
"""


def _normaliseSeasonFolders(organizer, dryRun: bool, *, refreshCatalogue: bool):
    """Canonicalise TV show and season folder names and optionally refresh TV paths."""

    from .mediaCatalogue import MediaCatalogue
    from .seasonFolders import SeasonFolderStats, normaliseTvSeasonFolders
    from .showFolders import normaliseMovieFolderNames, normaliseTvShowFolderNames

    storageLocations = organizer.scanStorageLocations()
    if not isinstance(storageLocations, (tuple, list)) or len(storageLocations) != 2:
        # A malformed discovery result cannot be used safely. This is principally
        # useful for lightweight mocked organizers, while keeping production
        # behaviour explicit rather than attempting to infer locations.
        logger.debug("skipping TV folder normalisation: storage locations unavailable")
        return SeasonFolderStats()

    movieDirs, videoDirs = storageLocations
    filesystem = FilesystemOperations(dryRun=dryRun)
    showStats = normaliseTvShowFolderNames(
        videoDirs,
        filesystem=filesystem,
        dryRun=dryRun,
    )
    drawBox(_seasonSummary(showStats, label="TV SHOW FOLDER"))
    movieFolderStats = normaliseMovieFolderNames(
        movieDirs,
        filesystem=filesystem,
        dryRun=dryRun,
    )
    drawBox(_seasonSummary(movieFolderStats, label="MOVIE FOLDER"))
    seasonStats = normaliseTvSeasonFolders(
        videoDirs,
        filesystem=filesystem,
        dryRun=dryRun,
    )
    drawBox(_seasonSummary(seasonStats, label="SEASON FOLDER"))
    changed = showStats.changed or movieFolderStats.changed or seasonStats.changed
    if not dryRun and refreshCatalogue and changed:
        logger.doing("refreshing media catalogue after folder normalisation")
        MediaCatalogue().catalogueReplaceFromStorage(
            movieDirs,
            videoDirs,
            replaceMovies=True,
            replaceTv=True,
        )
    combined = SeasonFolderStats(
        renamed=showStats.renamed + movieFolderStats.renamed + seasonStats.renamed,
        filesMoved=showStats.filesMoved
        + movieFolderStats.filesMoved
        + seasonStats.filesMoved,
        directoriesRemoved=showStats.directoriesRemoved
        + movieFolderStats.directoriesRemoved
        + seasonStats.directoriesRemoved,
        duplicates=showStats.duplicates
        + movieFolderStats.duplicates
        + seasonStats.duplicates,
        conflicts=showStats.conflicts
        + movieFolderStats.conflicts
        + seasonStats.conflicts,
        errors=showStats.errors + movieFolderStats.errors + seasonStats.errors,
    )
    return combined


def _runOrganizerWorkflow(args: argparse.Namespace, dryRun: bool) -> int:
    """Construct the domain organizer and dispatch one normalized workflow."""
    configPath = _getAppConfigPath()
    if args.key is not None:
        if not _persistTvdbApiKey(args.key, configPath):
            logger.warning("blank TVDB API key provided; not saving")
    else:
        _loadTvdbApiKeyFromConfig(configPath)

    selectedMode = _selectedMode(args)
    logger.value("source directory", args.source)
    logger.value("mode", selectedMode)
    logger.doing("initializing video organizer")
    from . import VideoOrganizer

    organizer = VideoOrganizer(
        sourceDir=args.source,
        dryRun=dryRun,
        refreshMetadataLibrary=args.refresh_metadata_library,
        useCurses=True,
    )
    organizer.tvdbApiKeyPrompt = (
        (lambda: _promptForTvdbApiKey(configPath))
        if selectedMode == "process" and not args.auto
        else None
    )
    if args.auto or selectedMode == "rescan":
        organizer.summaryReportPath = _getSummaryReportPath(args.source, selectedMode)
        organizer.summaryReportMode = selectedMode
    logger.done("video organizer initialized")

    if args.torrent:
        logger.doing("running torrent maintenance")
        torrentDir = organizer.sourceDir.parent / "Downloads"
        nameStats = {"renamed": 0, "skipped": 0, "errors": 0}
        if args.clean:
            nameStats = organizer.cleanTorrentNames(torrentDir=torrentDir)
        removeStats = organizer.removeTorrentsInLibrary(torrentDir=torrentDir)
        drawBox(
            f"""TORRENT SUMMARY
Torrents deleted: {removeStats['deleted']}
Torrents kept:    {removeStats['skipped']}
Delete errors:    {removeStats['errors']}
Names renamed:    {nameStats['renamed']}
Names skipped:    {nameStats['skipped']}
Rename errors:    {nameStats['errors']}
"""
        )
    elif args.clean:
        logger.doing("running clean mode")
        nameStats = organizer.cleanNames()
        cleanStats = organizer.cleanEmptyFolders()
        drawBox(
            f"""CLEAN SUMMARY
Names renamed:   {nameStats['renamed']}
Name errors:     {nameStats['errors']}
Folders removed: {cleanStats['removed']}
Folders kept:    {cleanStats['skipped']}
Folder errors:   {cleanStats['errors']}
"""
        )
        logger.doing("normalising TV show and season folders")
        folderStats = _normaliseSeasonFolders(
            organizer,
            dryRun,
            refreshCatalogue=True,
        )
        if folderStats.errors:
            return 1
    elif args.rescan:
        target = (
            "movies"
            if args.movie and not args.video
            else "tv" if args.video and not args.movie else "both"
        )
        logger.doing(f"running rescan mode ({target})")
        organizer.resetLibraryMetadata(target=target)
    elif getattr(args, "merge", False):
        from .mediaCatalogue import MediaCatalogue
        from .mediaMerge import mergeDuplicateMovies, mergeDuplicateTvShows

        logger.doing("normalising TV show and season folders before merge")
        seasonStats = _normaliseSeasonFolders(
            organizer,
            dryRun,
            refreshCatalogue=True,
        )
        logger.doing("running TV library merge mode")
        catalogue = MediaCatalogue()
        filesystem = FilesystemOperations(dryRun=dryRun)
        tvStats = mergeDuplicateTvShows(
            catalogue=catalogue,
            filesystem=filesystem,
            dryRun=dryRun,
        )
        drawBox(_mergeSummary(tvStats, label="TV"))
        logger.doing("running movie library merge mode")
        movieStats = mergeDuplicateMovies(
            catalogue=catalogue,
            filesystem=filesystem,
            dryRun=dryRun,
        )
        drawBox(_mergeSummary(movieStats, label="MOVIE"))
        if not dryRun and (tvStats.groupsMerged or movieStats.groupsMerged):
            logger.doing("refreshing media catalogue after merge")
            movieDirs, videoDirs = organizer.scanStorageLocations()
            catalogue.catalogueReplaceFromStorage(
                movieDirs,
                videoDirs,
                replaceMovies=True,
                replaceTv=True,
            )
        return 1 if tvStats.errors or movieStats.errors or seasonStats.errors else 0
    else:
        logger.doing("running file organisation mode")
        organizer.processFiles(interactive=not args.auto)
        logger.doing("normalising TV show and season folders")
        seasonStats = _normaliseSeasonFolders(
            organizer,
            dryRun,
            refreshCatalogue=True,
        )
        if seasonStats.errors:
            return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command-line application and return a process status."""
    parser = buildParser()
    args = _normalizeArguments(parser.parse_args(argv))
    _validateArguments(parser, args)

    dryRun = not args.confirm
    _configureLogging(args, dryRun)
    logger.doing("organiseMyVideo starting")

    if dryRun:
        logger.info("entering dry-run mode, use --confirm to execute")
    else:
        logger.info("confirm mode, changes will be made")

    command = getattr(args, "command", None)
    if command == "grok":
        status = _runGalleryWorkflow(args, dryRun)
    elif command == "camera":
        status = _runCameraWorkflow(args, dryRun)
    else:
        status = _runOrganizerWorkflow(args, dryRun)
    logger.done("organiseMyVideo complete")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
