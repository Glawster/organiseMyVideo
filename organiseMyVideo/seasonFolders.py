"""Canonical TV season-folder naming and safe in-library normalisation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .filesystemOperations import FilesystemOperations

logger = getLogger()
SEASON_FOLDER = re.compile(r"^season\s+0*(\d+)$", re.IGNORECASE)


@dataclass
class SeasonFolderStats:
    """Counts produced while normalising TV season folders."""

    renamed: int = 0
    filesMoved: int = 0
    directoriesRemoved: int = 0
    duplicates: int = 0
    conflicts: int = 0
    errors: int = 0

    @property
    def changed(self) -> bool:
        """Return True when filesystem content was or would be relocated."""

        return bool(self.renamed or self.filesMoved or self.directoriesRemoved)


def canonicalSeasonFolderName(name: str) -> Optional[str]:
    """Return canonical ``Season N`` for a recognised season-folder name."""

    match = SEASON_FOLDER.fullmatch(name.strip())
    if match is None:
        return None
    return f"Season {int(match.group(1))}"


def normaliseTvSeasonFolders(
    videoDirs: Iterable[Path],
    *,
    filesystem: Optional[FilesystemOperations] = None,
    dryRun: bool = True,
) -> SeasonFolderStats:
    """Remove leading zeroes from season folders across TV library roots."""

    operations = filesystem or FilesystemOperations(dryRun=dryRun)
    stats = SeasonFolderStats()
    for videoDir in videoDirs:
        root = Path(videoDir)
        if not root.is_dir():
            continue
        try:
            showDirs = sorted(
                (path for path in root.iterdir() if path.is_dir()),
                key=lambda path: path.name.lower(),
            )
        except OSError as error:
            stats.errors += 1
            logger.warning("could not inspect TV root %s: %s", root, error)
            continue
        for showDir in showDirs:
            _normaliseShowSeasonFolders(showDir, operations, dryRun, stats)
    return stats


def _normaliseShowSeasonFolders(
    showDir: Path,
    filesystem: FilesystemOperations,
    dryRun: bool,
    stats: SeasonFolderStats,
) -> None:
    """Normalise direct season-folder children of one TV show directory."""

    try:
        seasonDirs = sorted(
            (path for path in showDir.iterdir() if path.is_dir()),
            key=lambda path: path.name.lower(),
        )
    except OSError as error:
        stats.errors += 1
        logger.warning("could not inspect TV show %s: %s", showDir, error)
        return

    for source in seasonDirs:
        canonicalName = canonicalSeasonFolderName(source.name)
        if canonicalName is None or canonicalName == source.name:
            continue
        destination = source.with_name(canonicalName)
        logger.action(f"normalise season folder: {source} -> {destination}")
        try:
            if not destination.exists():
                filesystem.move(source, destination)
                _recordCatalogueMove(source, destination, dryRun=dryRun)
                stats.renamed += 1
                continue
            if not destination.is_dir():
                stats.conflicts += 1
                logger.warning(
                    "season-folder conflict: destination is not a directory: %s",
                    destination,
                )
                continue
            moved = _mergeDirectory(source, destination, filesystem, dryRun, stats)
            if moved:
                stats.renamed += 1
            if not dryRun and source.is_dir() and not any(source.iterdir()):
                filesystem.removeEmptyDirectory(source, stateKind="media")
                stats.directoriesRemoved += 1
        except (OSError, ValueError) as error:
            stats.errors += 1
            logger.warning("could not normalise season folder %s: %s", source, error)


def _mergeDirectory(
    sourceDir: Path,
    destinationDir: Path,
    filesystem: FilesystemOperations,
    dryRun: bool,
    stats: SeasonFolderStats,
) -> bool:
    """Merge one directory into another without overwriting any entry."""

    movedAny = False
    for source in sorted(sourceDir.iterdir(), key=lambda path: path.name.lower()):
        destination = destinationDir / source.name
        if source.is_dir():
            if not destination.exists():
                filesystem.move(source, destination)
                _recordCatalogueMove(source, destination, dryRun=dryRun)
                movedAny = True
                continue
            if not destination.is_dir():
                stats.conflicts += 1
                logger.warning("season merge conflict: %s -> %s", source, destination)
                continue
            childMoved = _mergeDirectory(source, destination, filesystem, dryRun, stats)
            movedAny = movedAny or childMoved
            if not dryRun and source.is_dir() and not any(source.iterdir()):
                filesystem.removeEmptyDirectory(source, stateKind="media")
                stats.directoriesRemoved += 1
            continue

        if not source.is_file():
            stats.conflicts += 1
            logger.warning("unsupported season-folder entry preserved: %s", source)
            continue
        if destination.exists():
            if destination.is_file() and _filesIdentical(source, destination):
                stats.duplicates += 1
                logger.warning(
                    "duplicate season file preserved: %s; existing %s",
                    source,
                    destination,
                )
            else:
                stats.conflicts += 1
                logger.warning("season merge conflict: %s -> %s", source, destination)
            continue
        filesystem.move(source, destination)
        _recordCatalogueMove(source, destination, dryRun=dryRun)
        stats.filesMoved += 1
        movedAny = True
    return movedAny


def _recordCatalogueMove(source: Path, destination: Path, *, dryRun: bool) -> None:
    """Tell the catalogue about one season-folder move after it succeeds."""

    from .mediaCatalogue import catalogueRecordMove

    catalogueRecordMove(source, destination, dryRun=dryRun)


def _filesIdentical(
    left: Path,
    right: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """Return True when two regular files have identical content.

    Cheap conclusive checks run before hashing: different sizes are distinct,
    while matching filesystem device and inode mean both paths name the same
    physical file. Different inodes of equal size still require content hashes.
    """

    try:
        if not left.is_file() or not right.is_file():
            return False
        leftStat = left.stat()
        rightStat = right.stat()
        if leftStat.st_size != rightStat.st_size:
            return False
        if leftStat.st_dev == rightStat.st_dev and leftStat.st_ino == rightStat.st_ino:
            return True

        processed = 0
        total = leftStat.st_size + rightStat.st_size

        def _onRead(amount: int) -> None:
            nonlocal processed
            processed += amount
            if progress is not None:
                progress(processed, total)

        return _digest(left, _onRead) == _digest(right, _onRead)
    except OSError:
        return False


def _digest(path: Path, onRead: Optional[Callable[[int], None]] = None) -> str:
    """Return a SHA-256 digest without loading the whole file into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            if onRead is not None:
                onRead(len(chunk))
    return digest.hexdigest()
