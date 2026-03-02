#!/usr/bin/env python3
"""
Organise My Video
Moves video files from a staging directory to organized storage locations.
Movies:    /mnt/movie<n>/Title (Year)/
TV Shows: /mnt/video<n>/TV/Show Name/Season NN/
"""

import os
import sys
import re
import shutil
import argparse
import logging
import datetime

from pathlib import Path
from typing import List, Tuple, Optional

from organiseMyProjects.logUtils import getLogger, drawBox # type: ignore

# Module-level logger used by class methods; replaced with runtime-configured logger in main().
logger = getLogger("organiseMyVideo")

# Video file extensions to process
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg"}

# Known torrent/index prefixes to strip from file and directory names
PREFIX_PATTERNS = [
    r"^\s*www\.UIndex\.org\s*-\s*",
    r"^\s*www\.Torrenting\.com\s*-\s*",
]

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
                    if re.match(r"movie\d*", item.name):
                        movieDirs.append(item)
                        logger.value("found movie storage", item)
                    elif re.match(r"video\d*", item.name):
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
                    logger.value("found existing movie directory",item)
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
                    logger.value("found existing TV show directory", item)
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
            rawName = input(f"Enter new name (space for default, blank/'quit' to skip): ")
            if not rawName:
                return None
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
            logger.action(f"would move to: {destFile}")
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
            logger.action(f"would move to: {destFile}")
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

        combinedRegex = re.compile("|".join(PREFIX_PATTERNS), re.IGNORECASE)

        for entry in sorted(self.sourceDir.iterdir()):
            oldName = entry.name
            if not combinedRegex.match(oldName):
                continue

            newName = combinedRegex.sub("", oldName, count=1).strip()

            if not newName or newName == oldName:
                logger.value("skipped (no change)", oldName)
                stats["skipped"] += 1
                continue

            newPath = self.sourceDir / newName

            if self.dryRun:
                logger.action(f"would rename: {oldName} → {newName}")
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

        for subDir in sorted(self.sourceDir.iterdir()):
            if not subDir.is_dir():
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
        
        # Get all video files
        videoFiles = [
            f for f in self.sourceDir. iterdir()
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
        summary = f"""
SUMMARY
Movies moved:   {stats['movies']}
TV shows moved: {stats['tv']}
Skipped:        {stats['skipped']}
Errors:         {stats['errors']}
"""
        drawBox(summary)
        logger.value("processing complete", stats)


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
        logger.info("dry-run mode (no changes will be made) — use --confirm to execute")
    else:
        logger.info("confirm mode — changes will be made")
    
    # Create organizer and run the requested mode
    organizer = VideoOrganizer(sourceDir=args.source, dryRun=dryRun)

    if args.clean:
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