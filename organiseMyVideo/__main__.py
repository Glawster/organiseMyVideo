#!/usr/bin/env python3
"""Entry point: ``python -m organiseMyVideo``."""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from organiseMyProjects.logUtils import getLogger, drawBox, setApplication  # type: ignore

from .constants import APP_CONFIG_FILE

thisApplication = Path(__file__).parent.name
setApplication(thisApplication)

logger = getLogger(includeConsole=False)


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
        deletedList = "\n".join(f"  {path}" for path in resetStats["deleted"]) or "  (none)"
        notFoundList = "\n".join(f"  {path}" for path in resetStats["notFound"]) or "  (none)"
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


def _buildSharedFlags() -> argparse.ArgumentParser:
    """Return flags shared by the organiser and grok subcommands."""
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        default=False,
        action="store_true",
        help="confirm execution — actually make changes (default is dry-run)",
    )
    shared.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )
    return shared


def buildParser() -> argparse.ArgumentParser:
    """Return the public CLI parser, including the grok subcommand."""
    parser = argparse.ArgumentParser(
        description="Organize video files into movies and TV show directories",
        parents=[_buildSharedFlags()],
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
    grokParser = subparsers.add_parser(
        "grok",
        parents=[_buildSharedFlags()],
        help="generate, list, and download Imagine media through the xAI API",
    )
    grokSub = grokParser.add_subparsers(dest="grokAction", required=True)
    generateParser = grokSub.add_parser(
        "generate",
        parents=[_buildSharedFlags()],
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
        parents=[_buildSharedFlags()],
        help="list stored Imagine images and videos",
    )
    downloadParser = grokSub.add_parser(
        "download",
        parents=[_buildSharedFlags()],
        help="download stored Imagine media to the local archive",
    )
    downloadParser.add_argument(
        "--file-id",
        dest="file_id",
        help="download only this Files API id",
    )
    return parser


def main():
    """Main entry point for the video organizer."""
    parser = buildParser()
    args = parser.parse_args()

    dryRun = not args.confirm

    # Setup logging — dryRun passed so logger.action() applies [] prefix correctly.
    # logUtils._setupLogging guards console handler with isinstance(h, StreamHandler)
    # which also matches FileHandler (subclass); add console handler explicitly if absent.
    global logger
    logger = getLogger(includeConsole=True, dryRun=dryRun)
    if args.debug:
        logger.logger.setLevel(logging.DEBUG)
    if not any(type(h) is logging.StreamHandler for h in logger.logger.handlers):
        _ch = logging.StreamHandler()
        _ch.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.logger.addHandler(_ch)
    else:
        # Update the existing console handler formatter to include timestamp
        for h in logger.logger.handlers:
            if type(h) is logging.StreamHandler:
                h.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                    )
                )
    logger.doing("organiseMyVideo starting")

    if dryRun:
        logger.info("entering dry-run mode, use --confirm to execute")
    else:
        logger.info("confirm mode, changes will be made")

    if args.reset_grok or args.import_firefox_session or args.grok:
        from .grokGallery import GROK_SESSION_FILE, GrokGallery

        gallery = GrokGallery(dryRun=dryRun)
        logger.value("mode", "grok-gallery")
        try:
            _runGrokGalleryCommand(args, gallery, GROK_SESSION_FILE)
        except RuntimeError as error:
            logger.error("%s", error)
            raise SystemExit(1) from error
        logger.done("organiseMyVideo complete")
        return

    if getattr(args, "command", None) == "grok":
        from .grok import grokCommandRun

        logger.value("mode", "grok")
        logger.value("grok action", args.grokAction)
        try:
            result = grokCommandRun(args, dryRun=dryRun)
        except RuntimeError as error:
            logger.error("%s", error)
            raise SystemExit(1) from error
        if args.grokAction == "download":
            summary = f"""GROK DOWNLOAD SUMMARY
Downloaded: {result['downloaded']}
Skipped:    {result['skipped']}
Errors:     {result['errors']}
"""
            drawBox(summary)
        elif args.grokAction == "list":
            logger.value("listed files", len(result.get("files", [])))
        elif args.grokAction == "generate":
            logger.value("file id", result.get("fileId") or "(dry-run)")
            logger.value("filename", result.get("filename"))
        logger.done("organiseMyVideo complete")
        return

    configPath = _getAppConfigPath()
    if args.key is not None:
        if not _persistTvdbApiKey(args.key, configPath):
            logger.warning("blank TVDB API key provided; not saving")
    else:
        _loadTvdbApiKeyFromConfig(configPath)

    if args.torrent:
        selectedMode = "torrent"
    elif args.rescan:
        selectedMode = "rescan"
    elif args.clean:
        selectedMode = "clean"
    else:
        selectedMode = "process"

    logger.value("source directory", args.source)
    logger.value("mode", selectedMode)

    # Create organizer and run the requested mode
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
        torrentDir = (
            organizer.sourceDir.parent / "Downloads"
            if organizer.sourceDir
            else Path("/mnt/video2/Downloads")
        )
        nameStats = {"renamed": 0, "skipped": 0, "errors": 0}
        if args.clean:
            nameStats = organizer.cleanTorrentNames(torrentDir=torrentDir)
        removeStats = organizer.removeTorrentsInLibrary(torrentDir=torrentDir)
        summary = f"""TORRENT SUMMARY
Torrents deleted: {removeStats['deleted']}
Torrents kept:    {removeStats['skipped']}
Delete errors:    {removeStats['errors']}
Names renamed:    {nameStats['renamed']}
Names skipped:    {nameStats['skipped']}
Rename errors:    {nameStats['errors']}
"""
        drawBox(summary)

    elif args.clean:
        logger.doing("running clean mode")
        nameStats = organizer.cleanNames()
        cleanStats = organizer.cleanEmptyFolders()
        summary = f"""CLEAN SUMMARY
Names renamed:   {nameStats['renamed']}
Name errors:     {nameStats['errors']}
Folders removed: {cleanStats['removed']}
Folders kept:    {cleanStats['skipped']}
Folder errors:   {cleanStats['errors']}
"""
        drawBox(summary)
    elif args.rescan:
        rescanTarget = "both"
        if args.movie and args.video:
            rescanTarget = "both"
        elif args.movie:
            rescanTarget = "movies"
        elif args.video:
            rescanTarget = "tv"
        logger.doing(f"running rescan mode ({rescanTarget})")
        organizer.resetLibraryMetadata(target=rescanTarget)
    else:
        logger.doing("running file organisation mode")
        organizer.processFiles(interactive=not (args.non_interactive or args.auto))

    logger.done("organiseMyVideo complete")


if __name__ == "__main__":
    main()
