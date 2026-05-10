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

from .constants import METADATA_LIBRARY_FILE, TVDB_API_BASE_URL

logger = getLogger()
_METADATA_SCAN_PLACEHOLDER = "__metadata_scan__.mkv"


class MetadataMixin:
    """Methods for caching local metadata and enriching TV episode details."""

    def _getMetadataLibraryPath(self) -> Path:
        """Return the persistent metadata-library file path."""
        return METADATA_LIBRARY_FILE

    def _metadataScanPath(self, baseDir: Path, stem: Optional[str] = None) -> Path:
        """Return a synthetic media path used to reuse the existing MCM readers."""
        suffix = Path(_METADATA_SCAN_PLACEHOLDER).suffix
        if stem is None:
            return baseDir / _METADATA_SCAN_PLACEHOLDER
        return baseDir / f"{stem}{suffix}"

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
            self._metadataLibraryCache = self._newMetadataLibrary()
            return self._metadataLibraryCache

        try:
            loaded = json.loads(libraryPath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as error:
            logger.warning("could not read metadata library %s: %s", libraryPath, error)
            loaded = self._newMetadataLibrary()

        if not isinstance(loaded, dict):
            loaded = self._newMetadataLibrary()

        loaded.setdefault("version", 1)
        loaded.setdefault("movies", {})
        loaded.setdefault("tv", {})
        loaded["tv"].setdefault("series", {})
        loaded["tv"].setdefault("episodes", {})
        self._metadataLibraryCache = loaded
        return loaded

    def _saveMetadataLibrary(self) -> None:
        """Persist the in-memory metadata library unless running in dry-run mode."""
        library = self._loadMetadataLibrary()
        libraryPath = self._getMetadataLibraryPath()
        logger.action("update metadata library: %s", libraryPath)
        if self.dryRun:
            return

        libraryPath.parent.mkdir(parents=True, exist_ok=True)
        libraryPath.write_text(
            json.dumps(library, indent=2, sort_keys=True),
            encoding="utf-8",
        )

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
                logger.action("adding movies to library")
                logger.value("movie name", record.get("title") or "unknown movie")
        else:
            record = self._normaliseTvMetadata(metadata)
            if record is None:
                return metadata
            seriesRecord = {
                "type": "tv",
                "showName": record.get("showName"),
                "seriesId": record.get("seriesId"),
                "imdbId": record.get("imdbId"),
                "metadataSource": record.get("metadataSource"),
                "metadataUpdatedAt": record.get("metadataUpdatedAt"),
            }
            seriesChanged = self._storeMetadataRecord(
                library["tv"]["series"],
                self._tvSeriesLibraryKeys(record),
                seriesRecord,
            )
            if seriesChanged:
                logger.action("adding shows to library")
                logger.value("show name", record.get("showName") or "unknown show")
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
        seriesRoot = self._readXmlRoot(showDir / "series.xml")
        showName = self._readFirstXmlText(seriesRoot, ("LocalTitle", "SeriesName"))
        imdbId = self._readFirstXmlText(seriesRoot, ("IMDB_ID", "IMDbId"))
        seriesId = self._readFirstXmlText(seriesRoot, ("SeriesID", "id"))

        if not self._hasAnyMetadata(
            showName=showName, imdbId=imdbId, seriesId=seriesId
        ):
            return None

        return {
            "type": "tv",
            "showName": showName,
            "imdbId": imdbId,
            "seriesId": seriesId,
            "metadataSource": "mcm",
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
            showDirs = sorted(path for path in tvDir.iterdir() if path.is_dir())
            for showDir in showDirs:
                self._updateMetadataLibraryFromHints(self._readTvSeriesMcmHints(showDir))
                for episodeXml in sorted(showDir.rglob("metadata/*.xml")):
                    self._updateMetadataLibraryFromHints(
                        self._readTvMcmHints(
                            self._metadataScanPath(
                                episodeXml.parent.parent, stem=episodeXml.stem
                            )
                        )
                    )

        logger.done("building metadata library from storage")

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

    def _enrichTvMetadata(self, tvInfo: Optional[dict]) -> Optional[dict]:
        """Resolve TV metadata from local hints, library cache, and optional scraper data."""
        resolved = self._normaliseTvMetadata(tvInfo)
        if resolved is None:
            return None

        resolved = self._mergeMetadata(
            resolved, self._lookupTvMetadataInLibrary(resolved)
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
        if self.dryRun:
            return resolved

        scraped = self._fetchTvMetadataFromScraper(resolved)
        if not scraped:
            return resolved

        resolved = self._mergeMetadata(resolved, self._normaliseTvMetadata(scraped))
        self._updateMetadataLibraryFromHints(resolved)
        return resolved

    def _fetchTvMetadataFromScraper(self, tvInfo: dict) -> Optional[dict]:
        """Return scraped TV metadata for *tvInfo* using a custom fetcher or TVDB."""
        fetcher = getattr(self, "_tvMetadataFetcher", None)
        if callable(fetcher):
            try:
                return fetcher(tvInfo)
            except Exception as error:
                logger.warning(
                    "custom TV metadata fetcher failed for %s: %s", tvInfo, error
                )
                return None

        return self._fetchTvdbMetadata(tvInfo)

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
