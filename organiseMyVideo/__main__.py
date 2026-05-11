#!/usr/bin/env python3
"""Entry point: ``python -m organiseMyVideo``."""

import argparse
import logging
from pathlib import Path

from organiseMyProjects.logUtils import getLogger, drawBox, setApplication  # type: ignore

thisApplication = Path(__file__).parent.name
setApplication(thisApplication)

logger = getLogger(includeConsole=False)


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
        "--refresh-metadata-library",
        dest="refresh_metadata_library",
        action="store_true",
        help="rebuild the saved metadata library from storage before processing"
    )
    parser.add_argument(
        "--curses",
        action="store_true",
        help="use curses-driven single-key prompts for interactive choices"
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
    logger = getLogger(includeConsole=True, dryRun=dryRun)
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
    
    if dryRun:
        logger.info("entering dry-run mode, use --confirm to execute")
    else:
        logger.info("confirm mode, changes will be made")

    if args.torrent:
        selectedMode = "torrent"
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
    logger.done("video organizer initialized")

    if args.torrent:
        logger.doing("running torrent maintenance")
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
    else:
        logger.doing("running file organisation mode")
        organizer.processFiles(interactive=not args.non_interactive)

    logger.done("organiseMyVideo complete")


if __name__ == "__main__":
    main()
