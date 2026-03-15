#!/usr/bin/env python3
"""Entry point: ``python -m organiseMyVideo``."""

import argparse
import datetime
import logging
from pathlib import Path

from organiseMyProjects.logUtils import getLogger, drawBox  # type: ignore

from . import VideoOrganizer
from .constants import GROK_SESSION_FILE

logger = getLogger("organiseMyVideo")


def main():
    """Main entry point for the video organizer."""
    parser = argparse.ArgumentParser(
        description="Organize video files into movies and TV show directories"
    )
    parser.add_argument(
        "--source",
        default="/mnt/video2/toFile",
        help="Source directory containing files to organize (default: /mnt/video2/toFile)"
    )
    parser.add_argument(
        '--confirm',
        default=False,
        action='store_true',
        help='confirm execution — actually make changes (default is dry-run)',
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove empty sub-folders from source directory (folders with only sample content are treated as empty)"
    )
    parser.add_argument(
        "--non-interactive",
        dest="non_interactive",
        action="store_true",
        help="Run without user prompts (skip files that cannot be auto-detected)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete saved Grok session and credentials config files to force a fresh login on the next --grok run"
    )
    parser.add_argument(
        "--import-firefox-session",
        dest="import_firefox_session",
        action="store_true",
        help=(
            "import Grok cookies from your Firefox profile into the saved session file — "
            "log into grok.com/imagine/saved in Firefox first, then run this to avoid "
            "the Cloudflare Turnstile challenge during --grok"
        ),
    )
    parser.add_argument(
        "--grok",
        action="store_true",
        help="Log into Grok and download media from saved Imagine items into --source"
    )
    parser.add_argument(
        "--torrent",
        action="store_true",
        help="scan the torrent download directory for .torrent files and delete those already in the library (dry-run by default; use --confirm to delete)"
    )
    args = parser.parse_args()
    
    dryRun = True if not args.confirm else False

    # Setup logging — dryRun passed so logger.action() applies [] prefix correctly.
    # logUtils._setupLogging guards console handler with isinstance(h, StreamHandler)
    # which also matches FileHandler (subclass); add console handler explicitly if absent.
    global logger
    logTimestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    logDir = Path.home() / ".local" / "state" / "organiseMy" / "logs"
    logDir.mkdir(parents=True, exist_ok=True)
    logFile = logDir / f"organiseMyVideo_{logTimestamp}.log"
    logger = getLogger("organiseMyVideo", logDir=logDir, includeConsole=True, dryRun=dryRun)
    if not any(type(h) is logging.StreamHandler for h in logger.logger.handlers):
        _ch = logging.StreamHandler()
        _ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.logger.addHandler(_ch)
    else:
        # Update the existing console handler formatter to include timestamp
        for h in logger.logger.handlers:
            if type(h) is logging.StreamHandler:
                h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.doing("organiseMyVideo starting")
    logger.value("logging to", logFile)
    
    if dryRun:
        logger.info("entering dry-run mode, use --confirm to execute")
    else:
        logger.info("confirm mode, changes will be made")
    
    # Create organizer and run the requested mode
    organizer = VideoOrganizer(sourceDir=args.source, dryRun=dryRun)

    if args.reset:
        resetStats = organizer.resetGrokConfig()
        deleted_list = "\n".join(f"  {p}" for p in resetStats["deleted"]) or "  (none)"
        not_found_list = "\n".join(f"  {p}" for p in resetStats["notFound"]) or "  (none)"
        summary = f"""RESET SUMMARY
Deleted:
{deleted_list}
Not found:
{not_found_list}
"""
        drawBox(summary)

    elif args.import_firefox_session:
        ok = organizer.importFirefoxSession()
        if ok:
            summary = (
                f"FIREFOX SESSION IMPORTED\n"
                f"  Session file: {GROK_SESSION_FILE}\n\n"
                f"Run --grok to start scraping."
            )
        else:
            summary = (
                "FIREFOX SESSION IMPORT FAILED\n\n"
                "Make sure you are logged into grok.com in Firefox,\n"
                "then run --import-firefox-session again.\n\n"
                "Alternatively, run --grok and log in via the browser window."
            )
        drawBox(summary)

    elif args.grok:
        grokStats = organizer.scrapeGrokSavedMedia()
        summary = f"""GROK SUMMARY
Posts found:     {grokStats['postsFound']}
URLs found:      {grokStats['urlsFound']}
Files handled:   {grokStats['downloaded']}
Already present: {grokStats['skipped']}
Errors:          {grokStats['errors']}
Session file:    {GROK_SESSION_FILE}
  (delete to force re-login)
"""
        drawBox(summary)

    elif args.torrent:
        torrentDir = organizer.sourceDir.parent / "Downloads" if organizer.sourceDir else Path("/mnt/video2/Downloads")
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
    else:
        organizer.processFiles(interactive=not args.non_interactive)

    logger.done("organiseMyVideo complete")


if __name__ == "__main__":
    main()
