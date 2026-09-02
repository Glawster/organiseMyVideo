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

from organiseMyProjects.logUtils import drawBox  # type: ignore

from .constants import APP_CONFIG_FILE
from .logging_utils import initializeLogging, logger

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
    configPath.parent.mkdir(parents=True, exist_ok=True)
    configPath.write_text(
        json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
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
    """Run --reset-grok, --import-firefox-session, or --grok gallery download."""
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
                f"Run --grok --confirm to download your Imagine media."
            )
        else:
            summary = (
                "FIREFOX SESSION IMPORT FAILED\n\n"
                "Make sure you are logged into grok.com in Firefox,\n"
                "then run --import-firefox-session again.\n\n"
                "Alternatively, run --grok and Firefox will be opened automatically."
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
  (delete with --reset-grok to force re-login)
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
        help="legacy alias for --verbose",
    )
    verbosity = shared.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", action="store_true", help="enable detailed logging"
    )
    verbosity.add_argument("--quiet", action="store_true", help="show errors only")
    return shared


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
        "--non-interactive",
        dest="non_interactive",
        action="store_true",
        help="Run without user prompts (skip files that cannot be auto-detected)",
    )
    parser.add_argument(
        "--refresh",
        dest="refresh_metadata_library",
        action="store_true",
        help="rebuild the saved metadata library from storage before processing",
    )
    parser.add_argument(
        "--no-curses",
        dest="curses",
        action="store_false",
        default=True,
        help="use line-based prompts instead of the default curses single-key menus",
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
    parser.add_argument(
        "--grok",
        action="store_true",
        help="download this account's generated grok.com Imagine media to ~/Downloads/Grok",
    )
    parser.add_argument(
        "--import-firefox-session",
        dest="import_firefox_session",
        action="store_true",
        help="import grok.com cookies from Firefox after logging in at grok.com/imagine/saved",
    )
    parser.add_argument(
        "--reset-grok",
        dest="reset_grok",
        action="store_true",
        help="delete saved grok.com session files so the next --grok run logs in again",
    )
    subparsers = parser.add_subparsers(dest="command")
    mediaParser = subparsers.add_parser("media", help="organise or clean staged media")
    mediaSub = mediaParser.add_subparsers(dest="mediaAction", required=True)
    mediaOrganise = mediaSub.add_parser(
        "organise", parents=[_buildSharedFlags(True)], help="organise staged media"
    )
    mediaOrganise.add_argument("source", nargs="?", default="/mnt/video2/toFile")
    mediaOrganise.add_argument("--auto", action="store_true")
    mediaOrganise.add_argument("--non-interactive", action="store_true")
    mediaOrganise.add_argument(
        "--refresh", dest="refresh_metadata_library", action="store_true"
    )
    mediaOrganise.add_argument(
        "--no-curses", dest="curses", action="store_false", default=True
    )
    mediaClean = mediaSub.add_parser(
        "clean",
        parents=[_buildSharedFlags(True)],
        help="clean staged media names and folders",
    )
    mediaClean.add_argument("source", nargs="?", default="/mnt/video2/toFile")

    libraryParser = subparsers.add_parser("library", help="maintain media libraries")
    librarySub = libraryParser.add_subparsers(dest="libraryAction", required=True)
    libraryRescan = librarySub.add_parser(
        "rescan", parents=[_buildSharedFlags(True)], help="rescan movie and TV metadata"
    )
    libraryRescan.add_argument("source", nargs="?", default="/mnt/video2/toFile")
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
    torrentMaintain.add_argument("source", nargs="?", default="/mnt/video2/toFile")
    torrentMaintain.add_argument("--clean-names", action="store_true")

    galleryParser = subparsers.add_parser(
        "gallery", help="maintain the legacy grok.com gallery"
    )
    gallerySub = galleryParser.add_subparsers(dest="galleryAction", required=True)
    gallerySub.add_parser("download", parents=[_buildSharedFlags(True)])
    gallerySub.add_parser("import-session", parents=[_buildSharedFlags(True)])
    gallerySub.add_parser("reset-session", parents=[_buildSharedFlags(True)])
    grokParser = subparsers.add_parser(
        "grok",
        parents=[_buildSharedFlags(True)],
        help="generate, list, and download Imagine media through the xAI API",
    )
    grokSub = grokParser.add_subparsers(dest="grokAction", required=True)
    generateParser = grokSub.add_parser(
        "generate",
        parents=[_buildSharedFlags(True)],
        help="generate an image or video and persist it with storage_options",
    )
    generateParser.add_argument(
        "prompt",
        help="text prompt for image or video generation",
    )
    generateParser.add_argument(
        "--kind",
        choices=("image", "video"),
        default="image",
        help="generation kind (default: image)",
    )
    generateParser.add_argument(
        "--filename",
        help="filename stored in the Files API (default: timestamp plus prompt slug)",
    )
    generateParser.add_argument(
        "--image",
        help="optional local image path or URL used as a reference",
    )
    generateParser.add_argument(
        "--duration",
        type=int,
        default=6,
        help="video duration in seconds, 1-15 (default: 6)",
    )
    grokSub.add_parser(
        "list",
        parents=[_buildSharedFlags(True)],
        help="list stored Imagine images and videos",
    )
    downloadParser = grokSub.add_parser(
        "download",
        parents=[_buildSharedFlags(True)],
        help="download stored Imagine media to the local archive",
    )
    downloadParser.add_argument(
        "--file-id",
        dest="file_id",
        help="download only this Files API id",
    )
    return parser


def _normalizeArguments(args: argparse.Namespace) -> argparse.Namespace:
    """Map canonical commands onto the established workflow argument shape."""
    command = getattr(args, "command", None)
    if command == "media":
        args.clean = args.mediaAction == "clean"
    elif command == "library":
        args.rescan = True
        args.movie = args.target == "movies"
        args.video = args.target == "tv"
    elif command == "torrent":
        args.torrent = True
        args.clean = bool(args.clean_names)
    elif command == "gallery":
        args.grok = args.galleryAction == "download"
        args.import_firefox_session = args.galleryAction == "import-session"
        args.reset_grok = args.galleryAction == "reset-session"
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
        and args.command != "grok"
        and legacyModes
        and args.command
        not in {
            "library",
            "torrent",
            "gallery",
        }
    ):
        parser.error("do not combine a canonical command with a legacy mode flag")
    if args.command in {"media", "library", "torrent"}:
        sourcePath = Path(args.source).expanduser()
        if not sourcePath.is_dir():
            parser.error(f"source directory does not exist: {sourcePath}")
        args.source = str(sourcePath)


def _loggingLevel(args: argparse.Namespace) -> int:
    """Return the requested process logging level."""
    if args.quiet:
        return logging.ERROR
    if args.verbose or args.debug:
        return logging.DEBUG
    return logging.INFO


def _configureLogging(args: argparse.Namespace, dryRun: bool) -> None:
    """Initialize logging once from the executable entry point."""
    initializeLogging(dryRun=dryRun, level=_loggingLevel(args), includeConsole=True)


def _selectedMode(args: argparse.Namespace) -> str:
    """Return the normalized organiser workflow mode."""
    if args.torrent:
        return "torrent"
    if args.rescan:
        return "rescan"
    if args.clean:
        return "clean"
    return "process"


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


def _runGrokWorkflow(args: argparse.Namespace, dryRun: bool) -> int:
    """Run an official Imagine API action and render its summary."""
    from .grok import grokCommandRun

    logger.value("mode", "grok")
    logger.value("grok action", args.grokAction)
    try:
        result = grokCommandRun(args, dryRun=dryRun)
    except RuntimeError as error:
        logger.error("%s", error)
        return 1
    if args.grokAction == "download":
        drawBox(
            f"""GROK DOWNLOAD SUMMARY
Downloaded: {result['downloaded']}
Skipped:    {result['skipped']}
Errors:     {result['errors']}
"""
        )
    elif args.grokAction == "list":
        logger.value("listed files", len(result.get("files", [])))
    else:
        logger.value("file id", result.get("fileId") or "(dry-run)")
        logger.value("filename", result.get("filename"))
    return 0


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
        useCurses=args.curses,
    )
    organizer.tvdbApiKeyPrompt = (
        (lambda: _promptForTvdbApiKey(configPath))
        if selectedMode == "process" and not (args.non_interactive or args.auto)
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
    elif args.rescan:
        target = (
            "movies"
            if args.movie and not args.video
            else "tv" if args.video and not args.movie else "both"
        )
        logger.doing(f"running rescan mode ({target})")
        organizer.resetLibraryMetadata(target=target)
    else:
        logger.doing("running file organisation mode")
        organizer.processFiles(interactive=not (args.non_interactive or args.auto))
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

    if args.reset_grok or args.import_firefox_session or args.grok:
        status = _runGalleryWorkflow(args, dryRun)
    elif getattr(args, "command", None) == "grok":
        status = _runGrokWorkflow(args, dryRun)
    else:
        status = _runOrganizerWorkflow(args, dryRun)
    logger.done("organiseMyVideo complete")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
