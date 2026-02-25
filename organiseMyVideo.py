#!/usr/bin/env python3
"""
Organise My Video
Moves video files from a staging directory to organized storage locations.
Movies:    /mnt/movie<n>/Title (Year)/
TV Shows: /mnt/video<n>/TV/Show Name/Season NN/
"""

import os
import re
import shutil
import argparse
import logging
from pathlib import Path
from typing import List, Tuple, Optional

# Video file extensions to process
VIDEO_EXTENSIONS = {". mp4", ".mkv", ". avi", ".mov", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg"}

# Setup logging
logger = logging.getLogger(__name__)


def setupLogging(logLevel: str = "INFO"):
    """
    Configure logging with appropriate handlers and formatting.
    
    Args:
        logLevel:  Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, logLevel. upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("organiseMyVideo.log"),
            logging.StreamHandler()
        ]
    )


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
        logger.info("... scanning for storage locations")
        
        movieDirs = []
        videoDirs = []
        
        # Scan for /mnt/movie<n> and /mnt/video<n> directories
        mntPath = Path("/mnt")
        if mntPath.exists():
            for item in mntPath.iterdir():
                if item.is_dir():
                    if re.match(r"movie\d*", item.name):
                        movieDirs.append(item)
                        logger.info(f"... found movie storage: {item}")
                    elif re.match(r"video\d*", item.name):
                        # Look for TV subdirectory
                        tvDir = item / "TV"
                        if tvDir.exists():
                            videoDirs.append(tvDir)
                            logger. info(f"...found TV storage: {tvDir}")
        
        logger.info(f"...storage scan complete: {len(movieDirs)} movie, {len(videoDirs)} TV locations")
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
        pattern = r"^(. +?)\.S(\d+)E(\d+)\..*\. (\w+)$"
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
                    logger.info(f"...found existing movie directory: {item}")
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
                    logger.info(f"...found existing TV show directory: {item}")
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
                logger.warning(f"Could not check space for {storageDir}: {e}")
                continue
        
        if bestDir:
            logger.info(f"...selected storage with most space: {bestDir}")
        
        return bestDir
    
    def promptUserConfirmation(self, filename: str, defaultName: str, fileType: str) -> str:
        """
        Prompt user to confirm or correct the detected name.
        
        Args:
            filename: Original filename
            defaultName:  Detected name to confirm
            fileType: Type of file ('tv' or 'movie')
            
        Returns:
            Confirmed or corrected name
        """
        if fileType == "tv":
            prompt = f"\nTV Show detected: '{defaultName}'\nIs this correct?  (y/n or enter new name): "
        else:
            prompt = f"\nMovie detected: '{defaultName}'\nIs this correct? (y/n or enter new name): "
        
        response = input(prompt).strip()
        
        if response.lower() in ["y", "yes", ""]:
            return defaultName
        elif response.lower() in ["n", "no"]:
            newName = input(f"Enter correct {fileType} name: ").strip()
            return newName if newName else defaultName
        else:
            return response
    
    def moveMovie(self, sourceFile: Path, movieInfo: dict, movieDirs: List[Path], 
                  interactive: bool = True) -> bool:
        """
        Move movie file to appropriate location.
        
        Args:
            sourceFile: Source file path
            movieInfo:  Parsed movie information
            movieDirs: List of movie storage directories
            interactive: Whether to prompt user for confirmation
            
        Returns: 
            True if successful, False otherwise
        """
        title = movieInfo["title"]
        year = movieInfo["year"]
        
        logger.info(f"...processing movie: {sourceFile. name}")
        
        # Check if user confirmation needed
        if interactive:
            confirmedTitle = self.promptUserConfirmation(
                sourceFile.name,
                f"{title} ({year})",
                "movie"
            )
            # Re-parse if user provided different input
            if confirmedTitle != f"{title} ({year})":
                # Try to extract year from new input
                match = re.match(r"^(.+? )\s*[\(\[]\s*(\d{4})\s*[\)\]]", confirmedTitle)
                if match:
                    title = match.group(1).strip()
                    year = match. group(2)
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
        
        print(f"\nMovie:  {sourceFile.name}")
        print(f"  -> {destFile}")
        
        if self.dryRun:
            print("  [DRY RUN - no changes made]")
            logger.info(f"... dry run: would move to {destFile}")
            return True
        
        try:
            destDir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sourceFile), str(destFile))
            print("  ✓ Moved successfully")
            logger.info(f"...movie moved successfully: {destFile}")
            return True
        except Exception as e:
            print(f"  ✗ Error:  {e}")
            logger.error(f"Failed to move movie: {e}")
            return False
    
    def moveTvShow(self, sourceFile: Path, tvInfo: dict, videoDirs: List[Path],
                   interactive: bool = True) -> bool:
        """
        Move TV show file to appropriate location.
        
        Args:
            sourceFile: Source file path
            tvInfo: Parsed TV show information
            videoDirs: List of TV storage directories
            interactive:  Whether to prompt user for confirmation
            
        Returns:
            True if successful, False otherwise
        """
        showName = tvInfo["showName"]
        season = tvInfo["season"]
        
        logger.info(f"... processing TV show: {sourceFile. name}")
        
        # Check if user confirmation needed
        if interactive:
            confirmedShow = self.promptUserConfirmation(
                sourceFile.name,
                showName,
                "tv"
            )
            showName = confirmedShow
        
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
        seasonDir = showDir / f"Season {season: 02d}"
        destFile = seasonDir / sourceFile.name
        
        print(f"\nTV Show: {sourceFile.name}")
        print(f"  -> {destFile}")
        
        if self.dryRun:
            print("  [DRY RUN - no changes made]")
            logger.info(f"... dry run: would move to {destFile}")
            return True
        
        try:
            seasonDir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sourceFile), str(destFile))
            print("  ✓ Moved successfully")
            logger.info(f"...TV show moved successfully: {destFile}")
            return True
        except Exception as e: 
            print(f"  ✗ Error: {e}")
            logger.error(f"Failed to move TV show: {e}")
            return False
    
    def processFiles(self, interactive: bool = True):
        """
        Process all video files in the source directory.
        
        Args:
            interactive:  Whether to prompt user for ambiguous files
        """
        logger.info("... starting file processing")
        
        if not self.sourceDir.exists():
            logger.error(f"Source directory does not exist: {self.sourceDir}")
            print(f"Error: Source directory does not exist: {self.sourceDir}")
            return
        
        # Scan for storage locations
        print("Scanning for storage locations...")
        movieDirs, videoDirs = self.scanStorageLocations()
        
        print(f"\nFound {len(movieDirs)} movie storage location(s):")
        for d in movieDirs:
            print(f"  - {d}")
        
        print(f"\nFound {len(videoDirs)} TV storage location(s):")
        for d in videoDirs:
            print(f"  - {d}")
        
        if not movieDirs and not videoDirs:
            logger.error("No storage locations found")
            print("\nError: No storage locations found!")
            return
        
        # Get all video files
        videoFiles = [
            f for f in self.sourceDir. iterdir()
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        ]
        
        if not videoFiles:
            logger. info(f"No video files found in {self.sourceDir}")
            print(f"\nNo video files found in {self.sourceDir}")
            return
        
        print(f"\nFound {len(videoFiles)} video file(s) to process\n")
        print("=" * 60)
        
        # Process each file
        stats = {"movies": 0, "tv": 0, "skipped": 0, "errors":  0}
        
        for videoFile in videoFiles:
            # Try parsing as TV show first
            tvInfo = self.parseTvFilename(videoFile.name)
            if tvInfo and videoDirs:
                if self.moveTvShow(videoFile, tvInfo, videoDirs, interactive):
                    stats["tv"] += 1
                else:
                    stats["errors"] += 1
                continue
            
            # Try parsing as movie
            movieInfo = self. parseMovieFilename(videoFile.name)
            if movieInfo and movieDirs:
                if self.moveMovie(videoFile, movieInfo, movieDirs, interactive):
                    stats["movies"] += 1
                else: 
                    stats["errors"] += 1
                continue
            
            # Could not determine type
            logger.warning(f"Could not parse filename: {videoFile.name}")
            print(f"\nSkipped: {videoFile.name}")
            print("  Could not determine if movie or TV show")
            
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
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Movies moved:      {stats['movies']}")
        print(f"TV shows moved:   {stats['tv']}")
        print(f"Skipped:          {stats['skipped']}")
        print(f"Errors:           {stats['errors']}")
        print("=" * 60)
        
        logger.info(f"... processing complete:  {stats}")


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
        dest='dryRun',
        action='store_false',
        help='confirm execution — actually make changes (default is dry-run)',
    )
    parser.add_argument('--dry-run', dest='dryRun', action='store_true', default=True, help=argparse.SUPPRESS)
    parser.set_defaults(dryRun=True)
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run without user prompts (skip files that cannot be auto-detected)"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setupLogging(args.log_level)
    logger.info("... organiseMyVideo starting")
    
    if args.dryRun:
        logger.info("...dry-run mode (no changes will be made) — use --confirm to execute")
    else:
        logger.info("...confirm mode — changes will be made")
    
    # Create organizer and process files
    organizer = VideoOrganizer(sourceDir=args.source, dryRun=args.dryRun)
    organizer.processFiles(interactive=not args.non_interactive)
    
    logger.info("...organiseMyVideo complete")


if __name__ == "__main__": 
    main()