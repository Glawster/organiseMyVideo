"""Merge duplicate TV-show folders identified by catalogue provider IDs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS
from .filesystemOperations import FilesystemOperations
from .mediaCatalogue import (
    MediaCatalogue,
    TvEpisodeCatalogueRecord,
    TvSeriesCatalogueRecord,
)

logger = getLogger()


@dataclass
class TvMergeStats:
    """Counts produced by one duplicate-TV merge run."""

    groupsFound: int = 0
    groupsMerged: int = 0
    identityConflicts: int = 0
    filesMoved: int = 0
    directoriesMoved: int = 0
    directoriesRemoved: int = 0
    duplicates: int = 0
    conflicts: int = 0
    errors: int = 0


@dataclass(frozen=True)
class TvMergeGroup:
    """One provider-identity group with a selected canonical destination."""

    series: tuple[TvSeriesCatalogueRecord, ...]
    destination: TvSeriesCatalogueRecord


class TvLibraryMerger:
    """Plan or execute merges of duplicate TV-show folders."""

    def __init__(
        self,
        *,
        catalogue: Optional[MediaCatalogue] = None,
        filesystem: Optional[FilesystemOperations] = None,
        dryRun: bool = True,
    ) -> None:
        self.catalogue = catalogue or MediaCatalogue()
        self.filesystem = filesystem or FilesystemOperations(dryRun=dryRun)
        self.dryRun = dryRun
        self.stats = TvMergeStats()

    def merge(self) -> TvMergeStats:
        """Merge every unambiguous duplicate TV-series group in the catalogue."""

        series = [
            row
            for row in self.catalogue.catalogueTvSeriesList()
            if Path(row.folderPath).is_dir()
        ]
        episodes = self.catalogue.catalogueTvEpisodesList()
        groups = self._duplicateGroups(series, episodes)
        self.stats.groupsFound = len(groups)

        for group in groups:
            self._mergeGroup(group, episodes)

        return self.stats

    def _duplicateGroups(
        self,
        series: list[TvSeriesCatalogueRecord],
        episodes: list[TvEpisodeCatalogueRecord],
    ) -> list[TvMergeGroup]:
        """Return duplicate groups linked by matching provider identity."""

        if len(series) < 2:
            return []

        parent = list(range(len(series)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            leftRoot = find(left)
            rightRoot = find(right)
            if leftRoot != rightRoot:
                parent[rightRoot] = leftRoot

        identityOwner: dict[tuple[str, str], int] = {}
        for index, row in enumerate(series):
            for identity in _seriesIdentityTokens(row):
                previous = identityOwner.get(identity)
                if previous is None:
                    identityOwner[identity] = index
                else:
                    union(previous, index)

        grouped: dict[int, list[TvSeriesCatalogueRecord]] = {}
        for index, row in enumerate(series):
            grouped.setdefault(find(index), []).append(row)

        episodeCounts: dict[str, int] = {}
        for episode in episodes:
            episodeCounts[episode.seriesFolderPath] = (
                episodeCounts.get(episode.seriesFolderPath, 0) + 1
            )

        result: list[TvMergeGroup] = []
        for members in grouped.values():
            if len(members) < 2:
                continue
            if _seriesIdentityConflicts(members):
                self.stats.identityConflicts += 1
                logger.warning(
                    "skipping TV merge with conflicting provider IDs: %s",
                    ", ".join(row.folderPath for row in members),
                )
                continue
            destination = max(
                members,
                key=lambda row: _seriesCompleteness(row, episodeCounts),
            )
            ordered = tuple(
                sorted(
                    members,
                    key=lambda row: (
                        row.folderPath != destination.folderPath,
                        row.folderPath.lower(),
                    ),
                )
            )
            result.append(TvMergeGroup(series=ordered, destination=destination))
        return sorted(
            result,
            key=lambda group: (
                group.destination.showName.lower(),
                group.destination.folderPath.lower(),
            ),
        )

    def _mergeGroup(
        self,
        group: TvMergeGroup,
        episodes: list[TvEpisodeCatalogueRecord],
    ) -> None:
        """Merge all non-canonical folders in *group* into its destination."""

        destination = Path(group.destination.folderPath)
        logger.doing(f"merging duplicate TV show: {group.destination.showName}")
        logger.value("merge destination", destination)

        episodeFiles = self._episodeIndex(group, episodes)
        mergedAny = False
        for sourceRow in group.series:
            source = Path(sourceRow.folderPath)
            if source == destination:
                continue
            logger.value("merge source", source)
            try:
                moved = self._mergeDirectory(
                    source,
                    destination,
                    source,
                    episodeFiles,
                )
                mergedAny = mergedAny or moved
                if not self.dryRun and source.is_dir() and not any(source.iterdir()):
                    self.filesystem.removeEmptyDirectory(source, stateKind="media")
                    self.stats.directoriesRemoved += 1
            except (OSError, RuntimeError, ValueError) as error:
                self.stats.errors += 1
                logger.error("could not merge %s into %s: %s", source, destination, error)

        if mergedAny:
            self.stats.groupsMerged += 1

    def _episodeIndex(
        self,
        group: TvMergeGroup,
        episodes: list[TvEpisodeCatalogueRecord],
    ) -> dict[tuple[object, ...], Path]:
        """Return known episode identities, preferring the canonical folder."""

        memberPaths = {row.folderPath for row in group.series}
        destination = group.destination.folderPath
        ordered = sorted(
            (episode for episode in episodes if episode.seriesFolderPath in memberPaths),
            key=lambda episode: (
                episode.seriesFolderPath != destination,
                episode.filePath.lower(),
            ),
        )
        indexed: dict[tuple[object, ...], Path] = {}
        for episode in ordered:
            key = _episodeIdentity(episode)
            if key is not None and key not in indexed:
                indexed[key] = Path(episode.filePath)
        return indexed

    def _mergeDirectory(
        self,
        sourceDir: Path,
        destinationDir: Path,
        seriesSource: Path,
        episodeFiles: dict[tuple[object, ...], Path],
    ) -> bool:
        """Recursively merge *sourceDir* without overwriting destination files."""

        movedAny = False
        try:
            children = sorted(sourceDir.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            raise

        if not destinationDir.exists():
            self.filesystem.move(sourceDir, destinationDir)
            self.stats.directoriesMoved += 1
            return True

        for source in children:
            destination = destinationDir / source.name
            if source.is_dir():
                if not destination.exists():
                    self.filesystem.move(source, destination)
                    self.stats.directoriesMoved += 1
                    movedAny = True
                    continue
                if not destination.is_dir():
                    self._recordConflict(source, destination, "directory/file collision")
                    continue
                childMoved = self._mergeDirectory(
                    source,
                    destination,
                    seriesSource,
                    episodeFiles,
                )
                movedAny = movedAny or childMoved
                if not self.dryRun and source.is_dir() and not any(source.iterdir()):
                    self.filesystem.removeEmptyDirectory(source, stateKind="media")
                    self.stats.directoriesRemoved += 1
                continue

            if not source.is_file():
                self._recordConflict(source, destination, "unsupported filesystem entry")
                continue

            episode = self._episodeForPath(source, seriesSource)
            if episode is not None:
                key = _episodeIdentity(episode)
                existing = episodeFiles.get(key) if key is not None else None
                if existing is not None and existing != source:
                    self._recordExistingEpisode(source, existing)
                    continue

            if destination.exists():
                if destination.is_file():
                    self._recordExistingFile(source, destination)
                else:
                    self._recordConflict(source, destination, "file/directory collision")
                continue

            self.filesystem.move(source, destination)
            self.stats.filesMoved += 1
            movedAny = True
            if episode is not None:
                key = _episodeIdentity(episode)
                if key is not None:
                    episodeFiles[key] = source if self.dryRun else destination

        return movedAny

    def _episodeForPath(
        self, source: Path, seriesSource: Path
    ) -> Optional[TvEpisodeCatalogueRecord]:
        """Return the catalogue episode represented by *source*, if any."""

        if source.suffix.lower() not in VIDEO_EXTENSIONS:
            return None
        sourceText = str(source)
        for episode in self.catalogue.catalogueTvEpisodesList():
            if episode.seriesFolderPath == str(seriesSource) and episode.filePath == sourceText:
                return episode
        return None

    def _recordExistingEpisode(self, source: Path, existing: Path) -> None:
        """Report a duplicate/conflicting episode and preserve both files."""

        if _filesIdentical(source, existing):
            self.stats.duplicates += 1
            logger.warning("duplicate episode preserved: %s; existing %s", source, existing)
        else:
            self._recordConflict(source, existing, "episode identity already exists")

    def _recordExistingFile(self, source: Path, destination: Path) -> None:
        """Report a same-path duplicate or conflict without overwriting."""

        if _filesIdentical(source, destination):
            self.stats.duplicates += 1
            logger.warning("duplicate file preserved: %s; existing %s", source, destination)
        else:
            self._recordConflict(source, destination, "destination already exists")

    def _recordConflict(self, source: Path, destination: Path, reason: str) -> None:
        """Record a merge conflict while leaving both entries untouched."""

        self.stats.conflicts += 1
        logger.warning("merge conflict (%s): %s -> %s", reason, source, destination)


def mergeDuplicateTvShows(
    *,
    catalogue: Optional[MediaCatalogue] = None,
    filesystem: Optional[FilesystemOperations] = None,
    dryRun: bool = True,
) -> TvMergeStats:
    """Convenience service for the ``media organise --merge`` workflow."""

    return TvLibraryMerger(
        catalogue=catalogue,
        filesystem=filesystem,
        dryRun=dryRun,
    ).merge()


def _seriesIdentityTokens(row: TvSeriesCatalogueRecord) -> set[tuple[str, str]]:
    """Return provider/value tokens that can establish series identity."""

    values = {
        "tvdb": row.tvdbId,
        "tmdb": row.tmdbId,
        "imdb": row.imdbId,
    }
    return {
        (provider, value.strip().lower())
        for provider, raw in values.items()
        if raw is not None and (value := str(raw).strip())
    }


def _seriesIdentityConflicts(rows: Iterable[TvSeriesCatalogueRecord]) -> bool:
    """Return True when a linked group contains contradictory provider IDs."""

    for attribute in ("tvdbId", "tmdbId", "imdbId"):
        values = {
            str(getattr(row, attribute)).strip().lower()
            for row in rows
            if getattr(row, attribute) not in (None, "")
        }
        if len(values) > 1:
            return True
    return False


def _seriesCompleteness(
    row: TvSeriesCatalogueRecord, episodeCounts: dict[str, int]
) -> tuple[int, int, int, str]:
    """Rank a TV folder by episodes, video count, bytes, then stable path."""

    root = Path(row.folderPath)
    videoCount = 0
    videoBytes = 0
    try:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            videoCount += 1
            try:
                videoBytes += path.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return (
        episodeCounts.get(row.folderPath, 0),
        videoCount,
        videoBytes,
        row.folderPath.lower(),
    )


def _episodeIdentity(
    episode: TvEpisodeCatalogueRecord,
) -> Optional[tuple[object, ...]]:
    """Return a stable episode key within an already-identified TV series."""

    for provider, raw in (
        ("tvdb", episode.tvdbEpisodeId),
        ("tmdb", episode.tmdbEpisodeId),
        ("imdb", episode.imdbId),
    ):
        if raw not in (None, ""):
            return (provider, str(raw).strip().lower())
    if episode.season is not None and episode.episode is not None:
        return ("number", int(episode.season), int(episode.episode))
    return None


def _filesIdentical(left: Path, right: Path) -> bool:
    """Return True only when two existing regular files have identical bytes."""

    try:
        if not left.is_file() or not right.is_file():
            return False
        if left.stat().st_size != right.stat().st_size:
            return False
        return _fileDigest(left) == _fileDigest(right)
    except OSError:
        return False


def _fileDigest(path: Path) -> str:
    """Return a SHA-256 digest without loading the whole file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
