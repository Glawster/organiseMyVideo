"""Canonical TV show-folder names, including leading-article inversion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .filesystemOperations import FilesystemOperations
from .seasonFolders import SeasonFolderStats, _mergeDirectory

logger = getLogger()
LEADING_THE = re.compile(r"^the\s+(.+)$", re.IGNORECASE)
TRAILING_THE = re.compile(r",\s*the$", re.IGNORECASE)
MOVIE_FOLDER = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)$")


def restoreLeadingThe(name: str) -> str:
    """Return a display title, moving a trailing ``, The`` back to the front."""

    normalised = re.sub(r"\s+", " ", name).strip()
    match = re.match(r"^(.+),\s*The$", normalised, re.IGNORECASE)
    if not match:
        return normalised or name
    remainder = match.group(1).strip()
    return f"The {remainder}" if remainder else normalised


def canonicalMovieFolderName(name: str) -> str:
    """Return ``Title, The (Year)`` when *name* is a leading-The movie folder."""

    parsed = MOVIE_FOLDER.match(name.strip())
    if not parsed:
        return name
    title = canonicalTvShowFolderName(parsed.group("title").strip())
    return f"{title} ({parsed.group('year')})"


def canonicalTvShowFolderName(name: str) -> str:
    """Return the on-disk show folder name, moving a leading ``The`` to the end."""

    normalised = re.sub(r"\s+", " ", name).strip()
    if not normalised:
        return name
    if TRAILING_THE.search(normalised):
        return TRAILING_THE.sub(", The", normalised)
    match = LEADING_THE.match(normalised)
    if not match:
        return normalised
    remainder = match.group(1).strip()
    return f"{remainder}, The" if remainder else normalised


def normaliseTvShowFolderNames(
    videoDirs: Iterable[Path],
    *,
    filesystem: Optional[FilesystemOperations] = None,
    dryRun: bool = True,
) -> SeasonFolderStats:
    """Rename ``The Show`` folders to ``Show, The`` across TV library roots."""

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
        for source in showDirs:
            canonicalName = canonicalTvShowFolderName(source.name)
            if canonicalName == source.name:
                continue
            destination = source.with_name(canonicalName)
            logger.action(f"normalise TV show folder: {source} -> {destination}")
            try:
                if not destination.exists():
                    operations.move(source, destination)
                    stats.renamed += 1
                    continue
                if not destination.is_dir():
                    stats.conflicts += 1
                    logger.warning(
                        "TV show folder conflict: destination is not a directory: %s",
                        destination,
                    )
                    continue
                moved = _mergeDirectory(source, destination, operations, dryRun, stats)
                if moved:
                    stats.renamed += 1
                if not dryRun and source.is_dir() and not any(source.iterdir()):
                    operations.removeEmptyDirectory(source, stateKind="media")
                    stats.directoriesRemoved += 1
            except (OSError, ValueError) as error:
                stats.errors += 1
                logger.warning(
                    "could not normalise TV show folder %s: %s", source, error
                )
    return stats


def normaliseMovieFolderNames(
    movieDirs: Iterable[Path],
    *,
    filesystem: Optional[FilesystemOperations] = None,
    dryRun: bool = True,
) -> SeasonFolderStats:
    """Rename ``The Title (Year)`` movie folders to ``Title, The (Year)``."""

    operations = filesystem or FilesystemOperations(dryRun=dryRun)
    stats = SeasonFolderStats()
    for movieDir in movieDirs:
        root = Path(movieDir)
        if not root.is_dir():
            continue
        try:
            folders = sorted(
                (path for path in root.iterdir() if path.is_dir()),
                key=lambda path: path.name.lower(),
            )
        except OSError as error:
            stats.errors += 1
            logger.warning("could not inspect movie root %s: %s", root, error)
            continue
        for source in folders:
            canonicalName = canonicalMovieFolderName(source.name)
            if canonicalName == source.name:
                continue
            destination = source.with_name(canonicalName)
            logger.action(f"normalise movie folder: {source} -> {destination}")
            try:
                if not destination.exists():
                    operations.move(source, destination)
                    stats.renamed += 1
                    continue
                if not destination.is_dir():
                    stats.conflicts += 1
                    logger.warning(
                        "movie folder conflict: destination is not a directory: %s",
                        destination,
                    )
                    continue
                moved = _mergeDirectory(source, destination, operations, dryRun, stats)
                if moved:
                    stats.renamed += 1
                if not dryRun and source.is_dir() and not any(source.iterdir()):
                    operations.removeEmptyDirectory(source, stateKind="media")
                    stats.directoriesRemoved += 1
            except (OSError, ValueError) as error:
                stats.errors += 1
                logger.warning("could not normalise movie folder %s: %s", source, error)
    return stats
