"""Interactive move and file-processing workflows for video organisation."""

import re
import sys
from pathlib import Path
from typing import List, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS

logger = getLogger()


class VideoMoveMixin:
    """Workflow methods for confirming, moving, and processing source files."""

    def promptUserConfirmation(
        self,
        filename: str,
        defaultName: str,
        fileType: str,
        videoDirs: Optional[List[Path]] = None,
        episodeTitle: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Prompt user to confirm or correct the detected name.

        Args:
            filename: Original filename
            defaultName:  Detected name to confirm
            fileType: Type of file ('tv' or 'movie')
            videoDirs: Optional list of TV storage directories used to suggest
                       an existing show name when the user switches to TV mode.

        Returns:
            dict with 'name' and 'type' keys, or None to skip this item.
            'type' may differ from fileType when the user switches category.
        """
        cachedResult = self._getCachedPromptDecision(defaultName, fileType)
        if cachedResult is not None:
            logger.value("reusing confirmed TV show", cachedResult["name"])
            return cachedResult

        if fileType == "tv":
            prompt = (
                f"  TV Show detected: {defaultName}\n"
                f"  Episode Title:    {episodeTitle}\n"
                "  Is this correct?  (y/n/q/t/m or enter new name): "
            )
        else:
            prompt = (
                f"  Movie detected: '{defaultName}'\n"
                "  Is this correct?  (y/n/q/t/m or enter new name): "
            )

        if self._shouldUseCursesPrompts():
            response = self._readMenuChoice(
                prompt,
                validChoices={"y", "n", "q", "t", "m"},
                defaultChoice="y",
            )
        else:
            response = self._readTextResponse(prompt)

        if response.lower() in ["y", "yes", ""]:
            result = {"name": defaultName, "type": fileType}
            self._cachePromptDecision(defaultName, fileType, result)
            return result
        elif response.lower() in ["n", "no"]:
            rawName = self._readTextResponse(
                "Enter new name (blank to keep default, 'quit' to skip): "
            )
            if not rawName:
                result = {"name": defaultName, "type": fileType}
                self._cachePromptDecision(defaultName, fileType, result)
                return result
            if rawName.strip().lower() == "quit":
                return None
            strippedName = rawName.strip()
            if not strippedName:
                result = {"name": defaultName, "type": fileType}
                self._cachePromptDecision(defaultName, fileType, result)
                return result
            result = {"name": strippedName, "type": fileType}
            self._cachePromptDecision(defaultName, fileType, result)
            return result
        elif response.lower() in ["q", "quit"]:
            logger.info("user requested to quit")
            sys.exit(0)
        elif response.lower() == "t":
            tvDefault = defaultName
            if videoDirs:
                tvParsed = self.parseTvFilename(filename)
                parsedShowName = tvParsed["showName"] if tvParsed else defaultName
                bestMatch = self.findBestMatchingTvShow(parsedShowName, videoDirs)
                if bestMatch:
                    tvDefault = bestMatch
            showName = self._readTextResponse(
                f"  Enter show name (default: {tvDefault}): "
            )
            return {"name": showName if showName else tvDefault, "type": "tv"}
        elif response.lower() == "m":
            title = self._readTextResponse(
                f"  Enter movie title (default: {defaultName}): "
            )
            return {"name": title if title else defaultName, "type": "movie"}
        else:
            result = {"name": response, "type": fileType}
            self._cachePromptDecision(defaultName, fileType, result)
            return result

    def moveMovie(
        self,
        sourceFile: Path,
        movieInfo: dict,
        movieDirs: List[Path],
        videoDirs: Optional[List[Path]] = None,
        interactive: bool = True,
    ) -> bool:
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
        resolvedMovieInfo = dict(movieInfo)
        enrichedMovieInfo = self._enrichMovieMetadata(resolvedMovieInfo)
        if enrichedMovieInfo:
            resolvedMovieInfo = enrichedMovieInfo
        title = resolvedMovieInfo["title"]
        year = resolvedMovieInfo["year"]

        logger.value("processing movie", sourceFile.name)

        # Check if user confirmation needed
        if interactive:
            result = self.promptUserConfirmation(
                sourceFile.name,
                f"{title} ({year})",
                "movie",
                videoDirs=videoDirs,
            )
            if result is None:
                logger.info(f"skipping: {sourceFile.name}")
                return False
            if result["type"] == "tv":
                # User wants to process as TV show instead
                season = self._readTextResponse("  Season number (default 1): ")
                season = int(season) if season.isdigit() else 1
                tvInfo = {
                    "showName": result["name"],
                    "season": season,
                    "episode": None,
                    "extension": sourceFile.suffix,
                    "type": "tv",
                }
                if videoDirs:
                    return self.moveTvShow(
                        sourceFile, tvInfo, videoDirs, interactive=False
                    )
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
            resolvedMovieInfo["title"] = title
            resolvedMovieInfo["year"] = year

        title = resolvedMovieInfo["title"]
        year = resolvedMovieInfo["year"]

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

        destFile = destDir / self._buildMovieDestinationFilename(
            sourceFile, resolvedMovieInfo
        )

        logger.action(
            f"moving movie:\n" f"     {sourceFile.name}\n" f"     -> {destFile}"
        )

        if self.dryRun:
            self._recordSummaryTransfer(sourceFile, destFile)
            return True

        try:
            destDir.mkdir(parents=True, exist_ok=True)
            self._moveFileWithProgress(sourceFile, destFile)
            self._replicateMovieMetadata(sourceFile, destDir, resolvedMovieInfo)
            self._recordSummaryTransfer(sourceFile, destFile)
            logger.done("movie moved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to move movie: {e}")
            return False

    def moveTvShow(
        self,
        sourceFile: Path,
        tvInfo: dict,
        videoDirs: List[Path],
        movieDirs: Optional[List[Path]] = None,
        interactive: bool = True,
    ) -> bool:
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
        tvInfo = dict(tvInfo)
        metadataLookupAttempted = bool(tvInfo.pop("_tvMetadataLookupAttempted", False))
        tvInfo = self._mergeMetadata(tvInfo, self.parseTvFilename(sourceFile.name))
        if not metadataLookupAttempted:
            tvInfo = self._enrichTvMetadata(tvInfo) or tvInfo
        showName = tvInfo["showName"]
        season = tvInfo["season"]

        logger.value("processing TV show", sourceFile.name)

        # Check if user confirmation needed
        if interactive:
            result = self.promptUserConfirmation(
                sourceFile.name,
                showName,
                "tv",
                videoDirs=videoDirs,
                episodeTitle=tvInfo.get("episodeTitle"),
            )
            if result is None:
                logger.info(f"skipping: {sourceFile.name}")
                return False
            if result["type"] == "movie":
                # User wants to process as movie instead
                year = self._readTextResponse("  Year (e.g. 2020): ")
                movieInfo = {
                    "title": result["name"],
                    "year": year if year else "Unknown",
                    "extension": sourceFile.suffix,
                    "type": "movie",
                }
                if movieDirs:
                    return self.moveMovie(
                        sourceFile, movieInfo, movieDirs, interactive=False
                    )
                logger.error("no movie storage locations available for type switch")
                return False
            showName = result["name"]
            tvInfo["showName"] = showName

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

            showDir = storage / self._buildTvShowFolderName(showName)

        # Create season directory
        seasonDir = showDir / f"Season {season:02d}"
        destFile = seasonDir / self._buildTvDestinationFilename(sourceFile, tvInfo)

        logger.action(
            f"moving TV show:\n" f"     {sourceFile.name}\n" f"     -> {destFile}"
        )

        if self.dryRun:
            self._recordSummaryTransfer(sourceFile, destFile)
            return True

        try:
            seasonDir.mkdir(parents=True, exist_ok=True)
            self._moveFileWithProgress(sourceFile, destFile)
            self._replicateTvMetadata(
                sourceFile, showDir, seasonDir, tvInfo, destFile=destFile
            )
            self._recordSummaryTransfer(sourceFile, destFile)
            logger.done("TV show moved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to move TV show: {e}")
            return False

    def processFiles(self, interactive: bool = True):
        """
        Process all video files in the source directory.

        Args:
            interactive:  Whether to prompt user for ambiguous files
        """
        from organiseMyProjects.logUtils import drawBox  # type: ignore

        from .video import _FILE_PROCESS_SEPARATOR

        logger.doing("starting file processing")

        if not self.sourceDir.exists():
            logger.error(f"Source directory does not exist: {self.sourceDir}")
            return

        # Scan for storage locations
        logger.doing("scanning for storage locations")
        movieDirs, videoDirs = self.scanStorageLocations()

        logger.info(
            f"found {len(movieDirs)} movie storage location(s) and {len(videoDirs)} TV storage location(s)"
        )
        for d in movieDirs:
            logger.value("  - ", d)

        logger.info(f"found {len(videoDirs)} TV storage location(s):")
        for d in videoDirs:
            logger.value("  - ", d)

        self._prepareMetadataLibrary(movieDirs, videoDirs)

        if not movieDirs:
            logger.error("No Movie storage locations found")
        if not videoDirs:
            logger.error("No TV storage locations found!")
            return

        self._renameExtrasFolders()

        # Get all video files (including those in subdirectories)
        videoFiles = [
            f
            for f in self.sourceDir.rglob("*")
            if f.is_file()
            and f.suffix.lower() in VIDEO_EXTENSIONS
            and not self._shouldIgnoreLocalVideoFile(f)
        ]

        if not videoFiles:
            logger.value("no video files found in", self.sourceDir)
            self._writeSummaryReport()
            return

        logger.info(f"found {len(videoFiles)} video file(s) to process")

        # Process each file
        stats = {"movies": 0, "tv": 0, "skipped": 0, "errors": 0}

        for videoFile in videoFiles:
            logger.info(_FILE_PROCESS_SEPARATOR)
            mcmHints = self._readMcmHints(videoFile)
            tvInfo, movieInfo = self._classifyVideoFile(videoFile, mcmHints)
            if tvInfo and videoDirs:
                if self.moveTvShow(
                    videoFile,
                    tvInfo,
                    videoDirs,
                    movieDirs=movieDirs,
                    interactive=interactive,
                ):
                    stats["tv"] += 1
                else:
                    stats["errors"] += 1
                continue

            if movieInfo and movieDirs:
                if self.moveMovie(
                    videoFile,
                    movieInfo,
                    movieDirs,
                    videoDirs=videoDirs,
                    interactive=interactive,
                ):
                    stats["movies"] += 1
                else:
                    stats["errors"] += 1
                continue

            # Could not determine type
            logger.warning(f"could not parse filename: {videoFile.name}")
            logger.value("skipped:", videoFile.name)
            logger.info("could not determine if movie or TV show")

            if interactive:
                fileType = self._readMenuChoice(
                    "Could not determine type.\nPress m for movie, t for TV show, or s to skip.",
                    validChoices={"m", "t", "s"},
                )

                if fileType == "m" and movieDirs:
                    # Prompt for movie info
                    title = self._readTextResponse(
                        f"  Movie title (default: {videoFile.stem}): "
                    )
                    title = title if title else videoFile.stem
                    year = self._readTextResponse("  Year:  ")

                    if year:
                        movieInfo = {
                            "title": title,
                            "year": year,
                            "extension": videoFile.suffix,
                            "type": "movie",
                        }
                        if self.moveMovie(videoFile, movieInfo, movieDirs, False):
                            stats["movies"] += 1
                        else:
                            stats["errors"] += 1
                        continue

                elif fileType == "t" and videoDirs:
                    # Prompt for TV show info
                    show = self._readTextResponse(
                        f"  Show name (default: {videoFile.stem}): "
                    )
                    show = show if show else videoFile.stem
                    season = self._readTextResponse("  Season number: ")

                    if season and season.isdigit():
                        tvInfo = {
                            "showName": show,
                            "season": int(season),
                            "episode": 0,
                            "extension": videoFile.suffix,
                            "type": "tv",
                        }
                        if self.moveTvShow(videoFile, tvInfo, videoDirs, False):
                            stats["tv"] += 1
                        else:
                            stats["errors"] += 1
                        continue

            stats["skipped"] += 1

        summary = f"""SUMMARY
Movies moved:   {stats['movies']}
TV shows moved: {stats['tv']}
Skipped:        {stats['skipped']}
Errors:         {stats['errors']}
"""
        drawBox(summary)
        logger.value("processing complete", stats)
        self._writeSummaryReport()
