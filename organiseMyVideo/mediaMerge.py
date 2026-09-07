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


class _TvMergeProgress:
    """Track recursive merge work on the established single-line progress display."""

    def __init__(
        self,
        showName: str,
        sourceName: str,
        *,
        stream=None,
    ) -> None:
        from .tvLibraryScan import _TvScanProgress

        self.total = 0
        self.completed = 0
        self.sourceName = sourceName
        self.progress = _TvScanProgress(0, f"Merging {showName}", stream=stream)
        self.progress.render(0, sourceName)

    def setTotal(self, total: int) -> None:
        """Set the descendant count once the source tree has been counted."""

        self.total = max(total, 0)
        self.progress.total = self.total
        self.progress.render(self.completed, self.sourceName)

    def advance(self, count: int = 1, name: Optional[str] = None) -> None:
        """Advance by *count* filesystem entries and refresh the live line."""

        self.completed += max(count, 0)
        if self.total:
            self.completed = min(self.completed, self.total)
        self.progress.render(self.completed, name or self.sourceName)

    def show(self, name: str) -> None:
        """Show the filesystem entry currently being evaluated."""

        self.progress.render(self.completed, name)

    def compareFiles(self, left: Path, right: Path) -> bool:
        """Compare equal-sized files while showing byte-level hashing progress."""

        try:
            leftSize = left.stat().st_size
            rightSize = right.stat().st_size
        except OSError:
            return False
        if leftSize != rightSize:
            return False

        from .tvLibraryScan import _TvScanProgress

        self.pause()
        totalBytes = leftSize + rightSize
        compareProgress = _TvScanProgress(totalBytes, "Comparing duplicate files")
        completedBytes = 0

        def digest(path: Path) -> str:
            nonlocal completedBytes
            value = hashlib.sha256()
            compareProgress.render(completedBytes, path.name)
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    value.update(chunk)
                    completedBytes += len(chunk)
                    compareProgress.render(completedBytes, path.name)
            return value.hexdigest()

        try:
            return digest(left) == digest(right)
        except OSError:
            return False
        finally:
            compareProgress.finish()
            self.resume(left.name)

    def pause(self) -> None:
        """Finish the current live line before ordinary logger output."""

        self.progress.finish()

    def resume(self, name: Optional[str] = None) -> None:
        """Redraw progress after a logger message interrupted the live line."""

        self.progress.render(self.completed, name or self.sourceName)

    def finish(self) -> None:
        """Complete the live merge line."""

        if self.completed < self.total:
            self.completed = self.total
            self.progress.render(self.completed, self.sourceName)
        self.progress.finish()


class TvLibraryMerger:
    """Plan or execute merges of duplicate TV-show folders."""

    def __init__(
        self,
        *,
        catalogue: Optional[MediaCatalogue] = None,
        filesystem: Optional[FilesystemOperations] = None,
        dryRun: bool = True,
        progressStream=None,
    ) -> None:
        self.catalogue = catalogue or MediaCatalogue()
        self.filesystem = filesystem or FilesystemOperations(dryRun=dryRun)
        self.dryRun = dryRun
        self.stats = TvMergeStats()
        self._episodeByPath: dict[tuple[str, str], TvEpisodeCatalogueRecord] = {}
        self.progressStream = progressStream

    def merge(self) -> TvMergeStats:
        """Merge every unambiguous duplicate TV-series group in the catalogue."""

        series = [
            row
            for row in self.catalogue.catalogueTvSeriesList()
            if Path(row.folderPath).is_dir()
        ]
        episodes = self.catalogue.catalogueTvEpisodesList()
        self._episodeByPath = {
            (episode.seriesFolderPath, episode.filePath): episode
            for episode in episodes
        }
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

        candidateGroups = [members for members in grouped.values() if len(members) > 1]
        result: list[TvMergeGroup] = []

        from .tvLibraryScan import _TvScanProgress

        progress = _TvScanProgress(len(candidateGroups), "Planning TV merges")
        try:
            for completed, members in enumerate(candidateGroups):
                displayName = members[0].showName or Path(members[0].folderPath).name
                progress.render(completed, displayName)

                if _seriesIdentityConflicts(members):
                    self.stats.identityConflicts += 1
                    progress.finish()
                    logger.warning(
                        "skipping TV merge with conflicting provider IDs: %s",
                        ", ".join(row.folderPath for row in members),
                    )
                    progress.render(completed + 1, displayName)
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
                progress.render(completed + 1, displayName)
        finally:
            progress.finish()

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
            progress = _TvMergeProgress(
                group.destination.showName,
                source.name,
                stream=self.progressStream,
            )
            try:
                progress.show("counting entries")
                progress.setTotal(_directoryDescendantCount(source))
                moved = self._mergeDirectory(
                    source,
                    destination,
                    source,
                    episodeFiles,
                    progress,
                )
                mergedAny = mergedAny or moved
                if not self.dryRun and source.is_dir() and not any(source.iterdir()):
                    self.filesystem.removeEmptyDirectory(source, stateKind="media")
                    self.stats.directoriesRemoved += 1
            except (OSError, RuntimeError, ValueError) as error:
                progress.pause()
                self.stats.errors += 1
                logger.error(
                    "could not merge %s into %s: %s", source, destination, error
                )
            finally:
                progress.finish()

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
            (
                episode
                for episode in episodes
                if episode.seriesFolderPath in memberPaths
            ),
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
        progress: Optional[_TvMergeProgress] = None,
    ) -> bool:
        """Recursively merge *sourceDir* without overwriting destination files."""

        movedAny = False
        if progress is not None:
            progress.show(f"listing {sourceDir.name}")
        try:
            children = sorted(sourceDir.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            raise

        if not destinationDir.exists():
            self._moveTree(sourceDir, destinationDir, progress)
            return True

        for source in children:
            destination = destinationDir / source.name
            if progress is not None:
                progress.show(source.name)
            if source.is_dir():
                if not destination.exists():
                    self._moveTree(source, destination, progress)
                    movedAny = True
                    continue
                if not destination.is_dir():
                    self._recordConflict(
                        source,
                        destination,
                        "directory/file collision",
                        progress,
                    )
                    if progress is not None:
                        progress.advance(1, source.name)
                    continue
                childMoved = self._mergeDirectory(
                    source,
                    destination,
                    seriesSource,
                    episodeFiles,
                    progress,
                )
                movedAny = movedAny or childMoved
                if not self.dryRun and source.is_dir() and not any(source.iterdir()):
                    self.filesystem.removeEmptyDirectory(source, stateKind="media")
                    self.stats.directoriesRemoved += 1
                if progress is not None:
                    progress.advance(1, source.name)
                continue

            if not source.is_file():
                self._recordConflict(
                    source,
                    destination,
                    "unsupported filesystem entry",
                    progress,
                )
                if progress is not None:
                    progress.advance(1, source.name)
                continue

            episode = self._episodeForPath(source, seriesSource)
            if episode is not None:
                key = _episodeIdentity(episode)
                existing = episodeFiles.get(key) if key is not None else None
                if existing is not None and existing != source:
                    self._recordExistingEpisode(source, existing, progress)
                    if progress is not None:
                        progress.advance(1, source.name)
                    continue

            if destination.exists():
                if destination.is_file():
                    if source.name.casefold() == "series.xml":
                        self._discardRegenerableSeriesMetadata(
                            source,
                            destination,
                            progress,
                        )
                        movedAny = True
                    else:
                        self._recordExistingFile(source, destination, progress)
                else:
                    self._recordConflict(
                        source,
                        destination,
                        "file/directory collision",
                        progress,
                    )
                if progress is not None:
                    progress.advance(1, source.name)
                continue

            if progress is not None:
                progress.advance(1, source.name)
            self.filesystem.move(source, destination)
            self.stats.filesMoved += 1
            movedAny = True
            if episode is not None:
                key = _episodeIdentity(episode)
                if key is not None:
                    episodeFiles[key] = source if self.dryRun else destination
            continue

        return movedAny

    def _moveTree(
        self,
        source: Path,
        destination: Path,
        progress: Optional[_TvMergeProgress] = None,
    ) -> None:
        """Move a missing destination tree and credit all contained entries."""

        if progress is not None:
            progress.show(source.name)
        entryCount = _treeEntryCount(source)
        if progress is not None:
            progress.advance(entryCount, source.name)
        self.filesystem.move(source, destination)
        self.stats.directoriesMoved += 1

    def _discardRegenerableSeriesMetadata(
        self,
        source: Path,
        destination: Path,
        progress: Optional[_TvMergeProgress] = None,
    ) -> None:
        """Keep destination ``series.xml`` and discard the regenerable source copy."""

        if progress is not None:
            progress.pause()
        logger.value("preserving destination series metadata", destination)
        logger.value("removing regenerable source metadata", source)
        self.filesystem.removeFile(source, stateKind="metadata")
        if progress is not None:
            progress.resume(source.name)

    def _episodeForPath(
        self, source: Path, seriesSource: Path
    ) -> Optional[TvEpisodeCatalogueRecord]:
        """Return the catalogue episode represented by *source*, if any."""

        if source.suffix.lower() not in VIDEO_EXTENSIONS:
            return None
        return self._episodeByPath.get((str(seriesSource), str(source)))

    def _recordExistingEpisode(
        self,
        source: Path,
        existing: Path,
        progress: Optional[_TvMergeProgress] = None,
    ) -> None:
        """Report a duplicate/conflicting episode and preserve both files."""

        identical = (
            progress.compareFiles(source, existing)
            if progress is not None
            else _filesIdentical(source, existing)
        )
        if identical:
            if progress is not None:
                progress.pause()
            self.stats.duplicates += 1
            logger.warning(
                "duplicate episode preserved: %s; existing %s", source, existing
            )
            if progress is not None:
                progress.resume(source.name)
        else:
            self._recordConflict(
                source,
                existing,
                "episode identity already exists",
                progress,
            )

    def _recordExistingFile(
        self,
        source: Path,
        destination: Path,
        progress: Optional[_TvMergeProgress] = None,
    ) -> None:
        """Report a same-path duplicate or conflict without overwriting."""

        identical = (
            progress.compareFiles(source, destination)
            if progress is not None
            else _filesIdentical(source, destination)
        )
        if identical:
            if progress is not None:
                progress.pause()
            self.stats.duplicates += 1
            logger.warning(
                "duplicate file preserved: %s; existing %s", source, destination
            )
            if progress is not None:
                progress.resume(source.name)
        else:
            self._recordConflict(
                source,
                destination,
                "destination already exists",
                progress,
            )

    def _recordConflict(
        self,
        source: Path,
        destination: Path,
        reason: str,
        progress: Optional[_TvMergeProgress] = None,
    ) -> None:
        """Record a merge conflict while leaving both entries untouched."""

        if progress is not None:
            progress.pause()
        self.stats.conflicts += 1
        logger.warning("merge conflict (%s): %s -> %s", reason, source, destination)
        if progress is not None:
            progress.resume(source.name)


def mergeDuplicateTvShows(
    *,
    catalogue: Optional[MediaCatalogue] = None,
    filesystem: Optional[FilesystemOperations] = None,
    dryRun: bool = True,
) -> TvMergeStats:
    """Merge duplicates from live storage, keeping explicit test catalogues injectable."""

    # The filesystem is authoritative for maintenance. A normal MediaCatalogue is
    # persisted UI/query state and may legitimately be stale or empty, so replace
    # it with a fresh in-memory snapshot. Lightweight injected catalogues used by
    # tests and callers remain honoured.
    if catalogue is None or isinstance(catalogue, MediaCatalogue):
        from .tvLibraryScan import scanTvLibrary

        catalogue = scanTvLibrary()

    return TvLibraryMerger(
        catalogue=catalogue,
        filesystem=filesystem,
        dryRun=dryRun,
    ).merge()


def _directoryDescendantCount(root: Path) -> int:
    """Return the number of entries beneath *root* for merge progress."""

    try:
        return sum(1 for _ in root.rglob("*"))
    except OSError:
        return 0


def _treeEntryCount(root: Path) -> int:
    """Return one for *root* plus every descendant beneath it."""

    return 1 + _directoryDescendantCount(root)


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
