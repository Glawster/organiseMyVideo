"""Canonical TV show-folder names, including leading-article inversion."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS
from .filesystemOperations import FilesystemOperations
from .incomingNames import mediaNameIsAncillary, mediaNameIsDisposableJunk
from .movieIdentity import (
    MOVIE_IDENTITY_AGREE,
    MOVIE_IDENTITY_PRESERVE_CASE,
    movieIdentityClassify,
)
from .seasonFolders import SeasonFolderStats, _filesIdentical, _mergeDirectory

logger = getLogger()
LEADING_THE = re.compile(r"^the\s+(.+)$", re.IGNORECASE)
TRAILING_THE = re.compile(r",\s*the$", re.IGNORECASE)
MOVIE_FOLDER = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)$")
_FILESYSTEM_SEPARATOR_PATTERN = re.compile(r"[\\/:]+")
_FILESYSTEM_REMOVED_CHARACTER = re.compile(r"[|?*<>\"]+")
_ARTWORK_SUFFIXES = {".jpg", ".jpeg", ".png"}
_METADATA_SUFFIXES = {".xml", ".nfo"}
_LARGE_COMPARISON_BYTES = 512 * 1024 * 1024


def restoreLeadingThe(name: str) -> str:
    """Return a display title, moving a trailing ``, The`` back to the front."""

    normalised = re.sub(r"\s+", " ", name).strip()
    match = re.match(r"^(.+),\s*The$", normalised, re.IGNORECASE)
    if not match:
        return normalised or name
    remainder = match.group(1).strip()
    return f"The {remainder}" if remainder else normalised


def movieFilesystemSafeTitle(title: str) -> str:
    """Return *title* safe to use as a movie folder or file name.

    Colons and path separators become `` - ``, so ``6:45`` stays ``6 - 45``.
    ``|`` also becomes a separator; ``?*<>"`` are removed. Identity is compared on the original title, so
    this mapping cannot make a different film or year look safe.
    """
    if title.isupper():
        title = title.title()
    safe = _FILESYSTEM_SEPARATOR_PATTERN.sub(" - ", title.replace("|", " - "))
    safe = _FILESYSTEM_REMOVED_CHARACTER.sub("", safe)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe


def canonicalMovieFolderName(name: str) -> str:
    """Return ``Title, The (Year)`` when *name* is a leading-The movie folder.

    Unsupported filename characters are removed before the article convention
    is applied, so the planned folder is safe before any rename.
    """
    parsed = MOVIE_FOLDER.match(name.strip())
    if not parsed:
        return name
    title = movieFilesystemSafeTitle(parsed.group("title").strip())
    if not title:
        return name
    title = canonicalTvShowFolderName(title)
    return f"{title} ({parsed.group('year')})"


def canonicalTvShowFolderName(name: str) -> str:
    """Return the on-disk show folder name, moving a leading ``The`` to the end."""

    normalised = _FILESYSTEM_SEPARATOR_PATTERN.sub(" - ", name)
    normalised = re.sub(r"\s+", " ", normalised).strip()
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
                    _recordCatalogueMove(source, destination, dryRun=dryRun)
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
                    _recordCatalogueMove(source, destination, dryRun=dryRun)
                    stats.renamed += 1
                    continue
                # A name that only became canonical by dropping ``|?*<>"`` must
                # not be merged. Article-only collisions keep the existing merge.
                parsed = MOVIE_FOLDER.match(source.name.strip())
                if parsed and _movieTitleDropsUnsupportedCharacters(
                    parsed.group("title").strip()
                ):
                    logger.warning(
                        "%s",
                        movieFolderCollisionReport(
                            source,
                            destination,
                            sameIdentity=_movieFoldersShareIdentity(
                                source.name, destination.name
                            ),
                        ),
                    )
                    stats.conflicts += 1
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


def movieFolderCollisionReport(
    source: Path, destination: Path, *, sameIdentity: bool
) -> str:
    """Return the operator report for a movie folder whose target already exists."""
    lines = ["movie folder collision"]
    evidence = ""
    if sameIdentity and source.is_dir() and destination.is_dir():
        relation, evidence = movieFolderContentDescribe(source, destination)
        lines.append("classification: same-identity merge candidate")
        lines.append(f"content: {relation}")
        if relation == "complementary":
            lines.append("action: reconcile complementary contents")
    else:
        lines.append("classification: unresolved")
    lines.append(f"source: {source}")
    lines.append(f"target: {destination}")
    if evidence:
        lines.append(evidence)
    return "\n".join(lines)


def movieFolderContentDescribe(source: Path, destination: Path) -> tuple[str, str]:
    """Return whether two movie folders are identical, complementary, or distinct."""
    sourceSizes = _movieFolderFileSizes(source)
    destinationSizes = _movieFolderFileSizes(destination)
    shared = set(sourceSizes) & set(destinationSizes)
    # Same size is not enough: a later merge must not treat different bytes as identical.
    differing = sorted(
        name
        for name in shared
        if not _movieFilesIdentical(source / name, destination / name)
    )
    if set(sourceSizes) == set(destinationSizes) and not differing:
        relation = "identical"
    elif differing:
        relation = "distinct"
    else:
        relation = "complementary"
    evidenceLines = [
        f"source contains: {_movieFolderContentKinds(source)}",
        f"target contains: {_movieFolderContentKinds(destination)}",
    ]
    if differing:
        evidenceLines.append(f"distinct files: {', '.join(differing[:3])}")
    for label, folder in (("source", source), ("target", destination)):
        nested = _movieFolderNestedFeatureDirs(folder)
        if nested:
            evidenceLines.append(
                f"{label} nested feature folder: {', '.join(nested[:3])}"
            )
        junk = _movieFolderDisposableJunk(folder)
        if junk:
            evidenceLines.append(
                f"{label} disposable junk: {', '.join(junk[:3])}"
            )
    return relation, "\n".join(evidenceLines)


def _movieFilesIdentical(left: Path, right: Path) -> bool:
    """Compare movie files, showing live progress when a large read is required."""
    try:
        large = max(left.stat().st_size, right.stat().st_size) >= _LARGE_COMPARISON_BYTES
    except OSError:
        large = False
    stream = sys.stderr
    isatty = getattr(stream, "isatty", None)
    showProgress = bool(large and callable(isatty) and isatty())
    lastPercent = -1

    def _progress(processed: int, total: int) -> None:
        nonlocal lastPercent
        if not showProgress or total <= 0:
            return
        percent = min(int(processed * 100 / total), 100)
        if percent == lastPercent and processed < total:
            return
        lastPercent = percent
        processedGb = processed / (1024**3)
        totalGb = total / (1024**3)
        stream.write(
            f"\rComparing duplicate content: {left.name} "
            f"{percent:3d}% ({processedGb:.1f}/{totalGb:.1f} GB)"
        )
        stream.flush()

    try:
        return _filesIdentical(left, right, progress=_progress if showProgress else None)
    finally:
        if showProgress and lastPercent >= 0:
            stream.write("\n")
            stream.flush()


def _movieFolderContentKinds(folder: Path) -> str:
    """Return a short description of feature, metadata, artwork and junk."""
    directFeature = nestedFeature = metadata = artwork = False
    junkCount = 0
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        if mediaNameIsDisposableJunk(path.name):
            junkCount += 1
            continue
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS and not mediaNameIsAncillary(path.name):
            relative = path.relative_to(folder)
            if len(relative.parts) > 1:
                nestedFeature = True
            else:
                directFeature = True
        elif suffix in _METADATA_SUFFIXES:
            metadata = True
        elif suffix in _ARTWORK_SUFFIXES:
            artwork = True
    kinds = []
    if directFeature:
        kinds.append("feature file")
    if nestedFeature:
        kinds.append("nested feature file")
    if metadata:
        kinds.append("metadata")
    if artwork:
        kinds.append("artwork")
    if junkCount:
        kinds.append(f"{junkCount} disposable junk file(s)")
    return ", ".join(kinds) if kinds else "no recognised media"


def _movieFolderNestedFeatureDirs(folder: Path) -> list[str]:
    """Return first-level nested folders containing meaningful feature media."""
    nested = set()
    for path in folder.rglob("*"):
        if (
            not path.is_file()
            or path.suffix.lower() not in VIDEO_EXTENSIONS
            or mediaNameIsAncillary(path.name)
        ):
            continue
        relative = path.relative_to(folder)
        if len(relative.parts) > 1:
            nested.add(relative.parts[0])
    return sorted(nested, key=str.casefold)


def _movieFolderDisposableJunk(folder: Path) -> list[str]:
    """Return release-note files safe to present as later cleanup candidates."""
    return sorted(
        (
            path.relative_to(folder).as_posix()
            for path in folder.rglob("*")
            if path.is_file() and mediaNameIsDisposableJunk(path.name)
        ),
        key=str.casefold,
    )


def _movieFolderFileSizes(folder: Path) -> dict[str, int]:
    """Return substantive relative file paths and sizes for one movie folder."""
    sizes = {}
    for path in folder.rglob("*"):
        if path.is_file() and not mediaNameIsDisposableJunk(path.name):
            sizes[path.relative_to(folder).as_posix()] = path.stat().st_size
    return sizes


def _movieFoldersShareIdentity(sourceName: str, destinationName: str) -> bool:
    """Return True when two movie folder names are the same film and year."""
    source = MOVIE_FOLDER.match(sourceName.strip())
    destination = MOVIE_FOLDER.match(destinationName.strip())
    if not source or not destination:
        return False
    decision = movieIdentityClassify(
        source.group("title"),
        source.group("year"),
        destination.group("title"),
        destination.group("year"),
    )
    return decision.kind in {MOVIE_IDENTITY_AGREE, MOVIE_IDENTITY_PRESERVE_CASE}


def _movieTitleDropsUnsupportedCharacters(title: str) -> bool:
    """Return True when safe naming removes characters other than ``\\/:``."""
    legacy = _FILESYSTEM_SEPARATOR_PATTERN.sub(" - ", title)
    legacy = re.sub(r"\s+", " ", legacy).strip()
    return movieFilesystemSafeTitle(title) != legacy


def _recordCatalogueMove(source: Path, destination: Path, *, dryRun: bool) -> None:
    """Tell the catalogue about one folder move after the filesystem operation."""

    from .mediaCatalogue import catalogueRecordMove

    catalogueRecordMove(source, destination, dryRun=dryRun)
