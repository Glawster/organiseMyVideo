#!/usr/bin/env python3
"""
Organise My Video
Moves video files from a staging directory to organized storage locations.
Movies:    /mnt/movie<n>/Title (Year)/  or  /mnt/myPictures/Title (Year)/
TV Shows: /mnt/video<n>/TV/Show Name/Season NN/  or  /mnt/myVideo/TV/Show Name/Season NN/
"""

import os
import sys
import re
import json
import shutil
import getpass
import argparse
import logging
import datetime
import urllib.parse
import urllib.request

from pathlib import Path
from typing import List, Tuple, Optional

from organiseMyProjects.logUtils import getLogger, drawBox # type: ignore

# Playwright is an optional dependency used only by --grok.  We import it at
# module level so tests can patch ``organiseMyVideo.sync_playwright``.
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except ImportError:
    sync_playwright = None  # type: ignore

# Module-level logger used by class methods; replaced with runtime-configured logger in main().
logger = getLogger("organiseMyVideo")

# Video file extensions to process
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg"}
GROK_MEDIA_EXTENSIONS = {".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
GROK_USER_CONTENT_DOMAINS = {"imagine-public.x.ai", "images-public.x.ai"}
GROK_CREDENTIALS_FILE = Path.home() / ".config" / "organiseMyVideo" / "grokCredentials.json"
# Browser launch arguments that suppress Playwright's automation fingerprint.
# Without these, X.ai's sign-in page detects the automated browser and returns
# 403 on background API calls before the user can log in.
_PLAYWRIGHT_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled"]
# Realistic Chrome user-agent used for all Playwright contexts.  Playwright's
# default headless UA contains "HeadlessChrome" which bot-detection heuristics
# flag immediately.
_PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
# JavaScript snippet injected into every page of every context to remove the
# navigator.webdriver property that Playwright exposes by default.
_PLAYWRIGHT_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
# Playwright storage-state file (cookies + localStorage) persisted after login.
# When this file exists the browser starts already authenticated and no
# username/password interaction is needed.  Delete this file to force a fresh
# login (e.g. after a session expires or credentials change).
GROK_SESSION_FILE = Path.home() / ".config" / "organiseMyVideo" / "grokSession.json"

# Known torrent/index prefixes to strip from file and directory names
PREFIX_PATTERNS = [
    r"^\s*www\.UIndex\.org\s*-\s*",
    r"^\s*www\.Torrenting\.com\s*-\s*",
]

# Compiled regex combining all known prefixes (built once at module load)
_PREFIX_REGEX = re.compile("|".join(PREFIX_PATTERNS), re.IGNORECASE)

class VideoOrganizer:
    """Main class for organizing video files into structured directories."""
    
    def __init__(self, sourceDir:  str = "/mnt/video2/toFile", dryRun: bool = True):
        """
        Initialize the video organizer.
        
        Args:
            sourceDir: Source directory containing files to organize
            dryRun: If True, show what would be done without making changes
        """
        self.sourceDir = Path(sourceDir)
        self.dryRun = dryRun
        
    def scanStorageLocations(self) -> Tuple[List[Path], List[Path]]:
        """
        Scan system for movie and video storage locations.
        
        Returns:
            Tuple of (movie_directories, tv_directories)
        """
        logger.info("scanning for storage locations...")
        
        movieDirs = []
        videoDirs = []
        
        # Scan for /mnt/movie<n> and /mnt/video<n> directories
        mntPath = Path("/mnt")
        if mntPath.exists():
            for item in mntPath.iterdir():
                if item.is_dir():
                    if re.match(r"movie\d*$", item.name):
                        movieDirs.append(item)
                        logger.value("found movie storage", item)
                    elif re.match(r"myPictures$", item.name):
                        # Use Movies subdirectory if present, otherwise use root
                        moviesSubDir = item / "Movies"
                        movieStorage = moviesSubDir if moviesSubDir.exists() else item
                        movieDirs.append(movieStorage)
                        logger.value("found movie storage", movieStorage)
                    elif re.match(r"video\d*$|myVideo$", item.name):
                        # Look for TV subdirectory
                        tvDir = item / "TV"
                        if tvDir.exists():
                            videoDirs.append(tvDir)
                            logger.value("found TV storage", tvDir)
        
        logger.info(f"storage scan complete: {len(movieDirs)} movie, {len(videoDirs)} TV locations")
        return sorted(movieDirs), sorted(videoDirs)
    
    def parseTvFilename(self, filename: str) -> Optional[dict]:
        """
        Parse TV show filename to extract show name, season, and episode.
        
        Expected format: show. SnnEnn.title.ext
        
        Args:
            filename: Name of the file to parse
            
        Returns:
            Dictionary with parsed info or None if parsing failed
        """
        # Pattern for SnnEnn format
        pattern = r"^(.+?)\.S(\d+)E(\d+)\..*\.(\w+)$"
        match = re.match(pattern, filename, re.IGNORECASE)
        
        if match:
            showName = match.group(1).replace(".", " ").strip()
            season = int(match.group(2))
            episode = int(match.group(3))
            extension = match.group(4)
            
            return {
                "showName": showName,
                "season": season,
                "episode": episode,
                "extension": extension,
                "type": "tv"
            }
        
        return None
    
    def parseMovieFilename(self, filename: str) -> Optional[dict]:
        """
        Parse movie filename to extract title and year.
        
        Expected format variations:  Title (Year).ext, Title.Year.ext, etc.
        
        Args:
            filename: Name of the file to parse
            
        Returns: 
            Dictionary with parsed info or None if parsing failed
        """
        # Remove extension
        nameWithoutExt = os.path.splitext(filename)[0]
        extension = os.path.splitext(filename)[1]
        
        # Pattern for "Title (Year)" or "Title.Year"
        pattern1 = r"^(.+? )\s*[\(\[]\s*(\d{4})\s*[\)\]]"
        pattern2 = r"^(.+?)[\.\s]+(\d{4})"
        
        match = re.match(pattern1, nameWithoutExt)
        if not match:
            match = re. match(pattern2, nameWithoutExt)
        
        if match:
            title = match. group(1).replace(".", " ").strip()
            year = match.group(2)
            
            return {
                "title": title,
                "year": year,
                "extension": extension,
                "type": "movie"
            }
        
        return None
    
    def findExistingMovieDir(self, title: str, year: str, movieDirs: List[Path]) -> Optional[Path]:
        """
        Search for existing movie directory matching title and year.
        
        Args:
            title: Movie title
            year: Release year
            movieDirs: List of movie storage directories to search
            
        Returns: 
            Path to existing directory or None
        """
        searchPattern = f"{title} ({year})"
        
        for movieRoot in movieDirs:
            for item in movieRoot.iterdir():
                if item.is_dir() and item.name.lower() == searchPattern.lower():
                    logger.value("found existing movie",item)
                    return item
        
        return None
    
    def findExistingTvShowDir(self, showName: str, videoDirs: List[Path]) -> Optional[Path]:
        """
        Search for existing TV show directory. 
        
        Args:
            showName: Name of the TV show
            videoDirs: List of TV storage directories to search
            
        Returns:
            Path to existing directory or None
        """
        for tvRoot in videoDirs:
            for item in tvRoot.iterdir():
                if item.is_dir() and item.name.lower() == showName.lower():
                    logger.value("found existing TV show", item)
                    return item
        
        return None
    
    def getStorageWithMostSpace(self, storageDirs: List[Path]) -> Optional[Path]:
        """
        Return the storage location with the most free space. 
        
        Args:
            storageDirs: List of storage directories to check
            
        Returns:
            Path with most free space or None
        """
        if not storageDirs:
            return None
        
        maxSpace = -1
        bestDir = None
        
        for storageDir in storageDirs: 
            try:
                stat = os.statvfs(storageDir)
                freeSpace = stat.f_bavail * stat.f_frsize
                if freeSpace > maxSpace: 
                    maxSpace = freeSpace
                    bestDir = storageDir
            except Exception as e:
                logger.warning(f"could not check space for {storageDir}: {e}")
                continue
        
        if bestDir:
            logger.value("selected storage with most space", bestDir)
        
        return bestDir
    
    def promptUserConfirmation(self, filename: str, defaultName: str, fileType: str) -> Optional[dict]:
        """
        Prompt user to confirm or correct the detected name.

        Args:
            filename: Original filename
            defaultName:  Detected name to confirm
            fileType: Type of file ('tv' or 'movie')

        Returns:
            dict with 'name' and 'type' keys, or None to skip this item.
            'type' may differ from fileType when the user switches category.
        """
        if fileType == "tv":
            prompt = f"\nTV Show detected: '{defaultName}'\nIs this correct?  (y/n/q/t/m or enter new name): "
        else:
            prompt = f"\nMovie detected: '{defaultName}'\nIs this correct? (y/n/q/t/m or enter new name): "

        response = input(prompt).strip()

        if response.lower() in ["y", "yes", ""]:
            return {"name": defaultName, "type": fileType}
        elif response.lower() in ["n", "no"]:
            rawName = input(f"Enter new name (blank for default, enter 'quit' to skip): ")
            if not rawName:
                return {"name": defaultName, "type": fileType}
            if rawName.strip().lower() == "quit":
                return None
            strippedName = rawName.strip()
            if not strippedName:
                return {"name": defaultName, "type": fileType}
            return {"name": strippedName, "type": fileType}
        elif response.lower() in ["q", "quit"]:
            logger.info("user requested to quit")
            sys.exit(0)
        elif response.lower() == "t":
            showName = input(f"  Enter show name (default: {defaultName}): ").strip()
            return {"name": showName if showName else defaultName, "type": "tv"}
        elif response.lower() == "m":
            title = input(f"  Enter movie title (default: {defaultName}): ").strip()
            return {"name": title if title else defaultName, "type": "movie"}
        else:
            return {"name": response, "type": fileType}
    
    def moveMovie(self, sourceFile: Path, movieInfo: dict, movieDirs: List[Path],
                  videoDirs: Optional[List[Path]] = None, interactive: bool = True) -> bool:
        """
        Move movie file to appropriate location.

        Args:
            sourceFile: Source file path
            movieInfo:  Parsed movie information
            movieDirs: List of movie storage directories
            videoDirs: Optional list of TV storage directories (used when switching type)
            interactive: Whether to prompt user for confirmation

        Returns:
            True if successful, False otherwise
        """
        title = movieInfo["title"]
        year = movieInfo["year"]

        logger.value("processing movie", sourceFile.name)

        # Check if user confirmation needed
        if interactive:
            result = self.promptUserConfirmation(
                sourceFile.name,
                f"{title} ({year})",
                "movie"
            )
            if result is None:
                logger.info(f"skipping: {sourceFile.name}")
                return False
            if result["type"] == "tv":
                # User wants to process as TV show instead
                season = input("  Season number (default 1): ").strip()
                season = int(season) if season.isdigit() else 1
                tvInfo = {
                    "showName": result["name"],
                    "season": season,
                    "episode": 0,
                    "extension": sourceFile.suffix,
                    "type": "tv",
                }
                if videoDirs:
                    return self.moveTvShow(sourceFile, tvInfo, videoDirs, interactive=False)
                logger.error("no TV storage locations available for type switch")
                return False
            confirmedTitle = result["name"]
            # Re-parse if user provided different input
            if confirmedTitle != f"{title} ({year})":
                # Try to extract year from new input
                match = re.match(r"^(.+?)\s*[\(\[]\s*(\d{4})\s*[\)\]]", confirmedTitle)
                if match:
                    title = match.group(1).strip()
                    year = match.group(2)
                else:
                    title = confirmedTitle
        
        # Find existing directory or choose storage location
        existingDir = self.findExistingMovieDir(title, year, movieDirs)
        
        if existingDir:
            destDir = existingDir
        else:
            # Create new directory in storage with most space
            storage = self.getStorageWithMostSpace(movieDirs)
            if not storage:
                logger.error("No movie storage locations found")
                return False
            
            destDir = storage / f"{title} ({year})"
        
        destFile = destDir / sourceFile.name
        
        logger.value("movie",sourceFile.name)
        logger.value("  ->", destFile)
        
        if self.dryRun:
            logger.action(f"move to: {destFile}")
            return True
        
        try:
            destDir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sourceFile), str(destFile))
            logger.action(f"movie moved successfully: {destFile}")
            return True
        except Exception as e:
            logger.error(f"Failed to move movie: {e}")
            return False
    
    def moveTvShow(self, sourceFile: Path, tvInfo: dict, videoDirs: List[Path],
                   movieDirs: Optional[List[Path]] = None, interactive: bool = True) -> bool:
        """
        Move TV show file to appropriate location.

        Args:
            sourceFile: Source file path
            tvInfo: Parsed TV show information
            videoDirs: List of TV storage directories
            movieDirs: Optional list of movie storage directories (used when switching type)
            interactive:  Whether to prompt user for confirmation

        Returns:
            True if successful, False otherwise
        """
        showName = tvInfo["showName"]
        season = tvInfo["season"]

        logger.value("processing TV show", sourceFile.name)

        # Check if user confirmation needed
        if interactive:
            result = self.promptUserConfirmation(
                sourceFile.name,
                showName,
                "tv"
            )
            if result is None:
                logger.info(f"skipping: {sourceFile.name}")
                return False
            if result["type"] == "movie":
                # User wants to process as movie instead
                year = input("  Year (e.g. 2020): ").strip()
                movieInfo = {
                    "title": result["name"],
                    "year": year if year else "Unknown",
                    "extension": sourceFile.suffix,
                    "type": "movie",
                }
                if movieDirs:
                    return self.moveMovie(sourceFile, movieInfo, movieDirs, interactive=False)
                logger.error("no movie storage locations available for type switch")
                return False
            showName = result["name"]
        
        # Find existing show directory or choose storage location
        existingShowDir = self.findExistingTvShowDir(showName, videoDirs)
        
        if existingShowDir:
            showDir = existingShowDir
        else:
            # Create new show directory in storage with most space
            storage = self.getStorageWithMostSpace(videoDirs)
            if not storage:
                logger.error("No TV storage locations found")
                return False
            
            showDir = storage / showName
        
        # Create season directory
        seasonDir = showDir / f"Season {season:02d}"
        destFile = seasonDir / sourceFile.name
        
        logger.value("TV Show", sourceFile.name)
        logger.value("  ->", destFile)
        
        if self.dryRun:
            logger.action(f"move to: {destFile}")
            return True
        
        try:
            seasonDir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sourceFile), str(destFile))
            logger.action(f"TV show moved successfully: {destFile}")
            return True
        except Exception as e: 
            logger.error(f"Failed to move TV show: {e}")
            return False
    
    def _isSampleLikeFolder(self, path: Path) -> bool:
        """Return True if the folder name indicates it is a sample/extras folder."""
        return "sample" in path.name.lower()

    def _hasRealVideoContent(self, folder: Path) -> bool:
        """
        Return True if folder contains real video files outside of sample-like sub-folders.

        Args:
            folder: Directory to inspect recursively
        """
        for item in folder.rglob("*"):
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                # Ignore files that live inside a sample-like folder
                relativeParts = item.relative_to(folder).parts
                if any(self._isSampleLikeFolder(Path(part)) for part in relativeParts[:-1]):
                    continue
                return True
        return False

    def cleanNames(self) -> dict:
        """
        Strip known torrent/index prefixes from file and directory names in the source directory.

        Returns:
            Dictionary with counts: {'renamed': int, 'skipped': int, 'errors': int}
        """
        logger.doing("starting clean of prefixed names")

        stats = {"renamed": 0, "skipped": 0, "errors": 0}

        if not self.sourceDir.exists():
            logger.error(f"source directory does not exist: {self.sourceDir}")
            return stats

        for entry in sorted(self.sourceDir.iterdir()):
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
                logger.action(f"rename: {oldName} → {newName}")
                stats["renamed"] += 1
                continue

            try:
                entry.rename(newPath)
                logger.action(f"renamed: {oldName} → {newName}")
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

        logger.done("clean names complete")
        return stats

    def cleanEmptyFolders(self) -> dict:
        """
        Remove sub-folders in the source directory that contain no real video files.

        Folders whose only video content is inside sample-like sub-folders are
        treated as empty and removed together with their contents.

        Returns:
            Dictionary with counts: {'removed': int, 'skipped': int, 'errors': int}
        """
        logger.doing("starting clean of empty folders")

        stats = {"removed": 0, "skipped": 0, "errors": 0}

        if not self.sourceDir.exists():
            logger.error(f"source directory does not exist: {self.sourceDir}")
            return stats

        for subDir in sorted(self.sourceDir.rglob("*"), key=lambda p: (len(p.parts), str(p)), reverse=True):
            if not subDir.exists() or not subDir.is_dir():
                continue

            if self._hasRealVideoContent(subDir):
                logger.value("keeping (has video content)", subDir.name)
                stats["skipped"] += 1
                continue

            logger.action(f"removing empty folder: {subDir}")
            if self.dryRun:
                stats["removed"] += 1
                continue

            try:
                shutil.rmtree(str(subDir))
                logger.action(f"removed: {subDir}")
                stats["removed"] += 1
            except Exception as e:
                logger.error(f"failed to remove {subDir}: {e}")
                stats["errors"] += 1

        logger.done(f"clean complete")
        return stats

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

    def processFiles(self, interactive: bool = True):
        """
        Process all video files in the source directory.
        
        Args:
            interactive:  Whether to prompt user for ambiguous files
        """
        logger.doing("starting file processing")
        
        if not self.sourceDir.exists():
            logger.error(f"Source directory does not exist: {self.sourceDir}")
            return
        
        # Scan for storage locations
        logger.doing("scanning for storage locations...")
        movieDirs, videoDirs = self.scanStorageLocations()
        
        logger.info(f"found {len(movieDirs)} movie storage location(s) and {len(videoDirs)} TV storage location(s)")
        for d in movieDirs:
            logger.value("  - ", d)
        
        logger.info(f"found {len(videoDirs)} TV storage location(s):")
        for d in videoDirs:
            logger.value("  - ", d)
        
        if not movieDirs:
            logger.error("No Movie storage locations found")
        if not videoDirs:   
            logger.error("No TV storage locations found!")
            return
        
        # Get all video files (including those in subdirectories)
        videoFiles = [
            f for f in self.sourceDir.rglob("*")
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        ]
        
        if not videoFiles:
            logger.value("no video files found in", self.sourceDir)
            return
        
        logger.info(f"found {len(videoFiles)} video file(s) to process")
        
        # Process each file
        stats = {"movies": 0, "tv": 0, "skipped": 0, "errors":  0}
        
        for videoFile in videoFiles:
            # Try parsing as TV show first
            tvInfo = self.parseTvFilename(videoFile.name)
            if tvInfo and videoDirs:
                if self.moveTvShow(videoFile, tvInfo, videoDirs, movieDirs=movieDirs, interactive=interactive):
                    stats["tv"] += 1
                else:
                    stats["errors"] += 1
                continue
            
            # Try parsing as movie
            movieInfo = self.parseMovieFilename(videoFile.name)
            if movieInfo and movieDirs:
                if self.moveMovie(videoFile, movieInfo, movieDirs, videoDirs=videoDirs, interactive=interactive):
                    stats["movies"] += 1
                else: 
                    stats["errors"] += 1
                continue
            
            # Could not determine type
            logger.warning(f"could not parse filename: {videoFile.name}")
            logger.value("skipped:", videoFile.name)
            logger.info("could not determine if movie or TV show")
            
            if interactive:
                fileType = input("  Is this a (m)ovie or (t)v show? (or 's' to skip): ").strip().lower()
                
                if fileType == "m" and movieDirs:
                    # Prompt for movie info
                    title = input(f"  Movie title (default: {videoFile.stem}): ").strip()
                    title = title if title else videoFile. stem
                    year = input("  Year:  ").strip()
                    
                    if year:
                        movieInfo = {
                            "title": title,
                            "year": year,
                            "extension": videoFile.suffix,
                            "type": "movie"
                        }
                        if self.moveMovie(videoFile, movieInfo, movieDirs, False):
                            stats["movies"] += 1
                        else: 
                            stats["errors"] += 1
                        continue
                
                elif fileType == "t" and videoDirs:
                    # Prompt for TV show info
                    show = input(f"  Show name (default: {videoFile.stem}): ").strip()
                    show = show if show else videoFile.stem
                    season = input("  Season number: ").strip()
                    
                    if season and season.isdigit():
                        tvInfo = {
                            "showName": show,
                            "season": int(season),
                            "episode": 0,
                            "extension": videoFile.suffix,
                            "type": "tv"
                        }
                        if self.moveTvShow(videoFile, tvInfo, videoDirs, False):
                            stats["tv"] += 1
                        else: 
                            stats["errors"] += 1
                        continue
            
            stats["skipped"] += 1
        
        # Print summary
        summary = f"""SUMMARY
Movies moved:   {stats['movies']}
TV shows moved: {stats['tv']}
Skipped:        {stats['skipped']}
Errors:         {stats['errors']}
"""
        drawBox(summary)
        logger.value("processing complete", stats)

    def _extractMediaUrlsFromHtml(self, html: str) -> List[str]:
        """Extract likely media URLs from Grok saved-image HTML."""
        mediaUrls = set()
        for match in re.findall(r'https?://[^\s"\']+', html, re.IGNORECASE):
            parsed = urllib.parse.urlparse(match)
            ext = Path(parsed.path).suffix.lower()
            if ext in GROK_MEDIA_EXTENSIONS:
                mediaUrls.add(match)
        return sorted(mediaUrls)

    def _extractMediaUrlsFromPage(self, page) -> List[str]:
        """Extract the user's saved Imagine media URLs from a live Playwright page.

        Uses DOM querying to read ``src`` attributes directly from ``<img>`` and
        ``<video>``/``<source>`` elements rather than regex-scanning the full HTML.
        Results are filtered to the known Grok user-content CDN domains so that
        system UI icons, marketing images, and promotional videos embedded in the
        page template are excluded.
        """
        rawUrls: List[str] = page.eval_on_selector_all(
            "img[src], video[src], source[src]",
            "els => els.map(el => el.src)",
        )
        mediaUrls = set()
        for url in rawUrls:
            if not url:
                continue
            parsed = urllib.parse.urlparse(url)
            ext = Path(parsed.path).suffix.lower()
            if ext not in GROK_MEDIA_EXTENSIONS:
                continue
            hostname = parsed.hostname or ""
            if hostname in GROK_USER_CONTENT_DOMAINS:
                mediaUrls.add(url)
        return sorted(mediaUrls)

    def _collectPostUrls(self, page) -> List[str]:
        """Return all unique ``/imagine/post/{uuid}`` URLs found on the current page.

        Queries the live DOM for anchor elements whose ``href`` contains
        ``/imagine/post/`` and returns a deduplicated, sorted list of absolute
        URLs.  Empty strings and duplicates are removed automatically.  Called
        on the saved-gallery page so that the scraper can then visit each post
        page individually to capture full-resolution media (including videos
        that are not loaded as part of the thumbnail grid).
        """
        hrefs: List[str] = page.eval_on_selector_all(
            "a[href*='/imagine/post/']",
            "els => els.map(el => el.href)",
        )
        return sorted({h for h in hrefs if h})

    def _isGrokMediaResponse(self, url: str, contentType: str) -> bool:
        """Return True when a Playwright network response should be captured as user media.

        Only responses from the known Grok user-content CDN domains
        (:data:`GROK_USER_CONTENT_DOMAINS`) are considered user-generated media.
        Everything else — the app's own domain, third-party CDNs hosting profile
        pictures, analytics pixels, ad networks, etc. — is excluded.

        A response qualifies when BOTH of the following are true:

        * The hostname is in :data:`GROK_USER_CONTENT_DOMAINS`.
        * The URL path has a recognised media extension **or** the
          ``Content-Type`` header indicates an image or video.

        This is used by the ``page.on("response", ...)`` listener inside
        :meth:`scrapeGrokSavedMedia` and is extracted here so it can be tested
        without a live Playwright session.
        """
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname or ""
        if not hostname or hostname not in GROK_USER_CONTENT_DOMAINS:
            return False
        ext = Path(parsed.path).suffix.lower()
        return ext in GROK_MEDIA_EXTENSIONS or contentType.startswith(("image/", "video/"))

    def _downloadMediaFiles(self, mediaUrls: List[str], playwrightContext=None) -> dict:
        """Download URLs into ~/Downloads/Grok and return download stats.

        Args:
            mediaUrls: List of media URLs to download.
            playwrightContext: An active Playwright ``BrowserContext``.  When
                provided, downloads are made via the authenticated browser
                session so that session cookies are included in each request,
                avoiding 403 responses from CDN URLs that require authentication.
                Falls back to ``urllib`` when *None*.
        """
        stats = {"downloaded": 0, "skipped": 0, "errors": 0}
        destDir = Path.home() / "Downloads" / "Grok"
        destDir.mkdir(parents=True, exist_ok=True)

        for mediaUrl in mediaUrls:
            parsed = urllib.parse.urlparse(mediaUrl)
            filename = Path(parsed.path).name or f"grok_media_{stats['downloaded'] + stats['errors'] + 1}"
            dest = destDir / filename

            if dest.exists():
                logger.value("grok media already exists, skipping", dest)
                stats["skipped"] += 1
                continue

            if self.dryRun:
                logger.action(f"would download grok media: {mediaUrl} -> {dest}")
                stats["downloaded"] += 1
                continue

            try:
                if playwrightContext is not None:
                    response = playwrightContext.request.get(
                        mediaUrl,
                        headers={"Referer": "https://grok.com/"},
                    )
                    if not response.ok:
                        raise RuntimeError(f"HTTP {response.status}")
                    dest.write_bytes(response.body())
                else:
                    with urllib.request.urlopen(mediaUrl, timeout=30) as response:
                        dest.write_bytes(response.read())
                logger.action(f"downloaded grok media: {dest}")
                stats["downloaded"] += 1
            except Exception as e:
                logger.error(f"failed downloading {mediaUrl}: {e}")
                stats["errors"] += 1

        return stats

    def _loadOrPromptGrokCredentials(
        self, credentialsFile: Path = GROK_CREDENTIALS_FILE
    ) -> tuple:
        """
        Load Grok credentials from a JSON file, prompting if not found.

        If the file exists and contains both ``username`` and ``password``,
        those values are returned directly.  Otherwise the user is prompted
        interactively (password entry is hidden) and the credentials are saved
        to the file for future use.

        Args:
            credentialsFile: Path to the JSON credentials file.

        Returns:
            Tuple of (username, password).
        """
        if credentialsFile.exists():
            try:
                data = json.loads(credentialsFile.read_text())
                username = data.get("username", "")
                password = data.get("password", "")
                if username and password:
                    logger.value("loaded grok credentials from", str(credentialsFile))
                    return username, password
            except Exception as e:
                logger.error(f"failed to load credentials from {credentialsFile}: {e}")

        logger.info("grok credentials not found - please enter your credentials")
        username = input("Grok username (email): ").strip()
        password = getpass.getpass("Grok password: ")

        if not username or not password:
            raise RuntimeError("username and password are required for --grok")

        credentialsFile.parent.mkdir(parents=True, exist_ok=True)
        credentialsFile.write_text(
            json.dumps({"username": username, "password": password}, indent=2)
        )
        credentialsFile.chmod(0o600)
        logger.value("saved grok credentials to", str(credentialsFile))
        return username, password

    def _autofillLoginPage(self, page, username: str) -> None:
        """Pre-fill the email field on the X.ai sign-in form.

        Only the email address is filled automatically.  Clicking Next,
        entering the password, and clicking Login are all intentionally left
        for the user so that Cloudflare Turnstile's human-verification
        challenge is triggered by real human navigation rather than automated
        page transitions — automating those clicks causes Turnstile error
        600010 (unsupported browser / bot detected).

        Silently degrades to a warning log if the email field is not found
        within the timeout so the user can still log in manually.

        Args:
            page: Playwright Page instance on the X.ai sign-in page.
            username: Email address to pre-fill.
        """
        EMAIL_SELECTOR = "input[type='email'], input[autocomplete='username'], input[name='email']"
        SELECTOR_TIMEOUT = 10_000
        try:
            page.wait_for_selector(EMAIL_SELECTOR, timeout=SELECTOR_TIMEOUT)
            page.fill(EMAIL_SELECTOR, username)
            logger.info("email pre-filled — please click Next, enter your password, and log in")
        except Exception as e:
            # Broad catch is intentional: Playwright raises various exception
            # types depending on the failure (timeout, missing element, navigation
            # error).  The helper is best-effort; any failure falls back to fully
            # manual entry so the user is never blocked.
            logger.warning(f"auto-fill of login form failed ({e}); please log in manually")

    def resetGrokConfig(
        self,
        sessionFile: Path = GROK_SESSION_FILE,
        credentialsFile: Path = GROK_CREDENTIALS_FILE,
    ) -> dict:
        """Delete saved Grok session and credentials config files.

        Removes *sessionFile* and *credentialsFile* if they exist so that the
        next ``--grok`` run will prompt for a fresh manual login.

        Args:
            sessionFile: Path to the Playwright storage-state file.
            credentialsFile: Path to the JSON credentials file.

        Returns:
            Dict with keys ``deleted`` (list of deleted paths) and
            ``notFound`` (list of paths that did not exist).
        """
        deleted = []
        notFound = []
        for path in (sessionFile, credentialsFile):
            if path.exists():
                if not self.dryRun:
                    path.unlink()
                logger.action(f"deleted Grok config file: {path}")
                deleted.append(str(path))
            else:
                logger.info(f"Grok config file not found (skipping): {path}")
                notFound.append(str(path))
        return {"deleted": deleted, "notFound": notFound}

    def scrapeGrokSavedMedia(
        self,
        sessionFile: Path = GROK_SESSION_FILE,
        credentialsFile: Path = GROK_CREDENTIALS_FILE,
    ) -> dict:
        """Log into Grok and scrape saved Imagine media, downloading to ~/Downloads/Grok.

        Authentication uses Playwright ``storage_state`` (cookies + localStorage)
        persisted at *sessionFile* (default :data:`GROK_SESSION_FILE`).

        * **If the session file exists** the browser starts already authenticated
          and no username/password interaction is needed.

        * **If the session file is absent** a visible browser window opens, saved
          credentials from *credentialsFile* are pre-filled into the sign-in form,
          and the user just needs to complete the login (e.g. click Login and
          solve any Cloudflare challenge).  The resulting session is saved so
          subsequent runs are instant.

        * **If the saved session has expired** (detected when Grok redirects the
          browser away from ``/imagine/saved`` rather than loading the page), the
          stale session file is deleted automatically, credentials are pre-filled,
          and the user is prompted to log in again via a visible browser window.

        After authentication the scrape runs in two phases:

        1. **Gallery phase** — navigates to ``grok.com/imagine/saved`` and
           scrolls to the bottom so that all post thumbnails are rendered.
           Collects every ``/imagine/post/{uuid}`` link found in the DOM.

        2. **Post phase** — visits each post page in turn and collects media
           via two complementary strategies:

           a. Network-response interception (fires for any resource the browser
              actually fetches from :data:`GROK_USER_CONTENT_DOMAINS`).

           b. DOM query (:meth:`_extractMediaUrlsFromPage`) reads ``<video
              src>`` and ``<source src>`` attributes directly — essential
              because video elements only fetch their media when they play, so
              the response listener alone misses them.

        All captured media URLs are then downloaded to ``~/Downloads/Grok``.
        """
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is required for --grok: "
                "pip install playwright && playwright install chromium"
            )

        logger.doing("starting Grok scrape for saved Imagine media")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=_PLAYWRIGHT_BROWSER_ARGS)

            # ------------------------------------------------------------------
            # Authentication — prefer a saved session so that the full login
            # flow (which may involve OAuth redirects, CAPTCHA, or 2FA) is only
            # required once.
            # ------------------------------------------------------------------
            if sessionFile.exists():
                try:
                    logger.info("loading saved Grok session")
                    context = browser.new_context(
                        storage_state=str(sessionFile),
                        user_agent=_PLAYWRIGHT_USER_AGENT,
                    )
                    context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                except Exception as e:
                    logger.warning(f"saved session could not be loaded ({e}); falling back to fresh login")
                    sessionFile.unlink(missing_ok=True)
                    context = None
            else:
                context = None

            if context is None:
                # No valid session — load credentials, relaunch as non-headless,
                # pre-fill the sign-in form, and wait for the user to complete login
                # (e.g. solve any Cloudflare Turnstile challenge and click Login).
                username, password = self._loadOrPromptGrokCredentials(
                    credentialsFile=credentialsFile
                )
                browser.close()
                browser = playwright.chromium.launch(headless=False, args=_PLAYWRIGHT_BROWSER_ARGS)
                context = browser.new_context(user_agent=_PLAYWRIGHT_USER_AGENT)
                context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                page = context.new_page()
                page.goto("https://grok.com", wait_until="domcontentloaded")
                self._autofillLoginPage(page, username)
                print(
                    "\nA browser window has opened and your email has been pre-filled.\n"
                    "Please click Next, enter your password, complete any verification,\n"
                    "then press Enter here to continue...",
                    flush=True,
                )
                input()

                # Persist session so the login form is never needed again.
                sessionFile.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(sessionFile))
                if sessionFile.exists():
                    sessionFile.chmod(0o600)
                logger.value("saved Grok session to", str(sessionFile))
            else:
                page = context.new_page()

            capturedUrls: set = set()

            def _onResponse(response) -> None:
                contentType = response.headers.get("content-type", "")
                if self._isGrokMediaResponse(response.url, contentType):
                    capturedUrls.add(response.url)

            def _navigateToSaved(pg) -> None:
                """Attach the response listener and navigate to /imagine/saved."""
                pg.on("response", _onResponse)
                pg.goto("https://grok.com/imagine/saved", wait_until="domcontentloaded")
                pg.wait_for_timeout(2000)

            # ------------------------------------------------------------------
            # Phase 1: Gallery — scroll /imagine/saved to render all post cards
            # and collect their individual post-page links.
            #
            # Stall detection tracks the number of post links visible in the
            # DOM (not capturedUrls) because gallery thumbnails may not come
            # from GROK_USER_CONTENT_DOMAINS, so capturedUrls could stay at
            # zero and cause the scroll to abort after just two passes.
            # ------------------------------------------------------------------
            _navigateToSaved(page)

            # Detect session expiry: an expired (or invalid) session causes
            # Grok to redirect the browser to the login page instead of loading
            # /imagine/saved.  When that happens, wipe the stale session file,
            # relaunch the browser as visible, pre-fill credentials, and let
            # the user complete login.
            if urllib.parse.urlparse(page.url).path != "/imagine/saved":
                logger.warning(
                    f"session appears expired (redirected to {page.url!r}); "
                    "deleting saved session and switching to manual login"
                )
                context.close()
                browser.close()
                sessionFile.unlink(missing_ok=True)
                username, password = self._loadOrPromptGrokCredentials(
                    credentialsFile=credentialsFile
                )
                browser = playwright.chromium.launch(headless=False, args=_PLAYWRIGHT_BROWSER_ARGS)
                context = browser.new_context(user_agent=_PLAYWRIGHT_USER_AGENT)
                context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                page = context.new_page()
                page.goto("https://grok.com", wait_until="domcontentloaded")
                self._autofillLoginPage(page, username)
                print(
                    "\nA browser window has opened.\n"
                    "Your previous Grok session has expired and your email has been pre-filled.\n"
                    "Please click Next, enter your password, complete any verification,\n"
                    "then press Enter here to continue...",
                    flush=True,
                )
                input()
                sessionFile.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(sessionFile))
                if sessionFile.exists():
                    sessionFile.chmod(0o600)
                logger.value("saved Grok session to", str(sessionFile))
                _navigateToSaved(page)

            previousLinkCount = 0
            stallCount = 0
            for _ in range(20):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(900)
                currentLinkCount = len(self._collectPostUrls(page))
                if currentLinkCount == previousLinkCount:
                    stallCount += 1
                    if stallCount >= 2:
                        break
                else:
                    stallCount = 0
                previousLinkCount = currentLinkCount

            postUrls = self._collectPostUrls(page)
            logger.value("found Grok post pages", len(postUrls))

            # ------------------------------------------------------------------
            # Phase 2: Post pages — visit each post and collect media via two
            # complementary strategies:
            #
            # a) Network-response listener (_onResponse, already active) fires
            #    for any resource that the browser fetches from
            #    GROK_USER_CONTENT_DOMAINS while the page loads.
            #
            # b) DOM query (_extractMediaUrlsFromPage) reads <video src> and
            #    <source src> attributes directly.  This is essential because
            #    <video> elements do not start fetching their media until they
            #    play, so the response listener alone misses them.
            #
            # We wait for "networkidle" (not just "domcontentloaded") so that
            # the React app has time to finish its API call and render the
            # video elements into the DOM before we query them.
            # ------------------------------------------------------------------
            for i, postUrl in enumerate(postUrls, 1):
                logger.doing(f"scraping post {i}/{len(postUrls)}: {postUrl}")
                page.goto(postUrl, wait_until="networkidle")
                page.wait_for_timeout(1000)
                for url in self._extractMediaUrlsFromPage(page):
                    capturedUrls.add(url)

            page.remove_listener("response", _onResponse)
            mediaUrls = sorted(capturedUrls)
            logger.value("found Grok media URLs", len(mediaUrls))

            # Refresh the session on disk so it stays current.
            context.storage_state(path=str(sessionFile))

            if not postUrls:
                logger.warning(
                    "no posts found — check that you are logged in; "
                    f"if the session has expired, delete {sessionFile} and re-run"
                )

            downloadStats = self._downloadMediaFiles(mediaUrls, playwrightContext=context)
            browser.close()

        logger.done("Grok scrape complete")
        return {
            "postsFound": len(postUrls),
            "urlsFound": len(mediaUrls),
            **downloadStats,
        }


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
