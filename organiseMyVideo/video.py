"""Core video-file organisation: scan storage, parse filenames, move files, clean names."""

import difflib
import os
import re
import sys
import shutil
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS, _PREFIX_REGEX

logger = getLogger()
UNKNOWN_YEAR = "Unknown"


class VideoMixin:
    """Methods for parsing, locating, moving and cleaning video files."""

    _MOVIE_MCM_PATTERNS = (
        "folder.jpg",
        "banner.jpg",
        "backdrop*.jpg",
        "movie.xml",
        "mcm_id__*.dvdid.xml",
    )
    _TV_SHOW_MCM_PATTERNS = (
        "folder.jpg",
        "banner.jpg",
        "backdrop*.jpg",
        "series.xml",
        "mcm_id__*.dvdid.xml",
    )
    _TV_SEASON_MCM_PATTERNS = ("folder.jpg",)

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

        logger.info(
            f"storage scan complete: {len(movieDirs)} movie, {len(videoDirs)} TV locations"
        )
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
        pattern = r"^(.+?)\.S(\d+)E(\d+)(?:\.(.+?))?\.(\w+)$"
        match = re.match(pattern, filename, re.IGNORECASE)

        if match:
            showName = match.group(1).replace(".", " ").strip()
            season = int(match.group(2))
            episode = int(match.group(3))
            episodeTitle = (
                match.group(4).replace(".", " ").strip() if match.group(4) else None
            )
            extension = match.group(5)

            return {
                "showName": showName,
                "season": season,
                "episode": episode,
                "episodeTitle": episodeTitle,
                "extension": extension,
                "type": "tv",
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
            match = re.match(pattern2, nameWithoutExt)

        if match:
            title = match.group(1).replace(".", " ").strip()
            year = match.group(2)

            return {
                "title": title,
                "year": year,
                "extension": extension,
                "type": "movie",
            }

        return None

    def findExistingMovieDir(
        self, title: str, year: str, movieDirs: List[Path]
    ) -> Optional[Path]:
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
                    logger.value("found existing movie", item)
                    return item

        return None

    def findExistingTvShowDir(
        self, showName: str, videoDirs: List[Path]
    ) -> Optional[Path]:
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

    def findBestMatchingTvShow(
        self, showName: str, videoDirs: List[Path]
    ) -> Optional[str]:
        """
        Find the best matching existing TV show folder name.

        Uses fuzzy matching so that minor differences in punctuation or
        capitalisation between the filename-derived show name and the folder
        name on disk are tolerated.

        Args:
            showName: Show name parsed from the filename
            videoDirs: List of TV storage directories to search

        Returns:
            Best matching folder name, or None if no close match is found
        """
        folderNames = []
        for tvRoot in videoDirs:
            if tvRoot.exists():
                for item in tvRoot.iterdir():
                    if item.is_dir():
                        folderNames.append(item.name)

        if not folderNames:
            return None

        matches = difflib.get_close_matches(showName, folderNames, n=1, cutoff=0.6)
        return matches[0] if matches else None

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

    def _collectMatchingFiles(
        self, sourceDir: Path, patterns: Iterable[str]
    ) -> List[Path]:
        """
        Return unique files in *sourceDir* matching the supplied glob patterns.

        Args:
            sourceDir: Directory to scan for companion metadata files.
            patterns: Glob patterns to evaluate within *sourceDir*.

        Returns:
            Sorted matching files with duplicates removed while preserving pattern order.
        """
        if not sourceDir.exists() or not sourceDir.is_dir():
            return []

        matches = []
        seen = set()
        for pattern in patterns:
            for match in sorted(sourceDir.glob(pattern)):
                if not match.is_file() or match in seen:
                    continue
                seen.add(match)
                matches.append(match)
        return matches

    def _copyFilesIntoDir(self, sourceFiles: Iterable[Path], destDir: Path) -> None:
        """
        Copy pre-filtered companion files into *destDir*.

        Args:
            sourceFiles: Existing files selected by the caller for replication.
            destDir: Destination directory that should receive the copied files.
        """
        for sourcePath in sourceFiles:
            destPath = destDir / sourcePath.name
            logger.action(f"copy metadata: {sourcePath} -> {destPath}")
            if self.dryRun:
                continue
            destDir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sourcePath, destPath)

    def _extractEpisodeMetadataImage(self, metadataFile: Path) -> Optional[str]:
        """Return the local metadata image filename referenced by an MCM episode XML file."""
        try:
            root = ET.fromstring(metadataFile.read_text(encoding="utf-8"))
        except (ET.ParseError, OSError, UnicodeDecodeError) as e:
            logger.warning("could not parse metadata XML %s: %s", metadataFile, e)
            return None

        filename = root.findtext("filename")
        if not filename:
            return None

        imageName = Path(filename.strip().lstrip("/\\")).name
        return imageName or None

    def _readXmlRoot(self, xmlFile: Path) -> Optional[ET.Element]:
        """Return the parsed XML root for *xmlFile*, or None if it cannot be read."""
        if not xmlFile.exists() or not xmlFile.is_file():
            return None

        try:
            return ET.fromstring(xmlFile.read_text(encoding="utf-8"))
        except (ET.ParseError, OSError, UnicodeDecodeError) as e:
            logger.warning("could not parse metadata XML %s: %s", xmlFile, e)
            return None

    def _readFirstXmlText(
        self, root: Optional[ET.Element], tags: Iterable[str]
    ) -> Optional[str]:
        """Return the first non-empty text value for any tag in *tags*."""
        if root is None:
            return None

        for tag in tags:
            value = root.findtext(tag)
            if value and value.strip():
                return value.strip()

        return None

    def _readIntXmlText(
        self, root: Optional[ET.Element], tags: Iterable[str]
    ) -> Optional[int]:
        """Return the first tag value that can be converted to an integer."""
        value = self._readFirstXmlText(root, tags)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _inferSeasonFromPath(self, seasonDir: Path) -> Optional[int]:
        """Return the season number inferred from a season directory name."""
        match = re.search(r"(?:season\s*|s)(\d+)", seasonDir.name, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _readMovieMcmHints(self, sourceFile: Path) -> Optional[dict]:
        """
        Return standardised movie hints from nearby MCM XML files.

        The returned structure is designed for both current move-time decisions
        and future scraper output, so it carries stable IDs in addition to the
        title/year values used today.

        Args:
            sourceFile: Video file whose parent directory may contain movie.xml.

        Returns:
            ``None`` when no usable movie metadata exists, otherwise a dict with
            ``type`` (str), ``title`` (Optional[str]), ``year`` (Optional[str]),
            ``imdbId`` (Optional[str]), ``tmdbId`` (Optional[str]), and
            ``metadataSource`` (str).
        """
        movieRoot = self._readXmlRoot(sourceFile.parent / "movie.xml")
        if movieRoot is None:
            return None

        title = self._readFirstXmlText(movieRoot, ("LocalTitle", "OriginalTitle"))
        year = self._readFirstXmlText(movieRoot, ("ProductionYear", "Year"))
        imdbId = self._readFirstXmlText(movieRoot, ("IMDbId", "IMDB", "IMDB_ID"))
        tmdbId = self._readFirstXmlText(movieRoot, ("TMDbId", "TMDBId"))

        if not self._hasAnyMetadata(
            title=title, year=year, imdbId=imdbId, tmdbId=tmdbId
        ):
            return None

        return {
            "type": "movie",
            "title": title,
            "year": year,
            "imdbId": imdbId,
            "tmdbId": tmdbId,
            "metadataSource": "mcm",
        }

    def _readTvMcmHints(self, sourceFile: Path) -> Optional[dict]:
        """
        Return standardised TV hints from nearby MCM XML files.

        The shape matches the future scraper-oriented metadata model so that
        move logic can consume the same keys whether the files already exist on
        disk or are generated later by organiseMyVideo.

        Args:
            sourceFile: Episode file whose show/season structure may contain
                        ``series.xml`` and episode metadata XML.

        Returns:
            ``None`` when no usable TV metadata exists, otherwise a dict with
            ``type`` (str), ``showName`` (Optional[str]), ``season``
            (Optional[int]), ``episode`` (Optional[int]), ``episodeTitle``
            (Optional[str]), ``imdbId`` (Optional[str]), ``seriesId``
            (Optional[str]), ``episodeId`` (Optional[str]), and
            ``metadataSource`` (str).
        """
        sourceSeasonDir = sourceFile.parent
        sourceShowDir = None
        if (
            sourceSeasonDir != self.sourceDir
            and sourceSeasonDir.parent != self.sourceDir
        ):
            sourceShowDir = sourceSeasonDir.parent
        seriesRoot = (
            self._readXmlRoot(sourceShowDir / "series.xml") if sourceShowDir else None
        )
        episodeRoot = self._readXmlRoot(
            sourceSeasonDir / "metadata" / f"{sourceFile.stem}.xml"
        )

        showName = self._readFirstXmlText(seriesRoot, ("LocalTitle", "SeriesName"))
        season = self._readIntXmlText(
            episodeRoot, ("SeasonNumber",)
        ) or self._inferSeasonFromPath(sourceSeasonDir)
        episode = self._readIntXmlText(episodeRoot, ("EpisodeNumber", "ID"))
        episodeTitle = self._readFirstXmlText(episodeRoot, ("EpisodeName",))
        imdbId = self._readFirstXmlText(episodeRoot, ("IMDB_ID", "IMDbId"))
        seriesId = self._readFirstXmlText(seriesRoot, ("SeriesID", "id"))
        episodeId = self._readFirstXmlText(episodeRoot, ("EpisodeID",))

        if not self._hasAnyMetadata(
            showName=showName,
            season=season,
            episode=episode,
            episodeTitle=episodeTitle,
            imdbId=imdbId,
            seriesId=seriesId,
            episodeId=episodeId,
        ):
            return None

        return {
            "type": "tv",
            "showName": showName,
            "season": season,
            "episode": episode,
            "episodeTitle": episodeTitle,
            "imdbId": imdbId,
            "seriesId": seriesId,
            "episodeId": episodeId,
            "metadataSource": "mcm",
        }

    def _readMcmHints(self, sourceFile: Path) -> Optional[dict]:
        """
        Return standardised MCM metadata hints for *sourceFile*.

        These hints help current move-time classification and naming decisions,
        and they also define the metadata shape future scraping code should
        populate when organiseMyVideo starts generating MCM-style files itself.

        TV hints are attempted first, then movie hints.

        Args:
            sourceFile: Video file whose nearby MCM files should be inspected.

        Returns:
            ``None`` when no usable hints exist, otherwise either the TV hint
            dict returned by :meth:`_readTvMcmHints` or the movie hint dict
            returned by :meth:`_readMovieMcmHints`.
        """
        hints = self._readTvMcmHints(sourceFile) or self._readMovieMcmHints(sourceFile)
        self._updateMetadataLibraryFromHints(hints)
        return hints

    def _applyMovieMcmHints(
        self, movieInfo: Optional[dict], mcmHints: Optional[dict], sourceFile: Path
    ) -> Optional[dict]:
        """
        Merge movie-specific MCM hints into filename-derived movie info.

        Args:
            movieInfo: Filename-derived movie info, or ``None`` when filename
                       parsing failed.
            mcmHints: Standardised MCM hints, which may describe another type.
            sourceFile: Source file used to supply a fallback extension.

        Returns:
            A merged movie info dict when a usable title is available,
            otherwise the original ``movieInfo`` value.
        """
        if not mcmHints or mcmHints.get("type") != "movie":
            return movieInfo

        merged = dict(movieInfo or {})
        merged["title"] = mcmHints.get("title") or merged.get("title")
        merged["year"] = mcmHints.get("year") or merged.get("year") or UNKNOWN_YEAR
        merged["extension"] = merged.get("extension") or sourceFile.suffix
        merged["type"] = "movie"
        for key in ("imdbId", "tmdbId", "metadataSource"):
            if mcmHints.get(key):
                merged[key] = mcmHints[key]
        return merged if merged.get("title") else movieInfo

    def _applyTvMcmHints(
        self, tvInfo: Optional[dict], mcmHints: Optional[dict], sourceFile: Path
    ) -> Optional[dict]:
        """
        Merge TV-specific MCM hints into filename-derived TV info.

        Args:
            tvInfo: Filename-derived TV info, or ``None`` when filename parsing
                    failed.
            mcmHints: Standardised MCM hints, which may describe another type.
            sourceFile: Source file used to supply a fallback extension.

        Returns:
            A merged TV info dict when show name and season are known,
            otherwise the original ``tvInfo`` value.
        """
        if not mcmHints or mcmHints.get("type") != "tv":
            return tvInfo

        merged = dict(tvInfo or {})
        merged["showName"] = mcmHints.get("showName") or merged.get("showName")
        merged["season"] = mcmHints.get("season") or merged.get("season")
        merged["episode"] = mcmHints.get("episode") or merged.get("episode")
        merged["extension"] = merged.get("extension") or sourceFile.suffix
        merged["type"] = "tv"
        for key in (
            "episodeTitle",
            "imdbId",
            "seriesId",
            "episodeId",
            "metadataSource",
        ):
            if mcmHints.get(key):
                merged[key] = mcmHints[key]
        if merged.get("showName") and merged.get("season") is not None:
            return merged
        return tvInfo

    def _hasAnyMetadata(self, **metadataValues) -> bool:
        """Return True when any metadata hint has a usable value."""
        return any(
            value is not None and value != "" for value in metadataValues.values()
        )

    def _replicateMovieMetadata(self, sourceFile: Path, destDir: Path) -> None:
        """Copy supported MCM movie companion files into the destination folder."""
        if sourceFile.parent == self.sourceDir:
            return

        movieMetadataFiles = self._collectMatchingFiles(
            sourceFile.parent, self._MOVIE_MCM_PATTERNS
        )
        self._copyFilesIntoDir(movieMetadataFiles, destDir)

    def _sanitiseFilenamePart(self, value: str) -> str:
        """Return a dot-separated, filesystem-safe filename fragment."""
        normalised = unicodedata.normalize("NFKC", value).replace("'", "")
        normalised = re.sub(r"[^\w]+", " ", normalised, flags=re.UNICODE)
        normalised = normalised.replace("_", " ")
        tokens = normalised.split()
        return ".".join(tokens)

    def _buildTvDestinationFilename(self, sourceFile: Path, tvInfo: dict) -> str:
        """Return the destination TV filename, preferring canonical enriched names."""
        showName = tvInfo.get("showName")
        season = tvInfo.get("season")
        episode = tvInfo.get("episode")
        episodeTitle = tvInfo.get("episodeTitle")
        extension = tvInfo.get("extension") or sourceFile.suffix
        if extension and not str(extension).startswith("."):
            extension = f".{extension}"

        if not showName or season is None or episode is None:
            return sourceFile.name

        showPart = self._sanitiseFilenamePart(showName)
        titlePart = self._sanitiseFilenamePart(episodeTitle) if episodeTitle else ""
        if not showPart:
            return sourceFile.name

        parts = [showPart, f"S{season:02d}E{episode:02d}"]
        if titlePart:
            parts.append(titlePart)
        return f"{'.'.join(parts)}{extension}"

    def _writeEpisodeMcmTemplate(
        self,
        sourceFile: Path,
        destMetadataDir: Path,
        tvInfo: dict,
        destStem: Optional[str] = None,
    ) -> None:
        """
        Create a starter MCM episode XML file when only show-level metadata is available.

        Args:
            sourceFile: Episode file being moved.
            destMetadataDir: Destination metadata directory for the generated XML.
            tvInfo: Parsed or inferred TV metadata.  When season or episode is
                    missing, the method returns without writing a template.
        """
        mcmHints = self._readTvMcmHints(sourceFile) or {}
        season = tvInfo.get("season") or mcmHints.get("season")
        episode = tvInfo.get("episode")
        if season is None or episode is None:
            return

        seriesId = tvInfo.get("seriesId") or mcmHints.get("seriesId") or ""
        imdbId = tvInfo.get("imdbId") or mcmHints.get("imdbId") or ""
        episodeId = tvInfo.get("episodeId") or mcmHints.get("episodeId") or ""
        episodeTitle = tvInfo.get("episodeTitle") or mcmHints.get("episodeTitle") or ""

        item = ET.Element("Item")
        fields = {
            "ID": str(episode),
            "EpisodeID": episodeId,
            "EpisodeNumber": str(episode),
            "SeasonNumber": str(season),
            "seriesid": seriesId,
            "IMDB_ID": imdbId,
            "EpisodeName": episodeTitle,
            "Type": "",
        }
        for key, value in fields.items():
            child = ET.SubElement(item, key)
            child.text = value

        destFile = destMetadataDir / f"{destStem or sourceFile.stem}.xml"
        logger.action("create metadata: %s", destFile)
        if self.dryRun:
            return

        destMetadataDir.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(item).write(destFile, encoding="utf-8", xml_declaration=True)

    def _updateEpisodeMetadataRoot(self, root: ET.Element, tvInfo: dict) -> ET.Element:
        """Update an episode XML root with resolved metadata values."""
        updates = {
            "EpisodeID": tvInfo.get("episodeId"),
            "EpisodeNumber": (
                str(tvInfo["episode"]) if tvInfo.get("episode") is not None else None
            ),
            "SeasonNumber": (
                str(tvInfo["season"]) if tvInfo.get("season") is not None else None
            ),
            "seriesid": tvInfo.get("seriesId"),
            "IMDB_ID": tvInfo.get("imdbId"),
            "EpisodeName": tvInfo.get("episodeTitle"),
        }
        for tag, value in updates.items():
            if value in (None, ""):
                continue
            child = root.find(tag)
            if child is None:
                child = ET.SubElement(root, tag)
            child.text = value
        return root

    def _writeEpisodeMetadataFile(self, destFile: Path, root: ET.Element) -> None:
        """Write an episode metadata XML file to *destFile*."""
        logger.action("create metadata: %s", destFile)
        if self.dryRun:
            return

        destFile.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(root).write(destFile, encoding="utf-8", xml_declaration=True)

    def _replicateTvMetadata(
        self,
        sourceFile: Path,
        showDir: Path,
        seasonDir: Path,
        tvInfo: dict,
        destFile: Optional[Path] = None,
    ) -> None:
        """
        Copy supported MCM TV-show companion files into show and season folders.

        Args:
            sourceFile: Episode file being moved.
            showDir: Destination show directory.
            seasonDir: Destination season directory.
            tvInfo: Parsed or inferred TV metadata used for template creation
                    when no episode XML exists yet.
        """
        sourceSeasonDir = sourceFile.parent
        if sourceSeasonDir == self.sourceDir or not sourceSeasonDir.is_dir():
            return

        if re.match(r"^season\b", sourceSeasonDir.name, re.IGNORECASE):
            sourceShowDir = sourceSeasonDir.parent
            if sourceShowDir != self.sourceDir:
                showMetadataFiles = self._collectMatchingFiles(
                    sourceShowDir, self._TV_SHOW_MCM_PATTERNS
                )
                self._copyFilesIntoDir(showMetadataFiles, showDir)

        seasonMetadataFiles = self._collectMatchingFiles(
            sourceSeasonDir, self._TV_SEASON_MCM_PATTERNS
        )
        self._copyFilesIntoDir(seasonMetadataFiles, seasonDir)

        metadataDir = sourceSeasonDir / "metadata"
        episodeMetadataFile = metadataDir / f"{sourceFile.stem}.xml"
        destMetadataDir = seasonDir / "metadata"
        destStem = destFile.stem if destFile else sourceFile.stem
        if not episodeMetadataFile.exists():
            # New episodes generate a starter XML instead of copying an existing file.
            self._writeEpisodeMcmTemplate(
                sourceFile, destMetadataDir, tvInfo, destStem=destStem
            )
            return

        if destStem == sourceFile.stem and not tvInfo.get("episodeTitle"):
            # When the destination stem already matches and no new title exists,
            # keep the original XML unchanged instead of rewriting it.
            self._copyFilesIntoDir([episodeMetadataFile], destMetadataDir)
        else:
            episodeRoot = self._readXmlRoot(episodeMetadataFile) or ET.Element("Item")
            self._writeEpisodeMetadataFile(
                destMetadataDir / f"{destStem}.xml",
                self._updateEpisodeMetadataRoot(episodeRoot, tvInfo),
            )

        imageName = self._extractEpisodeMetadataImage(episodeMetadataFile)
        if not imageName:
            return

        imagePath = metadataDir / imageName
        if imagePath.exists():
            self._copyFilesIntoDir([imagePath], destMetadataDir)

    def promptUserConfirmation(
        self,
        filename: str,
        defaultName: str,
        fileType: str,
        videoDirs: Optional[List[Path]] = None,
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
        if not self._promptHelpDisplayed:
            print(
                "  y/enter = confirm  |  n = rename  |  "
                "t = treat as TV show  |  m = treat as movie  |  q = quit"
            )
            self._promptHelpDisplayed = True

        if fileType == "tv":
            prompt = f"\nTV Show detected: '{defaultName}'\nIs this correct?  (y/n/q/t/m or enter new name): "
        else:
            prompt = f"\nMovie detected: '{defaultName}'\nIs this correct? (y/n/q/t/m or enter new name): "

        response = input(prompt).strip()

        if response.lower() in ["y", "yes", ""]:
            return {"name": defaultName, "type": fileType}
        elif response.lower() in ["n", "no"]:
            rawName = input(
                f"Enter new name (blank for default, enter 'quit' to skip): "
            )
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
            tvDefault = defaultName
            if videoDirs:
                tvParsed = self.parseTvFilename(filename)
                parsedShowName = tvParsed["showName"] if tvParsed else defaultName
                bestMatch = self.findBestMatchingTvShow(parsedShowName, videoDirs)
                if bestMatch:
                    tvDefault = bestMatch
            showName = input(f"  Enter show name (default: {tvDefault}): ").strip()
            return {"name": showName if showName else tvDefault, "type": "tv"}
        elif response.lower() == "m":
            title = input(f"  Enter movie title (default: {defaultName}): ").strip()
            return {"name": title if title else defaultName, "type": "movie"}
        else:
            return {"name": response, "type": fileType}

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
        title = movieInfo["title"]
        year = movieInfo["year"]

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
                season = input("  Season number (default 1): ").strip()
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

        logger.value("movie", sourceFile.name)
        logger.value("  ->", destFile)

        if self.dryRun:
            logger.action(f"move to: {destFile}")
            return True

        try:
            destDir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sourceFile), str(destFile))
            self._replicateMovieMetadata(sourceFile, destDir)
            logger.action(f"movie moved successfully: {destFile}")
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
        tvInfo = self._mergeMetadata(tvInfo, self.parseTvFilename(sourceFile.name))
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
                    return self.moveMovie(
                        sourceFile, movieInfo, movieDirs, interactive=False
                    )
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
        destFile = seasonDir / self._buildTvDestinationFilename(sourceFile, tvInfo)

        logger.value("TV Show", sourceFile.name)
        logger.value("  ->", destFile)

        if self.dryRun:
            logger.action(f"move to: {destFile}")
            return True

        try:
            seasonDir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(sourceFile), str(destFile))
            self._replicateTvMetadata(
                sourceFile, showDir, seasonDir, tvInfo, destFile=destFile
            )
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
                if any(
                    self._isSampleLikeFolder(Path(part)) for part in relativeParts[:-1]
                ):
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

        for subDir in sorted(
            self.sourceDir.rglob("*"),
            key=lambda p: (len(p.parts), str(p)),
            reverse=True,
        ):
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

        logger.info(
            f"found {len(movieDirs)} movie storage location(s) and {len(videoDirs)} TV storage location(s)"
        )
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
            f
            for f in self.sourceDir.rglob("*")
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        ]

        if not videoFiles:
            logger.value("no video files found in", self.sourceDir)
            return

        logger.info(f"found {len(videoFiles)} video file(s) to process")

        # Process each file
        stats = {"movies": 0, "tv": 0, "skipped": 0, "errors": 0}

        for videoFile in videoFiles:
            mcmHints = self._readMcmHints(videoFile)

            # Try parsing as TV show first
            tvInfo = self._enrichTvMetadata(
                self._applyTvMcmHints(
                    self.parseTvFilename(videoFile.name), mcmHints, videoFile
                )
            )
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

            # Try parsing as movie
            movieInfo = self._applyMovieMcmHints(
                self.parseMovieFilename(videoFile.name), mcmHints, videoFile
            )
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
                fileType = (
                    input("  Is this a (m)ovie or (t)v show? (or 's' to skip): ")
                    .strip()
                    .lower()
                )

                if fileType == "m" and movieDirs:
                    # Prompt for movie info
                    title = input(
                        f"  Movie title (default: {videoFile.stem}): "
                    ).strip()
                    title = title if title else videoFile.stem
                    year = input("  Year:  ").strip()

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
                    show = input(f"  Show name (default: {videoFile.stem}): ").strip()
                    show = show if show else videoFile.stem
                    season = input("  Season number: ").strip()

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

        # Print summary
        from organiseMyProjects.logUtils import drawBox  # type: ignore

        summary = f"""SUMMARY
Movies moved:   {stats['movies']}
TV shows moved: {stats['tv']}
Skipped:        {stats['skipped']}
Errors:         {stats['errors']}
"""
        drawBox(summary)
        logger.value("processing complete", stats)
