"""Live, in-memory TV library scanning for maintenance workflows."""

from __future__ import annotations

import os
import re
import shutil
import sys
import urllib.parse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Optional, TextIO

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import TVDB_API_BASE_URL, VIDEO_EXTENSIONS
from .mediaCatalogue import (
    TvEpisodeCatalogueRecord,
    TvSeriesCatalogueRecord,
    _catalogueIdentitySource,
    _tvEpisodeFromFile,
    _tvSeriesFromFolder,
)
from .video import VideoMixin

logger = getLogger()
_SCAN_PROGRESS_BAR_WIDTH = 24


@dataclass(frozen=True)
class TvLibrarySnapshot:
    """One read-only in-memory view of the current TV storage roots."""

    episodes: tuple[TvEpisodeCatalogueRecord, ...]
    series: tuple[TvSeriesCatalogueRecord, ...]

    def catalogueTvEpisodesList(self) -> list[TvEpisodeCatalogueRecord]:
        """Return episode rows using the catalogue-compatible interface."""

        return list(self.episodes)

    def catalogueTvSeriesList(self) -> list[TvSeriesCatalogueRecord]:
        """Return series rows using the catalogue-compatible interface."""

        return list(self.series)


class _TvScanProgress:
    """Single-line terminal progress display for long live-library scans."""

    def __init__(self, total: int, label: str, stream: Optional[TextIO] = None):
        self.total = max(total, 0)
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        isatty = getattr(self.stream, "isatty", None)
        self.enabled = bool(callable(isatty) and isatty())
        self.displayWidth = 0

    def render(self, completed: int, name: str = "") -> None:
        """Render current progress without adding a scrolling log line."""

        if not self.enabled:
            return
        if self.total <= 0:
            bar = "-" * _SCAN_PROGRESS_BAR_WIDTH
            prefix = f"{self.label}: [{bar}]   0% ({completed}/?)"
        else:
            progress = min(completed / self.total, 1.0)
            filled = int(progress * _SCAN_PROGRESS_BAR_WIDTH)
            bar = "#" * filled + "-" * (_SCAN_PROGRESS_BAR_WIDTH - filled)
            prefix = (
                f"{self.label}: [{bar}] {progress * 100:3.0f}% "
                f"({completed}/{self.total})"
            )
        columns = max(shutil.get_terminal_size(fallback=(80, 24)).columns, 20)
        available = columns - len(prefix) - 1
        suffix = ""
        if name and available > 0:
            suffix = " " + _truncateProgressText(name, available)
        line = prefix + suffix
        padding = max(self.displayWidth - len(line), 0)
        self.stream.write(f"\r{line}{' ' * padding}")
        self.stream.flush()
        self.displayWidth = len(line)

    def finish(self) -> None:
        """Finish the live line so subsequent logger output starts cleanly."""

        if self.enabled and self.displayWidth:
            self.stream.write("\n")
            self.stream.flush()
            self.displayWidth = 0


def _truncateProgressText(text: str, maxWidth: int) -> str:
    """Return text shortened to the available terminal width."""

    if len(text) <= maxWidth:
        return text
    if maxWidth <= 3:
        return text[:maxWidth]
    return text[: maxWidth - 3] + "..."


def discoverTvStorageLocations() -> list[Path]:
    """Return current TV roots using the application's established discovery logic."""

    scanner = VideoMixin.__new__(VideoMixin)
    _, videoDirs = scanner.scanStorageLocations()
    return list(videoDirs)


def _showDirectories(roots: list[Path]) -> list[Path]:
    """Return all direct TV-show directories from the supplied roots."""

    shows: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            shows.extend(path for path in root.iterdir() if path.is_dir())
        except OSError:
            continue
    return sorted(shows, key=lambda path: str(path).casefold())


def _collectLiveTvLibrary(
    roots: list[Path], identity
) -> tuple[list[TvEpisodeCatalogueRecord], list[TvSeriesCatalogueRecord]]:
    """Build live records using the catalogue's established record builders."""

    shows = _showDirectories(roots)
    progress = _TvScanProgress(len(shows), "Scanning TV library")
    episodes: list[TvEpisodeCatalogueRecord] = []
    series: list[TvSeriesCatalogueRecord] = []
    seen: set[str] = set()

    try:
        for index, showDir in enumerate(shows, start=1):
            progress.render(index - 1, showDir.name)
            series.append(_tvSeriesFromFolder(showDir, identity))
            for dirPath, dirNames, fileNames in os.walk(showDir):
                dirNames[:] = [name for name in dirNames if not name.startswith(".")]
                current = Path(dirPath)
                seasonHint = identity._inferSeasonFromPath(current)
                for fileName in fileNames:
                    path = current / fileName
                    if path.suffix.lower() not in VIDEO_EXTENSIONS:
                        continue
                    record = _tvEpisodeFromFile(path, showDir, seasonHint, identity)
                    if record.filePath in seen:
                        continue
                    seen.add(record.filePath)
                    episodes.append(record)
            progress.render(index, showDir.name)
    finally:
        progress.finish()

    episodes.sort(
        key=lambda item: (
            item.showName.lower(),
            item.season or 0,
            item.episode or 0,
            item.filePath,
        )
    )
    series.sort(key=lambda item: (item.showName.lower(), item.folderPath))
    return episodes, series


def _seriesHasProviderIdentity(row: TvSeriesCatalogueRecord) -> bool:
    """Return whether *row* already has any provider identity."""

    return any(
        value not in (None, "") for value in (row.tvdbId, row.tmdbId, row.imdbId)
    )


def _seriesLookupName(showName: str, identity) -> str:
    """Return a conservative provider-search name for a library folder/show name."""

    cleaned = re.sub(r"[\s._-]+$", "", showName).strip()
    cleaned = identity._stripResetTvShowDuplicateSuffixes(cleaned)
    return cleaned.strip() or showName.strip()


def _seriesDuplicateKey(row: TvSeriesCatalogueRecord, identity) -> Optional[str]:
    """Return a name key used only to decide which missing identities need lookup."""

    lookupName = _seriesLookupName(row.showName or Path(row.folderPath).name, identity)
    return identity._normaliseLookupText(lookupName)


def _tvdbExactSeriesId(identity, showName: str, token: str) -> Optional[str]:
    """Return one unambiguous exact TVDB series ID, never a fuzzy fallback."""

    query = urllib.parse.urlencode({"query": showName, "type": "series"})
    payload = identity._requestJson(
        f"{TVDB_API_BASE_URL}/search?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if not isinstance(payload, dict):
        return None

    results = payload.get("data", [])
    if not isinstance(results, list):
        return None

    showKey = identity._normaliseLookupText(showName)
    exactIds: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        resultKeys = {
            identity._normaliseLookupText(name)
            for name in identity._tvdbSearchResultNames(result)
        }
        resultKeys.discard(None)
        if showKey not in resultKeys:
            continue
        resultId = result.get("tvdb_id") or result.get("id")
        if resultId not in (None, ""):
            exactIds.add(str(resultId))

    if len(exactIds) != 1:
        if len(exactIds) > 1:
            logger.warning(
                "ambiguous TVDB identity lookup for %s; preserving unresolved identity",
                showName,
            )
        return None
    return next(iter(exactIds))


def _resolveMissingSeriesIdentities(
    series: list[TvSeriesCatalogueRecord], identity
) -> list[TvSeriesCatalogueRecord]:
    """Resolve missing IDs only inside plausible duplicate-name groups."""

    grouped: dict[str, list[int]] = {}
    for index, row in enumerate(series):
        key = _seriesDuplicateKey(row, identity)
        if key:
            grouped.setdefault(key, []).append(index)

    candidates = [
        index
        for indexes in grouped.values()
        if len(indexes) > 1
        for index in indexes
        if not _seriesHasProviderIdentity(series[index])
    ]
    if not candidates:
        return series

    token = identity._getTvdbToken()
    if not token:
        logger.info(
            "TVDB credentials not configured; unresolved duplicate TV identities remain"
        )
        return series

    resolved = list(series)
    cache: dict[str, Optional[str]] = {}
    progress = _TvScanProgress(len(candidates), "Resolving TV identities")
    try:
        for completed, index in enumerate(candidates):
            row = resolved[index]
            lookupName = _seriesLookupName(
                row.showName or Path(row.folderPath).name, identity
            )
            progress.render(completed, lookupName)
            lookupKey = (
                identity._normaliseLookupText(lookupName) or lookupName.casefold()
            )
            if lookupKey not in cache:
                cache[lookupKey] = _tvdbExactSeriesId(identity, lookupName, token)
            tvdbId = cache[lookupKey]
            if tvdbId:
                resolved[index] = replace(row, tvdbId=tvdbId)
                progress.finish()
                logger.value(
                    "resolved TV identity", f"{row.folderPath} -> TVDB {tvdbId}"
                )
            progress.render(completed + 1, lookupName)
    finally:
        progress.finish()

    return resolved


def scanTvLibrary(
    videoDirs: Iterable[Path] | None = None,
) -> TvLibrarySnapshot:
    """Scan current TV storage into records without writing SQLite state."""

    roots = (
        discoverTvStorageLocations()
        if videoDirs is None
        else [Path(path) for path in videoDirs]
    )
    identity = _catalogueIdentitySource()
    episodes, series = _collectLiveTvLibrary(roots, identity)
    series = _resolveMissingSeriesIdentities(series, identity)
    return TvLibrarySnapshot(
        episodes=tuple(episodes),
        series=tuple(series),
    )
