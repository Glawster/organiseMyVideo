"""Rename downloaded adult scenes and file them into the collection (REQ-046).

Parsing is pure so it can be tested without a filesystem. Planning reads the
source tree, and every mutation goes through :class:`FilesystemOperations`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS
from .filesystemOperations import FilesystemOperations

logger = getLogger()

DEFAULT_ADULT_SOURCE = "/mnt/video/toMove"
DEFAULT_ADULT_DESTINATION = "/mnt/myVideo/decrypted/Pron/toMove"

# Files a release group adds beside the video; safe to quarantine once the
# video has gone.
TRACKER_EXTENSIONS = {".nfo", ".txt", ".url", ".sfv"}

_RESOLUTION = re.compile(r"^(?:\d{3,4}p|4k|uhd)$", re.IGNORECASE)
_RELEASE_TAG = re.compile(
    r"^(?:xxx|mp4|mkv|web|webrip|hevc|x264|x265|h264|h265)\b", re.I
)
_SCENE = re.compile(
    r"^(?P<studio>[A-Za-z0-9]+)\.(?P<yy>\d{2})\.(?P<mm>\d{2})\.(?P<dd>\d{2})\.(?P<rest>.+)$"
)
_HYPHEN = re.compile(
    r"^\[?(?P<studio>[^\[\]]+?)\]?\s+-\s+(?P<performers>.+?)\s+-\s+(?P<title>.+?)"
    r"\s*\((?P<date>\d{2}\.\d{2}\.\d{2,4})\)"
)
_BRACKET = re.compile(
    r"^\[(?P<studio>[^\]]+)\]\s*(?P<rest>.+?)\s*\((?P<date>\d{2}\.\d{2}\.\d{2,4})\)"
)
_UNSAFE_SEPARATORS = re.compile(r"\s*[\\/:|]\s*")
_UNSAFE_REMOVED = re.compile(r'[?*<>"]')


@dataclass(frozen=True)
class AdultRelease:
    """The identity parsed from one downloaded scene name."""

    studio: str
    released: date
    performers: tuple[str, ...]
    title: str = ""
    explicitPerformers: bool = False


@dataclass
class AdultFilingItem:
    """One video found in the source and what will happen to it."""

    source: Path
    container: Optional[Path] = None
    release: Optional[AdultRelease] = None
    destination: Optional[Path] = None
    status: str = "move"
    reason: str = ""


@dataclass
class AdultFilingStats:
    """Counts reported at the end of a run."""

    moved: int = 0
    unparsed: int = 0
    conflicts: int = 0
    errors: int = 0
    foldersKept: int = 0
    items: list[AdultFilingItem] = field(default_factory=list)


## workflow


def adultFilingRun(
    sourceRoot: Path,
    destinationRoot: Path,
    *,
    dryRun: bool = True,
    knownPerformers: Iterable[str] = (),
    filesystem: Optional[FilesystemOperations] = None,
) -> AdultFilingStats:
    """Plan and, unless *dryRun*, perform the filing of every source video."""
    sourceRoot = Path(sourceRoot)
    destinationRoot = Path(destinationRoot)
    adultPathsValidate(sourceRoot, destinationRoot)
    filesystem = filesystem or FilesystemOperations(dryRun=dryRun)
    items = adultFilingPlan(sourceRoot, destinationRoot, knownPerformers)
    stats = AdultFilingStats(items=items)
    for item in items:
        if item.status == "unparsed":
            stats.unparsed += 1
            logger.warning("unparsed, left in place: %s", item.source)
        elif item.status == "conflict":
            stats.conflicts += 1
            logger.warning("conflict, left in place: %s (%s)", item.source, item.reason)
        else:
            _adultItemMove(item, filesystem, sourceRoot, stats)
    return stats


def adultFilingPlan(
    sourceRoot: Path,
    destinationRoot: Path,
    knownPerformers: Iterable[str] = (),
) -> list[AdultFilingItem]:
    """Return one planned item per source video, in a stable order."""
    candidates = list(_adultCandidates(Path(sourceRoot)))
    # Names that state their performers explicitly teach the split for the
    # scene-release names in the same run.
    known = {name.strip() for name in knownPerformers if name.strip()}
    for _item, name in candidates:
        release = adultReleaseParse(name)
        if release and release.explicitPerformers:
            known.update(release.performers)
    planned: dict[Path, AdultFilingItem] = {}
    items: list[AdultFilingItem] = []
    for item, name in candidates:
        item.release = adultReleaseParse(name, known)
        if item.release is None and name != item.source.stem:
            item.release = adultReleaseParse(item.source.stem, known)
        _adultItemDestination(item, Path(destinationRoot), planned)
        items.append(item)
    return items


def adultPathsValidate(sourceRoot: Path, destinationRoot: Path) -> None:
    """Refuse source/destination pairs that are equal or nested."""
    source = Path(sourceRoot).expanduser().resolve()
    destination = Path(destinationRoot).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"source directory does not exist: {source}")
    if source == destination:
        raise ValueError(f"source and destination are the same: {source}")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError(
            f"source and destination must not contain each other: {source}, {destination}"
        )


## naming


def adultFileName(release: AdultRelease, suffix: str) -> str:
    """Return ``Studio - yymmdd - Performers[ - Title]`` plus *suffix*."""
    parts = [release.studio, release.released.strftime("%y%m%d")]
    if release.performers:
        parts.append(", ".join(release.performers))
    if release.title:
        parts.append(release.title)
    return adultSafeName(" - ".join(parts)) + suffix.lower()


def adultSafeName(name: str) -> str:
    """Return *name* with path and reserved characters made filesystem-safe."""
    name = _UNSAFE_SEPARATORS.sub(" - ", name)
    name = _UNSAFE_REMOVED.sub("", name)
    return re.sub(r"\s+", " ", name).strip(" .")


## parsing


def adultReleaseParse(
    name: str, knownPerformers: Iterable[str] = ()
) -> Optional[AdultRelease]:
    """Parse a scene name in any supported form, or return ``None``."""
    known = tuple(knownPerformers)
    for parser in (_adultHyphenParse, _adultBracketParse, _adultSceneParse):
        release = parser(name.strip(), known)
        if release is not None:
            return release
    return None


def adultPerformersSplit(
    words: list[str], knownPerformers: Iterable[str] = ()
) -> tuple[tuple[str, ...], str]:
    """Split leading performer names from the title words that follow."""
    known = sorted(
        (tuple(name.lower().split()) for name in knownPerformers if name.split()),
        key=len,
        reverse=True,
    )

    def knownAt(index: int) -> int:
        lowered = tuple(word.lower() for word in words)
        for name in known:
            if lowered[index : index + len(name)] == name:
                return len(name)
        return 0

    def nameAt(index: int) -> int:
        # A known name wins; otherwise assume the usual first-and-last name.
        return knownAt(index) or min(2, len(words) - index)

    performers: list[str] = []
    index = nameAt(0)
    if index:
        performers.append(" ".join(words[:index]))
    while index < len(words):
        if words[index].lower() in {"and", "&"} and index + 1 < len(words):
            length = nameAt(index + 1)
            performers.append(" ".join(words[index + 1 : index + 1 + length]))
            index += 1 + length
        elif length := knownAt(index):
            performers.append(" ".join(words[index : index + length]))
            index += length
        else:
            break
    return tuple(performers), " ".join(words[index:])


def _adultBracketParse(name: str, known: tuple[str, ...]) -> Optional[AdultRelease]:
    """Parse ``[Studio] Performers Title (yy.mm.dd)[tags]``."""
    match = _BRACKET.match(name)
    released = match and _adultDate(match["date"])
    if not match or released is None:
        return None
    performers, title = adultPerformersSplit(_adultWords(match["rest"]), known)
    return AdultRelease(match["studio"].strip(), released, performers, title)


def _adultHyphenParse(name: str, known: tuple[str, ...]) -> Optional[AdultRelease]:
    """Parse ``Studio - A, B - Title (dd.mm.yyyy) rq``."""
    match = _HYPHEN.match(name)
    released = match and _adultDate(match["date"])
    if not match or released is None:
        return None
    performers = tuple(
        performer.strip()
        for performer in re.split(r"\s*(?:,|&|\band\b)\s*", match["performers"])
        if performer.strip()
    )
    return AdultRelease(
        match["studio"].strip(),
        released,
        performers,
        match["title"].strip(),
        explicitPerformers=True,
    )


def _adultSceneParse(name: str, known: tuple[str, ...]) -> Optional[AdultRelease]:
    """Parse ``Studio.yy.mm.dd.Performers.Title.XXX.1080p.MP4-GROUP[XC]``."""
    match = _SCENE.match(name)
    if not match:
        return None
    try:
        released = date(2000 + int(match["yy"]), int(match["mm"]), int(match["dd"]))
    except ValueError:
        return None
    words: list[str] = []
    for word in re.sub(r"\[[^\]]*\]", "", match["rest"]).split("."):
        # Everything from the first release tag onwards describes the encode.
        if not word or _RESOLUTION.match(word) or _RELEASE_TAG.match(word):
            break
        words.append(word)
    if words and all(word.islower() for word in words):
        words = [word.capitalize() for word in words]
    performers, title = adultPerformersSplit(words, known)
    studio = match["studio"]
    return AdultRelease(
        studio if not studio.islower() else studio.capitalize(),
        released,
        performers,
        title,
    )


## source discovery


def _adultCandidates(sourceRoot: Path) -> Iterable[tuple[AdultFilingItem, str]]:
    """Yield each source video with the name its identity is parsed from."""
    for entry in sorted(sourceRoot.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
            yield AdultFilingItem(source=entry), entry.stem
        elif entry.is_dir():
            videos = _adultFolderVideos(entry)
            if len(videos) == 1:
                yield AdultFilingItem(source=videos[0], container=entry), entry.name
            else:
                for video in videos:
                    yield AdultFilingItem(source=video), video.stem


def _adultFolderVideos(folder: Path) -> list[Path]:
    """Return feature videos below *folder*, ignoring samples and hidden paths."""
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
        and not any(part.startswith(".") for part in path.relative_to(folder).parts)
        and "sample" not in path.stem.lower()
        and "sample" not in path.parent.name.lower()
    )


## utilities


def _adultDate(text: str) -> Optional[date]:
    """Return a date from ``dd.mm.yyyy`` or ``yy.mm.dd``."""
    first, second, third = text.split(".")
    try:
        if len(third) == 4:
            return date(int(third), int(second), int(first))
        return date(2000 + int(first), int(second), int(third))
    except ValueError:
        return None


def _adultWords(text: str) -> list[str]:
    """Return the words of a space-separated name with bracketed tags removed."""
    return re.sub(r"\[[^\]]*\]", " ", text).split()


def _adultItemDestination(
    item: AdultFilingItem, destinationRoot: Path, planned: dict[Path, AdultFilingItem]
) -> None:
    """Set the item's destination and mark unparsed names and conflicts."""
    if item.release is None:
        item.status = "unparsed"
        return
    studio = adultSafeName(item.release.studio)
    destination = (
        destinationRoot / studio / adultFileName(item.release, item.source.suffix)
    )
    item.destination = destination
    if destination.exists():
        item.status, item.reason = "conflict", "destination already exists"
    elif destination in planned:
        item.status = "conflict"
        item.reason = f"same destination as {planned[destination].source}"
    else:
        planned[destination] = item


def _adultItemMove(
    item: AdultFilingItem,
    filesystem: FilesystemOperations,
    sourceRoot: Path,
    stats: AdultFilingStats,
) -> None:
    """Move one video and tidy its release folder; record any failure."""
    assert item.destination is not None
    logger.action(f"moving {item.source} → {item.destination}")
    try:
        filesystem.move(item.source, item.destination)
    except Exception as error:  # noqa: BLE001 - reported and counted
        item.status, item.reason = "error", str(error)
        stats.errors += 1
        logger.error("move failed for %s: %s", item.source, error)
        return
    if not filesystem.dryRun:
        logger.done(f"moved {item.destination.name}")
    stats.moved += 1
    if item.container is not None:
        _adultContainerTidy(item.container, item.source, filesystem, sourceRoot, stats)


def _adultContainerTidy(
    container: Path,
    video: Path,
    filesystem: FilesystemOperations,
    sourceRoot: Path,
    stats: AdultFilingStats,
) -> None:
    """Quarantine tracker files and remove the folder once nothing else is left."""
    remaining = [
        path for path in container.rglob("*") if path.is_file() and path != video
    ]
    others = [p for p in remaining if p.suffix.lower() not in TRACKER_EXTENSIONS]
    if others:
        stats.foldersKept += 1
        logger.warning("release folder kept, it holds other files: %s", container)
        return
    try:
        for tracker in remaining:
            logger.action(f"quarantining {tracker}")
            filesystem.quarantine(tracker, sourceRoot=sourceRoot)
        # Deepest folders first so each is empty when removed.
        folders = sorted(
            (p for p in container.rglob("*") if p.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        )
        for folder in [*folders, container]:
            logger.action(f"removing empty folder {folder}")
            filesystem.removeEmptyDirectory(folder, stateKind="media")
    except OSError as error:
        stats.errors += 1
        logger.error("could not tidy release folder %s: %s", container, error)
