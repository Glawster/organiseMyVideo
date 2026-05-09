"""Torrent-file cleanup: remove stale .torrent files from the download directory."""

import shutil
from pathlib import Path

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import _PREFIX_REGEX

logger = getLogger(Path(__file__).stem)


class TorrentMixin:
    """Methods for managing torrent files in the download directory."""

    def removeTorrentsInLibrary(self, torrentDir: str = "/mnt/video2/Downloads") -> dict:
        """
        Scan the download directory for .torrent files and delete those
        belonging to movies or TV shows already present in the library.

        When a matching .torrent file lives inside a sub-directory of the
        download directory, the whole containing folder is removed. This keeps
        in-progress download folders together instead of deleting only the
        .torrent file and leaving the partial download behind.

        Args:
            torrentDir: Directory to scan for .torrent files (default: /mnt/video2/Downloads)

        Returns:
            Dictionary with counts: {'deleted': int, 'skipped': int, 'errors': int}
        """
        logger.doing(f"scanning for obsolete torrent files in {torrentDir}")

        stats = {"deleted": 0, "skipped": 0, "errors": 0}

        downloadPath = Path(torrentDir)
        if not downloadPath.exists():
            logger.error(f"torrent directory does not exist: {torrentDir}")
            return stats

        movieDirs, videoDirs = self.scanStorageLocations()

        # Track removed download sub-directories so nested torrent files from an
        # already-deleted folder are not processed again later in the scan.
        removedDirs = set()

        for entry in sorted(downloadPath.rglob("*.torrent")):
            if not entry.is_file():
                continue
            if any(parent in removedDirs for parent in entry.parents):
                continue

            # The stem may already contain an inner extension (e.g. "Movie.2010.mkv")
            # or may not (e.g. "Movie.2010"). Append ".mkv" as a neutral fallback so
            # that the TV/movie parsers (which require an extension suffix) can still match.
            # Strip known torrent-site prefixes (e.g. "www.Torrenting.com - ") before parsing.
            stem = _PREFIX_REGEX.sub("", entry.stem, count=1).strip()
            fallback = stem + ".mkv"
            tvInfo = self.parseTvFilename(stem) or self.parseTvFilename(fallback)
            movieInfo = self.parseMovieFilename(stem) or self.parseMovieFilename(fallback)

            inLibrary = False

            if tvInfo and videoDirs:
                existingDir = self.findExistingTvShowDir(tvInfo["showName"], videoDirs)
                if existingDir:
                    inLibrary = True
                    logger.value("torrent matches TV show", f"{entry.name} → {existingDir}")

            if not inLibrary and movieInfo and movieDirs:
                existingDir = self.findExistingMovieDir(movieInfo["title"], movieInfo["year"], movieDirs)
                if existingDir:
                    inLibrary = True
                    logger.value("torrent matches Movie", f"{entry.name} → {existingDir}")

            if inLibrary:
                downloadSubDir = entry.parent if entry.parent != downloadPath else None
                if self.dryRun:
                    if downloadSubDir is not None:
                        logger.action(f"delete folder: {downloadSubDir.name}")
                        removedDirs.add(downloadSubDir)
                    else:
                        logger.action(f"delete torrent: {entry.name}")
                    stats["deleted"] += 1
                else:
                    try:
                        if downloadSubDir is not None:
                            shutil.rmtree(downloadSubDir)
                            logger.action(f"deleted folder: {downloadSubDir.name}")
                            removedDirs.add(downloadSubDir)
                        else:
                            entry.unlink()
                            logger.action(f"deleted torrent: {entry.name}")
                        stats["deleted"] += 1
                    except Exception as e:
                        logger.error(f"failed to delete {entry.name}: {e}")
                        stats["errors"] += 1
            else:
                logger.value("keeping torrent", entry.name)
                stats["skipped"] += 1

        logger.done("remove torrents in library complete")
        return stats

    def cleanTorrentNames(self, torrentDir: str = "/mnt/video2/Downloads") -> dict:
        """
        Scan the download directory for .torrent files and rename those whose
        file names contain known torrent-site prefixes (e.g. "www.Torrenting.com - ").

        Args:
            torrentDir: Directory to scan for .torrent files (default: /mnt/video2/Downloads)

        Returns:
            Dictionary with counts: {'renamed': int, 'skipped': int, 'errors': int}
        """
        logger.doing(f"cleaning torrent file names in {torrentDir}")

        stats = {"renamed": 0, "skipped": 0, "errors": 0}

        downloadPath = Path(torrentDir)
        if not downloadPath.exists():
            logger.error(f"torrent directory does not exist: {torrentDir}")
            return stats

        for entry in sorted(downloadPath.rglob("*.torrent")):
            if not entry.is_file():
                continue

            oldName = entry.name
            if not _PREFIX_REGEX.match(oldName):
                continue

            newName = _PREFIX_REGEX.sub("", oldName, count=1).strip()

            if not newName or newName == oldName:
                logger.value("skipped (no change)", oldName)
                stats["skipped"] += 1
                continue

            newPath = entry.parent / newName

            if self.dryRun:
                logger.action(f"rename torrent: {oldName} → {newName}")
                stats["renamed"] += 1
                continue

            try:
                entry.rename(newPath)
                logger.action(f"renamed torrent: {oldName} → {newName}")
                stats["renamed"] += 1
            except FileExistsError:
                logger.error(f"target already exists, skipping: {newName}")
                stats["errors"] += 1
            except PermissionError:
                logger.error(f"permission denied renaming: {oldName}")
                stats["errors"] += 1
            except Exception as e:
                logger.error(f"error renaming {oldName}: {e}")
                stats["errors"] += 1

        logger.done("clean torrent names complete")
        return stats
