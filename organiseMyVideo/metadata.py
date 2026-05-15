"""Persistent metadata library and TV metadata enrichment helpers."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import (
    METADATA_LIBRARY_FILE,
    TMDB_API_BASE_URL,
    TMDB_IMAGE_BASE_URL,
    TVDB_API_BASE_URL,
)

logger = getLogger()
_METADATA_SCAN_PLACEHOLDER_FILENAME = "__metadata_scan__.mkv"
_METADATA_SCAN_SUFFIX = Path(_METADATA_SCAN_PLACEHOLDER_FILENAME).suffix
_METADATA_LIBRARY_LOG_CONTINUATION_PREFIX = " "
_METADATA_LIBRARY_STATE_MISSING = "missing"
_METADATA_LIBRARY_STATE_INVALID = "invalid"
_METADATA_LIBRARY_STATE_READY = "ready"
_OMDB_API_BASE_URL = "https://www.omdbapi.com/"
_MAX_ARTWORK_SIZE_BYTES = 20_000_000


class MetadataMixin:
    """Methods for caching local metadata and enriching TV episode details."""

    def _promptForTvdbApiKeyIfNeeded(self) -> Optional[str]:
        """Prompt once for a TVDB API key when no credentials are configured."""
        apiKey = os.environ.get("ORGANISEMYVIDEO_TVDB_API_KEY")
        if apiKey:
            return apiKey

        if getattr(self, "_tvdbApiKeyPromptAttempted", False):
            return None

        prompt = getattr(self, "tvdbApiKeyPrompt", None)
        if not callable(prompt):
            return None

        self._tvdbApiKeyPromptAttempted = True
        try:
            prompted = prompt()
        except Exception as error:
            logger.warning("TVDB API key prompt failed: %s", error)
            return None

        if isinstance(prompted, str) and prompted.strip():
            apiKey = prompted.strip()
            os.environ["ORGANISEMYVIDEO_TVDB_API_KEY"] = apiKey
            return apiKey

        apiKey = os.environ.get("ORGANISEMYVIDEO_TVDB_API_KEY")
        return apiKey.strip() if apiKey else None

    def _logMetadataLibraryAddition(self, mediaType: str, name: str) -> None:
        """Log a grouped metadata-library addition header followed by ``name``."""
        if mediaType == "movie":
            if not self._metadataMovieLogStarted:
                logger.doing("adding movie to library")
                self._metadataMovieLogStarted = True
        elif mediaType == "show":
            if not self._metadataShowLogStarted:
                logger.doing("adding show to library")
                self._metadataShowLogStarted = True
        else:
            raise ValueError(f"unsupported metadata log media type: {mediaType}")

        # Use logger.info() here instead of logger.value() so additions render as
        # a compact grouped list beneath the one-time header for that media type.
        logger.info(f"{_METADATA_LIBRARY_LOG_CONTINUATION_PREFIX}{name}")

    def _getMetadataLibraryPath(self) -> Path:
        """Return the persistent metadata-library file path."""
        return METADATA_LIBRARY_FILE

    def _metadataScanPath(self, baseDir: Path, stem: Optional[str] = None) -> Path:
        """Return a synthetic media path used to reuse the existing MCM readers."""
        if stem is None:
            return baseDir / _METADATA_SCAN_PLACEHOLDER_FILENAME
        return baseDir / f"{stem}{_METADATA_SCAN_SUFFIX}"

    def _newMetadataLibrary(self) -> dict:
        """Return an empty metadata-library structure."""
        return {
            "version": 1,
            "movies": {},
            "tv": {"series": {}, "episodes": {}},
        }

    def _loadMetadataLibrary(self) -> dict:
        """Load the metadata library once per organizer instance."""
        cached = getattr(self, "_metadataLibraryCache", None)
        if cached is not None:
            return cached

        libraryPath = self._getMetadataLibraryPath()
        if not libraryPath.exists():
            self._metadataLibraryLoadState = _METADATA_LIBRARY_STATE_MISSING
            self._metadataLibraryCache = self._newMetadataLibrary()
            return self._metadataLibraryCache

        try:
            loaded = json.loads(libraryPath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
            logger.warning("could not read metadata library %s: %s", libraryPath, error)
            self._metadataLibraryLoadState = _METADATA_LIBRARY_STATE_INVALID
            loaded = self._newMetadataLibrary()

        if not isinstance(loaded, dict):
            self._metadataLibraryLoadState = _METADATA_LIBRARY_STATE_INVALID
            loaded = self._newMetadataLibrary()

        loaded.setdefault("version", 1)
        loaded.setdefault("movies", {})
        loaded.setdefault("tv", {})
        loaded["tv"].setdefault("series", {})
        loaded["tv"].setdefault("episodes", {})
        if self._metadataLibraryLoadState != _METADATA_LIBRARY_STATE_INVALID:
            self._metadataLibraryLoadState = _METADATA_LIBRARY_STATE_READY
        self._metadataLibraryCache = loaded
        return loaded

    def _saveMetadataLibrary(self) -> None:
        """
        Persist the in-memory metadata library for reuse on later runs.

        The cache is written even in dry-run mode because it is application state
        used to avoid unnecessary library rescans on subsequent executions. This
        differs from media-file operations, which still respect dry-run mode.
        """
        library = self._loadMetadataLibrary()
        libraryPath = self._getMetadataLibraryPath()
        libraryPath.parent.mkdir(parents=True, exist_ok=True)
        libraryPath.write_text(
            json.dumps(library, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._metadataLibraryLoadState = _METADATA_LIBRARY_STATE_READY

    def _resetMetadataLibrary(self) -> None:
        """Clear in-memory metadata state before a full rebuild."""
        self._metadataLibraryCache = self._newMetadataLibrary()
        self._metadataLibraryLoadState = _METADATA_LIBRARY_STATE_READY
        self._metadataMovieLogStarted = False
        self._metadataShowLogStarted = False

    def _metadataUpdatedAt(self) -> str:
        """Return an ISO-8601 UTC timestamp for metadata updates."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _normaliseLookupText(self, value: Optional[str]) -> Optional[str]:
        """Return a loose lookup key for titles and show names."""
        if not value:
            return None
        collapsed = "".join(ch.lower() for ch in value if ch.isalnum())
        return collapsed or None

    def _normaliseEpisodeValue(self, value) -> Optional[int]:
        """Return *value* as an integer episode/season number when possible."""
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normaliseIdValue(self, value) -> Optional[str]:
        """Return *value* as a non-empty string identifier when possible."""
        if value in (None, ""):
            return None
        return str(value)

    def _normaliseTvMetadata(self, tvInfo: Optional[dict]) -> Optional[dict]:
        """Return TV metadata in a stable shape."""
        if not tvInfo:
            return None

        normalised = dict(tvInfo)
        normalised["type"] = "tv"
        normalised["showName"] = normalised.get("showName") or None
        normalised["season"] = self._normaliseEpisodeValue(normalised.get("season"))
        normalised["episode"] = self._normaliseEpisodeValue(normalised.get("episode"))
        normalised["episodeTitle"] = normalised.get("episodeTitle") or None
        normalised["imdbId"] = normalised.get("imdbId") or None
        normalised["seriesId"] = self._normaliseIdValue(normalised.get("seriesId"))
        normalised["episodeId"] = self._normaliseIdValue(normalised.get("episodeId"))
        normalised["metadataSource"] = normalised.get("metadataSource") or None
        normalised["metadataUpdatedAt"] = (
            normalised.get("metadataUpdatedAt") or self._metadataUpdatedAt()
        )
        return normalised

    def _mergeMetadata(
        self, primary: Optional[dict], fallback: Optional[dict]
    ) -> Optional[dict]:
        """Merge *fallback* values into *primary* without overwriting populated fields."""
        if primary is None:
            return dict(fallback) if fallback else None
        if fallback is None:
            return dict(primary)

        merged = dict(primary)
        for key, value in fallback.items():
            if merged.get(key) in (None, "") and value not in (None, ""):
                merged[key] = value
        return merged

    def _tvEpisodeLibraryKeys(self, tvInfo: Optional[dict]) -> list[str]:
        """Return metadata-library lookup keys for a TV episode."""
        if not tvInfo:
            return []

        keys = []
        episodeId = tvInfo.get("episodeId")
        if episodeId:
            keys.append(f"episode:{episodeId}")

        season = tvInfo.get("season")
        episode = tvInfo.get("episode")
        if season is not None and episode is not None:
            if tvInfo.get("seriesId"):
                keys.append(f"series:{tvInfo['seriesId']}:s{season:02d}e{episode:02d}")
            showKey = self._normaliseLookupText(tvInfo.get("showName"))
            if showKey:
                keys.append(f"show:{showKey}:s{season:02d}e{episode:02d}")
        return keys

    def _tvSeriesLibraryKeys(self, tvInfo: Optional[dict]) -> list[str]:
        """Return metadata-library lookup keys for a TV series."""
        if not tvInfo:
            return []

        keys = []
        if tvInfo.get("seriesId"):
            keys.append(f"series:{tvInfo['seriesId']}")
        showKey = self._normaliseLookupText(tvInfo.get("showName"))
        if showKey:
            keys.append(f"show:{showKey}")
        return keys

    def _movieLibraryKeys(self, movieInfo: Optional[dict]) -> list[str]:
        """Return metadata-library lookup keys for a movie."""
        if not movieInfo:
            return []

        keys = []
        if movieInfo.get("imdbId"):
            keys.append(f"imdb:{movieInfo['imdbId']}")
        if movieInfo.get("tmdbId"):
            keys.append(f"tmdb:{movieInfo['tmdbId']}")
        titleKey = self._normaliseLookupText(movieInfo.get("title"))
        if titleKey and movieInfo.get("year"):
            keys.append(f"title:{titleKey}:{movieInfo['year']}")
        return keys

    def _storeMetadataRecord(self, bucket: dict, keys: list[str], record: dict) -> bool:
        """Store *record* under *keys* and return True when anything changed."""
        changed = False
        for key in keys:
            existing = bucket.get(key)
            merged = self._mergeMetadata(record, existing)
            if existing != merged:
                bucket[key] = merged
                changed = True
        return changed

    def _firstStoredMetadataRecord(
        self, bucket: dict, keys: list[str]
    ) -> Optional[dict]:
        """Return the first record found in `bucket` following the alias order in `keys`."""
        for key in keys:
            existing = bucket.get(key)
            if existing is not None:
                return existing
        return None

    def _updateMetadataLibraryFromHints(
        self, metadata: Optional[dict]
    ) -> Optional[dict]:
        """Merge local or scraped metadata into the in-memory/persistent library."""
        if not metadata or metadata.get("type") not in {"movie", "tv"}:
            return metadata

        library = self._loadMetadataLibrary()
        changed = False

        if metadata.get("type") == "movie":
            record = dict(metadata)
            record["metadataUpdatedAt"] = (
                record.get("metadataUpdatedAt") or self._metadataUpdatedAt()
            )
            changed = self._storeMetadataRecord(
                library["movies"], self._movieLibraryKeys(record), record
            )
            if changed:
                self._logMetadataLibraryAddition(
                    "movie", record.get("title") or "unknown movie"
                )
        else:
            record = self._normaliseTvMetadata(metadata)
            if record is None:
                return metadata
            isEpisodeLevelHint = any(
                record.get(field) not in (None, "")
                for field in ("season", "episode", "episodeId", "episodeTitle")
            )
            seriesKeys = self._tvSeriesLibraryKeys(record)
            existingSeries = self._firstStoredMetadataRecord(
                library["tv"]["series"], seriesKeys
            )
            seriesRecord = {
                "type": "tv",
                "showName": record.get("showName"),
                "seriesId": record.get("seriesId"),
                "imdbId": record.get("imdbId"),
                "metadataSource": record.get("metadataSource"),
                "metadataUpdatedAt": record.get("metadataUpdatedAt"),
            }
            if record.get("mcm") is not None:
                seriesRecord["mcm"] = record.get("mcm")
            if existingSeries and metadata.get("metadataUpdatedAt") is None:
                # Preserve the stored series timestamp so episode-only updates do
                # not make the series record look newly changed each time. When
                # metadataUpdatedAt is present in `metadata`, that explicit
                # series-level refresh timestamp should win instead.
                seriesRecord["metadataUpdatedAt"] = existingSeries.get(
                    "metadataUpdatedAt"
                )
            if existingSeries and isEpisodeLevelHint:
                # Preserve the stored series record when processing episode
                # hints so the same show is not logged repeatedly.
                seriesRecord = dict(existingSeries)
            seriesChanged = self._storeMetadataRecord(
                library["tv"]["series"],
                seriesKeys,
                seriesRecord,
            )
            if seriesChanged:
                self._logMetadataLibraryAddition(
                    "show", record.get("showName") or "unknown show"
                )
            changed = seriesChanged or changed
            changed = (
                self._storeMetadataRecord(
                    library["tv"]["episodes"],
                    self._tvEpisodeLibraryKeys(record),
                    record,
                )
                or changed
            )

        if changed:
            self._saveMetadataLibrary()
        return metadata

    def _readTvSeriesMcmHints(self, showDir: Path) -> Optional[dict]:
        """Return show-level TV metadata hints from a library show's ``series.xml``."""
        seriesFile = showDir / "series.xml"
        seriesRoot = self._readXmlRoot(seriesFile)
        showName = self._readFirstXmlText(seriesRoot, ("LocalTitle", "SeriesName"))
        imdbId = self._readFirstXmlText(seriesRoot, ("IMDB_ID", "IMDbId"))
        seriesId = self._readFirstXmlText(seriesRoot, ("SeriesID", "id"))
        try:
            seasonMetadataDirs = [
                item for item in showDir.glob("Season*/metadata") if item.is_dir()
            ]
        except OSError as error:
            logger.warning(
                "could not inspect show metadata folders %s: %s", showDir, error
            )
            seasonMetadataDirs = []

        mcmPresence = {
            "showXmlExists": seriesFile.exists(),
            "dvdIdXmlExists": self._hasMatchingFiles(showDir, ("mcm_id__*.dvdid.xml",)),
            "seasonMetadataFolderExists": bool(seasonMetadataDirs),
            "episodeXmlExists": self._hasMatchingFiles(
                showDir, ("Season*/metadata/*.xml",)
            ),
            "artworkExists": self._hasMatchingFiles(
                showDir,
                ("folder.jpg", "banner.jpg", "backdrop*.jpg", "Season*/folder.jpg"),
            ),
        }

        if not self._hasAnyMetadata(
            showName=showName, imdbId=imdbId, seriesId=seriesId
        ) and not any(mcmPresence.values()):
            return None

        return {
            "type": "tv",
            "showName": showName,
            "imdbId": imdbId,
            "seriesId": seriesId,
            "metadataSource": "mcm",
            "mcm": mcmPresence,
        }

    def _buildMetadataLibraryFromStorage(
        self, movieDirs: list[Path], videoDirs: list[Path]
    ) -> None:
        """Preload the metadata library from existing movie/TV storage MCM files."""
        logger.doing("building metadata library from storage")

        for movieDir in movieDirs:
            if not movieDir.exists() or not movieDir.is_dir():
                continue
            logger.value("movie metadata storage", movieDir)

            for movieXml in sorted(movieDir.rglob("movie.xml")):
                self._updateMetadataLibraryFromHints(
                    self._readMovieMcmHints(self._metadataScanPath(movieXml.parent))
                )

        for tvDir in videoDirs:
            if not tvDir.exists() or not tvDir.is_dir():
                continue
            logger.value("TV metadata storage", tvDir)

            try:
                showDirs = sorted(
                    [showDir for showDir in tvDir.iterdir() if showDir.is_dir()]
                )
            except OSError as error:
                logger.warning(
                    "could not read TV metadata storage %s: %s", tvDir, error
                )
                continue
            for showDir in showDirs:
                self._updateMetadataLibraryFromHints(
                    self._readTvSeriesMcmHints(showDir)
                )
                for episodeXml in sorted(showDir.rglob("metadata/*.xml")):
                    self._updateMetadataLibraryFromHints(
                        self._readTvMcmHints(
                            self._metadataScanPath(
                                episodeXml.parent.parent, stem=episodeXml.stem
                            )
                        )
                    )

        logger.done("building metadata library from storage")

    def _prepareMetadataLibrary(
        self, movieDirs: list[Path], videoDirs: list[Path]
    ) -> None:
        """Load cached metadata, or rebuild it from storage when requested."""
        self._loadMetadataLibrary()
        libraryPath = self._getMetadataLibraryPath()
        loadState = self._metadataLibraryLoadState or "missing"

        if self.refreshMetadataLibrary or loadState in {
            _METADATA_LIBRARY_STATE_MISSING,
            _METADATA_LIBRARY_STATE_INVALID,
        }:
            if self.refreshMetadataLibrary:
                logger.value("refreshing metadata library", libraryPath)
            self._resetMetadataLibrary()
            self._buildMetadataLibraryFromStorage(movieDirs, videoDirs)
            return

        logger.value("using saved metadata library", libraryPath)

    def _lookupTvMetadataInLibrary(self, tvInfo: Optional[dict]) -> Optional[dict]:
        """Return the best matching TV metadata record from the library."""
        normalised = self._normaliseTvMetadata(tvInfo)
        if normalised is None:
            return None

        library = self._loadMetadataLibrary()
        merged = None
        for key in self._tvSeriesLibraryKeys(normalised):
            merged = self._mergeMetadata(merged, library["tv"]["series"].get(key))
        for key in self._tvEpisodeLibraryKeys(normalised):
            merged = self._mergeMetadata(merged, library["tv"]["episodes"].get(key))
        return merged

    def _resolveCanonicalTvShowName(
        self,
        resolved: dict,
        libraryMatch: Optional[dict],
        *,
        keepExistingShowName: bool = False,
    ) -> dict:
        """Return *resolved* with a canonical show name when one can be inferred."""
        if keepExistingShowName and resolved.get("showName"):
            return resolved

        canonicalShowName = (libraryMatch or {}).get("showName")
        if canonicalShowName:
            resolved["showName"] = canonicalShowName
        return resolved

    def _enrichTvMetadata(self, tvInfo: Optional[dict]) -> Optional[dict]:
        """Resolve TV metadata from local hints, library cache, and optional scraper data."""
        resolved = self._normaliseTvMetadata(tvInfo)
        if resolved is None:
            return None

        sourceIsMcm = resolved.get("metadataSource") == "mcm"
        libraryMatch = self._lookupTvMetadataInLibrary(resolved)
        resolved = self._mergeMetadata(resolved, libraryMatch)
        resolved = self._resolveCanonicalTvShowName(
            resolved,
            libraryMatch,
            keepExistingShowName=sourceIsMcm,
        )
        if (
            resolved.get("episodeTitle")
            or resolved.get("season") is None
            or resolved.get("episode") is None
        ):
            return resolved

        logger.action(
            "fetch TV metadata: %s S%02dE%02d",
            resolved.get("showName") or "unknown show",
            resolved["season"],
            resolved["episode"],
        )
        scraped = self._fetchTvMetadataFromScraper(resolved)
        if not scraped:
            return resolved

        resolved = self._mergeMetadata(resolved, self._normaliseTvMetadata(scraped))
        resolved = self._resolveCanonicalTvShowName(
            resolved,
            self._lookupTvMetadataInLibrary(resolved),
            keepExistingShowName=sourceIsMcm,
        )
        self._updateMetadataLibraryFromHints(resolved)
        return resolved

    def _fetchTvMetadataFromScraper(self, tvInfo: dict) -> Optional[dict]:
        """Return scraped TV metadata for `tvInfo` using a custom fetcher or built-in providers."""
        fetcher = getattr(self, "_tvMetadataFetcher", None)
        if callable(fetcher):
            try:
                custom = fetcher(tvInfo)
                if custom:
                    return custom
            except Exception as error:
                logger.warning(
                    "custom TV metadata fetcher failed for %s: %s", tvInfo, error
                )
        return self._fetchTvMetadataFromProviders(tvInfo)

    def _fetchTvMetadataFromProviders(self, tvInfo: dict) -> Optional[dict]:
        """Return TV metadata using the default provider order (TVDB then IMDb)."""
        for fetcher in (self._fetchTvdbMetadata, self._fetchImdbMetadata):
            fetched = fetcher(tvInfo)
            if fetched and fetched.get("episodeTitle"):
                return fetched
        return None

    def _getTvdbToken(self) -> Optional[str]:
        """
        Return a TVDB bearer token from configured environment variables.

        Supported configuration:
        - ``ORGANISEMYVIDEO_TVDB_TOKEN`` for a pre-issued bearer token
        - ``ORGANISEMYVIDEO_TVDB_API_KEY`` for TVDB API login
        - ``ORGANISEMYVIDEO_TVDB_PIN`` for API logins that also require a PIN
        """
        envToken = os.environ.get("ORGANISEMYVIDEO_TVDB_TOKEN")
        if envToken:
            return envToken

        apiKey = os.environ.get("ORGANISEMYVIDEO_TVDB_API_KEY")
        if not apiKey:
            apiKey = self._promptForTvdbApiKeyIfNeeded()
            if not apiKey:
                return None

        payload = {"apikey": apiKey}
        pin = os.environ.get("ORGANISEMYVIDEO_TVDB_PIN")
        if pin:
            payload["pin"] = pin

        response = self._requestJson(
            f"{TVDB_API_BASE_URL}/login",
            method="POST",
            payload=payload,
            headers={},
        )
        if not response:
            return None

        data = response.get("data", response)
        if isinstance(data, dict):
            return data.get("token")
        return None

    def _requestJson(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> Optional[dict]:
        """Return decoded JSON for *url*, or None if the request fails."""
        if not url.startswith("https://"):
            raise ValueError(f"refusing to fetch non-https URL: {url!r}")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"refusing malformed metadata URL: {url!r}")

        requestHeaders = {"Accept": "application/json", "User-Agent": "organiseMyVideo"}
        if headers:
            requestHeaders.update(headers)

        requestData = None
        if payload is not None:
            requestHeaders.setdefault("Content-Type", "application/json")
            requestData = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=requestData,
            headers=requestHeaders,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                contentLength = response.headers.get("Content-Length")
                if contentLength and int(contentLength) > 1_000_000:
                    logger.warning("TV metadata response too large for %s", url)
                    return None
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    logger.warning("TV metadata response too large for %s", url)
                    return None
                return json.loads(raw.decode("utf-8"))
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
            OSError,
            UnicodeDecodeError,
            ValueError,
        ) as error:
            logger.warning("TV metadata request failed for %s: %s", url, error)
            return None

    def _tvdbEpisodeRecord(self, payload: Optional[dict]) -> Optional[dict]:
        """Return a normalized TV episode record from a TVDB response payload."""
        if not payload:
            return None

        data = payload.get("data", payload)
        if isinstance(data, list):
            for item in data:
                record = self._tvdbEpisodeRecord(item)
                if record:
                    return record
            return None

        if not isinstance(data, dict):
            return None

        season = self._normaliseEpisodeValue(
            data.get("seasonNumber") or data.get("airedSeason") or data.get("season")
        )
        episode = self._normaliseEpisodeValue(
            data.get("number")
            or data.get("episodeNumber")
            or data.get("airedEpisodeNumber")
            or data.get("episode")
        )
        showName = data.get("seriesName") or data.get("series") or data.get("name")
        if isinstance(showName, dict):
            showName = showName.get("name")

        seriesId = data.get("seriesId")
        if seriesId is None and isinstance(data.get("series"), dict):
            seriesId = data["series"].get("id")

        episodeTitle = data.get("episodeName") or data.get("name")
        if self._normaliseLookupText(episodeTitle) == self._normaliseLookupText(
            showName
        ):
            episodeTitle = None

        return self._normaliseTvMetadata(
            {
                "type": "tv",
                "showName": showName,
                "season": season,
                "episode": episode,
                "episodeTitle": episodeTitle,
                "seriesId": seriesId,
                "episodeId": data.get("id"),
                "imdbId": data.get("imdbId"),
                "metadataSource": "tvdb",
                "metadataUpdatedAt": self._metadataUpdatedAt(),
            }
        )

    def _fetchTvdbMetadata(self, tvInfo: dict) -> Optional[dict]:
        """Fetch TV metadata from TVDB when configuration is available."""
        token = self._getTvdbToken()
        if not token:
            logger.info(
                "TVDB credentials not configured; skipping TV metadata enrichment"
            )
            return None

        headers = {"Authorization": f"Bearer {token}"}

        episodeId = tvInfo.get("episodeId")
        if episodeId:
            record = self._tvdbEpisodeRecord(
                self._requestJson(
                    f"{TVDB_API_BASE_URL}/episodes/{episodeId}/extended",
                    headers=headers,
                )
            )
            if record and record.get("episodeTitle"):
                return record

        seriesId = tvInfo.get("seriesId")
        season = tvInfo.get("season")
        episode = tvInfo.get("episode")
        if seriesId and season is not None and episode is not None:
            record = self._tvdbEpisodeRecord(
                self._requestJson(
                    f"{TVDB_API_BASE_URL}/series/{seriesId}/episodes/default/{season}/{episode}",
                    headers=headers,
                )
            )
            if record and record.get("episodeTitle"):
                return record

        showName = tvInfo.get("showName")
        if not showName:
            return None

        query = urllib.parse.urlencode({"query": showName, "type": "series"})
        searchPayload = self._requestJson(
            f"{TVDB_API_BASE_URL}/search?{query}",
            headers=headers,
        )
        searchResults = (
            searchPayload.get("data", []) if isinstance(searchPayload, dict) else []
        )
        for result in searchResults:
            resultId = result.get("tvdb_id") or result.get("id")
            if not resultId or season is None or episode is None:
                continue
            record = self._tvdbEpisodeRecord(
                self._requestJson(
                    f"{TVDB_API_BASE_URL}/series/{resultId}/episodes/default/{season}/{episode}",
                    headers=headers,
                )
            )
            if record and record.get("episodeTitle"):
                return record

        return None

    def _fetchImdbMetadata(self, tvInfo: dict) -> Optional[dict]:
        """Fetch TV episode metadata from IMDb via OMDb when configuration is available."""
        apiKey = os.environ.get("ORGANISEMYVIDEO_OMDB_API_KEY")
        if not apiKey:
            return None

        season = tvInfo.get("season")
        episode = tvInfo.get("episode")
        if season is None or episode is None:
            return None

        query = {"apikey": apiKey, "Season": str(season), "Episode": str(episode)}
        imdbId = tvInfo.get("imdbId")
        if imdbId:
            query["i"] = imdbId
        elif tvInfo.get("showName"):
            query["t"] = tvInfo["showName"]
        else:
            return None

        response = self._requestJson(
            f"{_OMDB_API_BASE_URL}?{urllib.parse.urlencode(query)}"
        )
        if not isinstance(response, dict):
            return None
        if str(response.get("Response", "")).lower() == "false":
            return None

        episodeTitle = response.get("Title")
        if not episodeTitle:
            return None

        return self._normaliseTvMetadata(
            {
                "type": "tv",
                "showName": response.get("seriesTitle")
                or response.get("SeriesTitle")
                or tvInfo.get("showName"),
                "season": response.get("Season") or season,
                "episode": response.get("Episode") or episode,
                "episodeTitle": episodeTitle,
                "seriesId": tvInfo.get("seriesId"),
                "episodeId": tvInfo.get("episodeId"),
                "imdbId": response.get("imdbID") or tvInfo.get("imdbId"),
                "metadataSource": "imdb",
                "metadataUpdatedAt": self._metadataUpdatedAt(),
            }
        )

    # -----------------------------------------------------------------------
    # Movie metadata enrichment
    # -----------------------------------------------------------------------

    def _normaliseMovieMetadata(self, movieInfo: Optional[dict]) -> Optional[dict]:
        """Return movie metadata in a stable shape."""
        if not movieInfo:
            return None

        normalised = dict(movieInfo)
        normalised["type"] = "movie"
        normalised["title"] = normalised.get("title") or None
        normalised["year"] = normalised.get("year") or None
        normalised["imdbId"] = self._normaliseIdValue(normalised.get("imdbId"))
        normalised["tmdbId"] = self._normaliseIdValue(normalised.get("tmdbId"))
        normalised["metadataSource"] = normalised.get("metadataSource") or None
        normalised["metadataUpdatedAt"] = (
            normalised.get("metadataUpdatedAt") or self._metadataUpdatedAt()
        )
        return normalised

    def _lookupMovieMetadataInLibrary(
        self, movieInfo: Optional[dict]
    ) -> Optional[dict]:
        """Return the best matching movie metadata record from the library."""
        if not movieInfo:
            return None

        library = self._loadMetadataLibrary()
        merged = None
        for key in self._movieLibraryKeys(movieInfo):
            merged = self._mergeMetadata(merged, library["movies"].get(key))
        return merged

    def _enrichMovieMetadata(self, movieInfo: Optional[dict]) -> Optional[dict]:
        """Resolve movie metadata from local hints, library cache, and optional scraper data."""
        resolved = self._normaliseMovieMetadata(movieInfo)
        if resolved is None:
            return None

        libraryMatch = self._lookupMovieMetadataInLibrary(resolved)
        resolved = self._mergeMetadata(resolved, libraryMatch)

        if resolved.get("imdbId") and resolved.get("tmdbId"):
            return resolved

        if not resolved.get("title"):
            return resolved

        logger.action(
            "fetch movie metadata: %s (%s)",
            resolved.get("title") or "unknown title",
            resolved.get("year") or "unknown year",
        )
        scraped = self._fetchMovieMetadataFromScraper(resolved)
        if not scraped:
            return resolved

        resolved = self._mergeMetadata(resolved, self._normaliseMovieMetadata(scraped))
        self._updateMetadataLibraryFromHints(resolved)
        return resolved

    def _fetchMovieMetadataFromScraper(self, movieInfo: dict) -> Optional[dict]:
        """Return scraped movie metadata using a custom fetcher or built-in providers."""
        fetcher = getattr(self, "_movieMetadataFetcher", None)
        if callable(fetcher):
            try:
                custom = fetcher(movieInfo)
                if custom:
                    return custom
            except Exception as error:
                logger.warning(
                    "custom movie metadata fetcher failed for %s: %s", movieInfo, error
                )
        return self._fetchMovieMetadataFromProviders(movieInfo)

    def _fetchMovieMetadataFromProviders(self, movieInfo: dict) -> Optional[dict]:
        """Return movie metadata using the default provider order (TMDB then OMDb)."""
        for fetcher in (self._fetchTmdbMovieMetadata, self._fetchOmdbMovieMetadata):
            fetched = fetcher(movieInfo)
            if fetched and (fetched.get("imdbId") or fetched.get("tmdbId")):
                return fetched
        return None

    def _fetchTmdbMovieMetadata(self, movieInfo: dict) -> Optional[dict]:
        """Fetch movie metadata from TMDB when configuration is available."""
        apiKey = os.environ.get("ORGANISEMYVIDEO_TMDB_API_KEY")
        if not apiKey:
            return None

        tmdbId = movieInfo.get("tmdbId")
        title = movieInfo.get("title")

        if tmdbId:
            # JWT bearer tokens start with "ey" (base64-encoded '{"'); plain API keys do not.
            if apiKey.startswith("ey"):
                data = self._requestJson(
                    f"{TMDB_API_BASE_URL}/movie/{tmdbId}",
                    headers={"Authorization": f"Bearer {apiKey}"},
                )
            else:
                params = urllib.parse.urlencode({"api_key": apiKey})
                data = self._requestJson(f"{TMDB_API_BASE_URL}/movie/{tmdbId}?{params}")
            if data and isinstance(data, dict) and not data.get("status_code"):
                return self._tmdbMovieRecord(data)

        if not title:
            return None

        queryParams: dict = {"query": title}
        if movieInfo.get("year"):
            queryParams["year"] = movieInfo["year"]

        # JWT bearer tokens start with "ey" (base64-encoded '{"'); plain API keys do not.
        if apiKey.startswith("ey"):
            queryStr = urllib.parse.urlencode(queryParams)
            searchData = self._requestJson(
                f"{TMDB_API_BASE_URL}/search/movie?{queryStr}",
                headers={"Authorization": f"Bearer {apiKey}"},
            )
        else:
            queryParams["api_key"] = apiKey
            queryStr = urllib.parse.urlencode(queryParams)
            searchData = self._requestJson(
                f"{TMDB_API_BASE_URL}/search/movie?{queryStr}"
            )

        if not isinstance(searchData, dict):
            return None

        results = searchData.get("results", [])
        if not results:
            return None

        return self._tmdbMovieRecord(results[0])

    def _tmdbMovieRecord(self, data: dict) -> Optional[dict]:
        """Return a normalised movie record from a TMDB movie response."""
        if not isinstance(data, dict):
            return None

        title = data.get("title") or data.get("original_title")
        if not title:
            return None

        tmdbId = self._normaliseIdValue(data.get("id"))
        imdbId = data.get("imdb_id") or None
        releaseDate = data.get("release_date") or ""
        year = releaseDate[:4] if len(releaseDate) >= 4 else None

        return self._normaliseMovieMetadata(
            {
                "type": "movie",
                "title": title,
                "year": year,
                "imdbId": imdbId,
                "tmdbId": tmdbId,
                "posterPath": data.get("poster_path") or None,
                "backdropPath": data.get("backdrop_path") or None,
                "metadataSource": "tmdb",
                "metadataUpdatedAt": self._metadataUpdatedAt(),
            }
        )

    def _fetchOmdbMovieMetadata(self, movieInfo: dict) -> Optional[dict]:
        """Fetch movie metadata from OMDb when configuration is available."""
        apiKey = os.environ.get("ORGANISEMYVIDEO_OMDB_API_KEY")
        if not apiKey:
            return None

        query: dict = {"apikey": apiKey, "type": "movie"}
        imdbId = movieInfo.get("imdbId")
        if imdbId:
            query["i"] = imdbId
        elif movieInfo.get("title"):
            query["t"] = movieInfo["title"]
            if movieInfo.get("year"):
                query["y"] = movieInfo["year"]
        else:
            return None

        response = self._requestJson(
            f"{_OMDB_API_BASE_URL}?{urllib.parse.urlencode(query)}"
        )
        if not isinstance(response, dict):
            return None
        if str(response.get("Response", "")).lower() == "false":
            return None

        title = response.get("Title")
        if not title:
            return None

        year = response.get("Year")
        if year and len(year) >= 4:
            year = year[:4]

        return self._normaliseMovieMetadata(
            {
                "type": "movie",
                "title": title,
                "year": year,
                "imdbId": response.get("imdbID") or movieInfo.get("imdbId"),
                "tmdbId": movieInfo.get("tmdbId"),
                "posterUrl": response.get("Poster") or None,
                "metadataSource": "omdb",
                "metadataUpdatedAt": self._metadataUpdatedAt(),
            }
        )

    def _downloadArtworkFile(self, url: str, destPath: Path) -> bool:
        """
        Download artwork from *url* and save it to *destPath*.

        Returns True on success, False on failure.  Existing files are preserved.
        """
        if destPath.exists():
            logger.value("preserving existing artwork", destPath)
            return True

        if not url or not url.startswith("https://"):
            return False

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            return False

        logger.action("download artwork: %s -> %s", url, destPath)
        if self.dryRun:
            return True

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "organiseMyVideo"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                contentLength = response.headers.get("Content-Length")
                if contentLength and int(contentLength) > _MAX_ARTWORK_SIZE_BYTES:
                    logger.warning("artwork response too large from %s", url)
                    return False
                raw = response.read(_MAX_ARTWORK_SIZE_BYTES + 1)
                if len(raw) > _MAX_ARTWORK_SIZE_BYTES:
                    logger.warning("artwork response too large from %s", url)
                    return False
                destPath.parent.mkdir(parents=True, exist_ok=True)
                destPath.write_bytes(raw)
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as error:
            logger.warning("artwork download failed for %s: %s", url, error)
            return False

    def _fetchMovieArtwork(self, movieInfo: dict, destDir: Path) -> None:
        """
        Download movie artwork (poster → folder.jpg, backdrop → backdrop.jpg).

        Uses TMDB paths when available, then falls back to the OMDb Poster URL.
        Existing files are always preserved.
        """
        posterDest = destDir / "folder.jpg"
        backdropDest = destDir / "backdrop.jpg"

        posterUrl: Optional[str] = None
        backdropUrl: Optional[str] = None

        posterPath = movieInfo.get("posterPath")
        backdropPath = movieInfo.get("backdropPath")
        if posterPath:
            posterUrl = f"{TMDB_IMAGE_BASE_URL}{posterPath}"
        if backdropPath:
            backdropUrl = f"{TMDB_IMAGE_BASE_URL}{backdropPath}"

        if not posterUrl:
            omdbPosterUrl = movieInfo.get("posterUrl")
            if omdbPosterUrl and omdbPosterUrl != "N/A":
                posterUrl = omdbPosterUrl

        if posterUrl:
            self._downloadArtworkFile(posterUrl, posterDest)
        if backdropUrl:
            self._downloadArtworkFile(backdropUrl, backdropDest)
