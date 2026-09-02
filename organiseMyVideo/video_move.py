"""Interactive move and file-processing workflows for video organisation."""

import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Optional

from .constants import MUSIC_EXTENSIONS, MUSIC_FOLDER_NAMES, VIDEO_EXTENSIONS
from .logging_utils import logger


class VideoMoveMixin:
    """Workflow methods for confirming, moving, and processing source files."""

    def _getMusicLibraryRoot(self) -> Path:
        """Return the root folder used for organised music files."""
        return Path.home() / "Music"

    def _isMusicFolder(self, folder: Path) -> bool:
        """Return True when *folder* is a source music folder."""
        return folder.name.strip().casefold() in MUSIC_FOLDER_NAMES

    def _findSourceMusicFolders(self) -> List[Path]:
        """Return top-level matching music folders within the current source tree."""
        if not self.sourceDir.exists():
            return []

        musicFolders = []
        if self._isMusicFolder(self.sourceDir):
            musicFolders.append(self.sourceDir)
        for folder in sorted(
            self.sourceDir.rglob("*"), key=lambda item: len(item.parts)
        ):
            if not folder.is_dir() or not self._isMusicFolder(folder):
                continue
            if any(
                folder == existing or folder.is_relative_to(existing)
                for existing in musicFolders
            ):
                continue
            musicFolders.append(folder)
        return musicFolders

    def _isInsideAnyFolder(self, path: Path, folders: List[Path]) -> bool:
        """Return True when *path* is inside one of *folders*."""
        return any(path == folder or path.is_relative_to(folder) for folder in folders)

    def _cleanMusicField(self, value: object) -> Optional[str]:
        """Return a filesystem-safe music metadata value."""
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            value = next((item for item in value if item), None)
        text = str(value).strip()
        if not text:
            return None
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" .")
        return text or None

    def _readMusicTags(self, musicFile: Path) -> dict:
        """Return simple audio metadata using mutagen when available."""
        try:
            from mutagen import File as MutagenFile  # type: ignore
        except ImportError:
            return {}

        try:
            audio = MutagenFile(musicFile, easy=True)
        except Exception as error:
            logger.warning(f"could not read music tags for {musicFile}: {error}")
            return {}
        if audio is None:
            return {}

        return {
            "artist": self._cleanMusicField(audio.get("artist")),
            "album": self._cleanMusicField(audio.get("album")),
            "title": self._cleanMusicField(audio.get("title")),
            "disc": self._cleanMusicNumber(audio.get("discnumber")),
            "track": self._cleanMusicNumber(audio.get("tracknumber")),
        }

    def _cleanMusicNumber(self, value: object) -> Optional[int]:
        """Return a music disc/track number from a tag or filename fragment."""
        if isinstance(value, (list, tuple)):
            value = next((item for item in value if item), None)
        if value is None:
            return None
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None

    def _inferMusicMetadataFromPath(self, musicFile: Path, musicFolder: Path) -> dict:
        """Infer artist, album, title and track from a source music path."""
        relativePath = musicFile.relative_to(musicFolder)
        parts = relativePath.parts
        parentParts = parts[:-1]
        artist = (
            self._cleanMusicField(parentParts[0]) if len(parentParts) >= 2 else None
        )
        album = self._cleanMusicField(parentParts[1]) if len(parentParts) >= 2 else None
        if len(parentParts) == 1:
            album = self._cleanMusicField(parentParts[0])

        stem = musicFile.stem
        disc = None
        track = None
        titleText = stem
        match = re.match(r"^\s*(\d+)-(\d+)\s+(.+)$", stem)
        if match:
            disc = int(match.group(1))
            track = int(match.group(2))
            titleText = match.group(3)
        else:
            match = re.match(r"^\s*(\d{1,3})(?:\s*[-._]\s*|\s+)(.+)$", stem)
            if match:
                track = int(match.group(1))
                titleText = match.group(2)

        return {
            "artist": artist,
            "album": album,
            "title": self._cleanMusicField(titleText),
            "disc": disc,
            "track": track,
        }

    def _resolveMusicMetadata(self, musicFile: Path, musicFolder: Path) -> dict:
        """Return complete music metadata from tags with path-based fallbacks."""
        tags = self._readMusicTags(musicFile)
        inferred = self._inferMusicMetadataFromPath(musicFile, musicFolder)
        return {
            "artist": tags.get("artist") or inferred.get("artist") or "Unknown Artist",
            "album": tags.get("album") or inferred.get("album") or "Unknown Album",
            "title": tags.get("title") or inferred.get("title") or musicFile.stem,
            "disc": tags.get("disc") or inferred.get("disc") or 1,
            "track": tags.get("track") or inferred.get("track"),
        }

    def _buildMusicDestinationFilename(self, musicFile: Path, metadata: dict) -> str:
        """Return the destination filename for a music track."""
        title = self._cleanMusicField(metadata.get("title")) or musicFile.stem
        disc = metadata.get("disc")
        track = metadata.get("track")
        if isinstance(track, int) and track > 0:
            discNumber = disc if isinstance(disc, int) and disc > 0 else 1
            return f"{discNumber}-{track:02d} {title}{musicFile.suffix.lower()}"
        return f"{title}{musicFile.suffix.lower()}"

    def _dedupeDestinationPath(self, destFile: Path) -> Path:
        """Return a non-existing destination path by adding a numeric suffix."""
        if not destFile.exists():
            return destFile
        for counter in range(2, 1000):
            candidate = destFile.with_name(
                f"{destFile.stem} ({counter}){destFile.suffix}"
            )
            if not candidate.exists():
                return candidate
        raise FileExistsError(f"could not find available destination for {destFile}")

    def _updateMusicTags(self, musicFile: Path, metadata: dict) -> None:
        """Best-effort update of MP3/audio tags after a track has been moved."""
        try:
            if musicFile.suffix.lower() == ".mp3":
                from mutagen.easyid3 import EasyID3  # type: ignore
                from mutagen.id3 import ID3, ID3NoHeaderError  # type: ignore

                try:
                    tags = EasyID3(musicFile)
                except ID3NoHeaderError:
                    ID3().save(musicFile)
                    tags = EasyID3(musicFile)
            else:
                from mutagen import File as MutagenFile  # type: ignore

                tags = MutagenFile(musicFile, easy=True)
                if tags is None:
                    return

            tags["artist"] = [str(metadata["artist"])]
            tags["album"] = [str(metadata["album"])]
            tags["title"] = [str(metadata["title"])]
            if metadata.get("disc"):
                tags["discnumber"] = [str(metadata["disc"])]
            if metadata.get("track"):
                tags["tracknumber"] = [str(metadata["track"])]
            tags.save()
        except ImportError:
            logger.warning("mutagen is not installed; music tags were not updated")
        except Exception as error:
            logger.warning(f"could not update music tags for {musicFile}: {error}")

    def moveMusicFile(self, musicFile: Path, musicFolder: Path) -> bool:
        """Move one audio file into the user's Music library."""
        metadata = self._resolveMusicMetadata(musicFile, musicFolder)
        libraryRoot = self._getMusicLibraryRoot()
        destDir = libraryRoot / metadata["artist"] / metadata["album"]
        destFile = self._dedupeDestinationPath(
            destDir / self._buildMusicDestinationFilename(musicFile, metadata)
        )

        logger.action(f"moving music:\n     {musicFile.name}\n     -> {destFile}")
        if self.dryRun:
            self._recordSummaryTransfer(musicFile, destFile)
            return True

        try:
            destDir.mkdir(parents=True, exist_ok=True)
            self._moveFileWithProgress(musicFile, destFile)
            self._updateMusicTags(destFile, metadata)
            self._recordSummaryTransfer(musicFile, destFile)
            logger.done("music moved successfully")
            return True
        except Exception as error:
            logger.error(f"Failed to move music: {error}")
            return False

    def processMusicFolders(self) -> dict:
        """Move audio files found under source folders named Music."""
        stats = {"music": 0, "errors": 0, "folders": 0}
        for musicFolder in self._findSourceMusicFolders():
            musicFiles = [
                item
                for item in sorted(musicFolder.rglob("*"))
                if item.is_file() and item.suffix.lower() in MUSIC_EXTENSIONS
            ]
            if not musicFiles:
                continue
            stats["folders"] += 1
            logger.info(f"found music folder: {musicFolder}")
            for musicFile in musicFiles:
                if self.moveMusicFile(musicFile, musicFolder):
                    stats["music"] += 1
                else:
                    stats["errors"] += 1
        return stats

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

        showName = self._capitaliseLowercaseTvShowTitle(showName) or showName
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
        destFile = seasonDir / self._buildTvDestinationFilename(
            sourceFile,
            tvInfo,
            preferSpaceStyle=bool(
                tvInfo.get("metadataSource") and tvInfo.get("episodeTitle")
            ),
        )

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

        self._renameExtrasFolders()
        musicFolders = self._findSourceMusicFolders()
        musicStats = self.processMusicFolders()

        if not movieDirs:
            logger.error("No Movie storage locations found")
        if not videoDirs:
            logger.error("No TV storage locations found!")
            if musicStats["music"] or musicStats["errors"]:
                logger.value("music processing complete", musicStats)
                self._writeSummaryReport()
            return

        # Get all video files (including those in subdirectories)
        videoFiles = [
            f
            for f in self.sourceDir.rglob("*")
            if f.is_file()
            and f.suffix.lower() in VIDEO_EXTENSIONS
            and not self._shouldIgnoreLocalVideoFile(f)
            and not self._isInsideAnyFolder(f, musicFolders)
        ]

        if not videoFiles:
            if musicStats["music"] or musicStats["errors"]:
                logger.value("music processing complete", musicStats)
            else:
                logger.value("no video files found in", self.sourceDir)
            self._writeSummaryReport()
            return

        logger.info(f"found {len(videoFiles)} video file(s) to process")

        # Process each file
        stats = {
            "movies": 0,
            "tv": 0,
            "music": musicStats["music"],
            "skipped": 0,
            "errors": musicStats["errors"],
        }

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
Music moved:    {stats['music']}
Skipped:        {stats['skipped']}
Errors:         {stats['errors']}
"""
        drawBox(summary)
        logger.value("processing complete", stats)
        self._writeSummaryReport()
