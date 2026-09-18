"""Typed, non-mutating camera import planning for REQ-004."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

from organiseMediaStudio.identity.hash import mediaHashCalculate

from .cameraDetect import CameraDetectedFile, cameraDetect
from .cameraMetadata import (
    metadataCr3CaptureRead,
    metadataFilenameCaptureRead,
    metadataJpegCaptureRead,
    metadataMp4CaptureRead,
)

_SLR_BY_DATE = "By Date"

_INCREMENT_SUFFIX = re.compile(r"^(?P<base>.*) \((?P<number>\d+)\)$")
_TRANSCEND_MODEL_DIRECTORY = re.compile(r"^DPB?\d{2,4}[A-Z]*$", re.IGNORECASE)
_TRANSCEND_PROXY_DIRECTORIES = {"TEMP", "E_TEMP"}


@dataclass(frozen=True)
class CameraAsset:
    """One supported source asset with capture metadata and planned destination."""

    sourcePath: Path
    relativePath: str
    cameraKind: str
    fileKind: str
    captureAt: datetime
    dateSource: str
    destinationPath: Path


@dataclass(frozen=True)
class ImportOperation:
    """One planner decision for a considered camera asset."""

    asset: CameraAsset
    outcome: str
    reason: str
    sourceDigest: Optional[str] = None
    destinationDigest: Optional[str] = None


@dataclass(frozen=True)
class ImportPlan:
    """Pure planning result. Building this object performs no filesystem mutation."""

    sourcePath: Path
    operations: tuple[ImportOperation, ...]
    excludedPaths: tuple[str, ...]
    unknownPaths: tuple[str, ...]


class CameraImportPlanner:
    """Build dry-run camera import plans without changing source or archive."""

    def __init__(
        self,
        *,
        goproDestination: Path,
        droneDestination: Path,
        dashcamDestination: Path,
        photoDestination: Optional[Path] = None,
        videoDestination: Optional[Path] = None,
        includeGoproCompanions: bool = False,
    ):
        self.goproDestination = Path(goproDestination)
        self.droneDestination = Path(droneDestination)
        self.dashcamDestination = Path(dashcamDestination)
        self.photoDestination = Path(photoDestination) if photoDestination else None
        self.videoDestination = Path(videoDestination) if videoDestination else None
        self.includeGoproCompanions = includeGoproCompanions

    def importPlan(self, source: Path) -> ImportPlan:
        """Return the complete non-mutating plan for *source*."""

        detection = cameraDetect(source)
        excluded: list[str] = []
        operations: list[ImportOperation] = []
        plannedCopies: dict[Path, Path] = {}
        slrPairDates = _slrPairDates(detection.files)

        videosByStem = {
            (item.path.parent, item.path.stem.lower()): item
            for item in detection.files
            if item.fileKind == "video"
        }
        for item in detection.files:
            if _transcendProxyPath(item):
                excluded.append(item.relativePath)
                continue

            if item.cameraKind == "gopro" and item.fileKind in {"preview", "thumbnail"}:
                if not self.includeGoproCompanions:
                    excluded.append(item.relativePath)
                    continue

            captureItem = item
            if item.cameraKind == "dji" and item.fileKind == "sidecar":
                primary = videosByStem.get((item.path.parent, item.path.stem.lower()))
                if primary is None:
                    excluded.append(item.relativePath)
                    continue
                captureItem = primary

            captureAt, dateSource = slrPairDates.get(item.path, (None, ""))
            if captureAt is None:
                captureAt, dateSource = _captureRead(captureItem)
            if captureAt is None:
                excluded.append(item.relativePath)
                continue

            destination = self._destinationFor(item, captureAt)
            asset = CameraAsset(
                sourcePath=item.path,
                relativePath=item.relativePath,
                cameraKind=item.cameraKind,
                fileKind=item.fileKind,
                captureAt=captureAt,
                dateSource=dateSource,
                destinationPath=destination,
            )
            operation = _operationBuild(
                asset,
                plannedCopies,
                inventFilename=item.cameraKind != "slr",
            )
            operations.append(operation)
            if operation.outcome == "copy":
                plannedCopies[operation.asset.destinationPath] = (
                    operation.asset.sourcePath
                )

        return ImportPlan(
            sourcePath=detection.sourcePath,
            operations=tuple(operations),
            excludedPaths=tuple(sorted(excluded)),
            unknownPaths=detection.unknownPaths,
        )

    def _destinationFor(self, item: CameraDetectedFile, captureAt: datetime) -> Path:
        if item.cameraKind == "slr":
            return self._slrDestinationFor(item, captureAt)
        root = {
            "gopro": self.goproDestination,
            "dji": self.droneDestination,
            "dashcam": self.dashcamDestination,
        }[item.cameraKind]
        return (
            root
            / f"{captureAt.year:04d}"
            / f"{captureAt.month:02d}"
            / f"{captureAt.day:02d}"
            / item.path.name
        )

    def _slrDestinationFor(self, item: CameraDetectedFile, captureAt: datetime) -> Path:
        """Route one SLR asset into ``By Date/YYYY/MM/DD`` under the matching root."""

        if item.fileKind == "video":
            root = self.videoDestination
            if root is None:
                raise ValueError(
                    "SLR video import requires a configured video destination"
                )
        else:
            root = self.photoDestination
            if root is None:
                raise ValueError(
                    "SLR photo import requires a configured photo destination"
                )
        return (
            root
            / _SLR_BY_DATE
            / f"{captureAt.year:04d}"
            / f"{captureAt.month:02d}"
            / f"{captureAt.day:02d}"
            / item.path.name
        )


def _transcendProxyPath(item: CameraDetectedFile) -> bool:
    """Return True for low-resolution Transcend TEMP/E_TEMP proxy recordings."""

    if item.cameraKind != "dashcam":
        return False
    parts = Path(item.relativePath).parts
    hasModelRoot = any(_TRANSCEND_MODEL_DIRECTORY.fullmatch(part) for part in parts)
    hasProxyDirectory = any(
        part.upper() in _TRANSCEND_PROXY_DIRECTORIES for part in parts
    )
    return hasModelRoot and hasProxyDirectory


def _captureRead(item: CameraDetectedFile) -> tuple[Optional[datetime], str]:
    """Read embedded/filename capture metadata, then filesystem mtime fallback."""

    captured: Optional[datetime] = None
    suffix = item.path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".thm"}:
        captured = metadataJpegCaptureRead(item.path)
    elif suffix in {".mp4", ".mov"}:
        captured = metadataMp4CaptureRead(item.path)
    elif suffix == ".cr3":
        captured = metadataCr3CaptureRead(item.path)
    if captured is not None:
        return captured, "metadata"

    captured = metadataFilenameCaptureRead(item.path)
    if captured is not None:
        return captured, "filename"

    try:
        return datetime.fromtimestamp(item.path.stat().st_mtime), "filesystem"
    except OSError:
        return None, "unavailable"


def _operationBuild(
    asset: CameraAsset,
    plannedCopies: Optional[dict[Path, Path]] = None,
    *,
    inventFilename: bool = True,
) -> ImportOperation:
    """Resolve duplicate/collision state without mutating source or archive.

    Candidate names follow the established organiseMyPhotos convention:
    ``name.ext``, ``name (2).ext``, ``name (3).ext`` and so on. At every
    occupied candidate, content identity is checked first. Identical content is
    ``alreadyPresent``; only different content advances to the next name.
    ``plannedCopies`` makes the same rule apply to earlier files in this plan.
    SLR assets keep their original names: different content at the planned
    destination is a conflict rather than an invented ``(2)`` filename.
    """

    plannedCopies = plannedCopies or {}
    sourceDigest: Optional[str] = None
    candidate = asset.destinationPath
    counter = _incrementStart(candidate)

    for _ in range(10_000):
        plannedSource = plannedCopies.get(candidate)
        if plannedSource is not None:
            sourceDigest = sourceDigest or _sha256(asset.sourcePath)
            plannedDigest = _sha256(plannedSource)
            if sourceDigest == plannedDigest:
                resolvedAsset = replace(asset, destinationPath=candidate)
                return ImportOperation(
                    asset=resolvedAsset,
                    outcome="alreadyPresent",
                    reason="identical content already planned for destination",
                    sourceDigest=sourceDigest,
                    destinationDigest=plannedDigest,
                )
            if not inventFilename:
                return ImportOperation(
                    asset=asset,
                    outcome="conflict",
                    reason="same destination name with different content",
                    sourceDigest=sourceDigest,
                    destinationDigest=plannedDigest,
                )
            candidate = _incrementedPath(asset.destinationPath, counter)
            counter += 1
            continue

        if candidate.exists():
            destinationDigest = None
            if candidate.is_file():
                sourceDigest = sourceDigest or _sha256(asset.sourcePath)
                destinationDigest = _sha256(candidate)
                if sourceDigest == destinationDigest:
                    resolvedAsset = replace(asset, destinationPath=candidate)
                    return ImportOperation(
                        asset=resolvedAsset,
                        outcome="alreadyPresent",
                        reason="identical destination content",
                        sourceDigest=sourceDigest,
                        destinationDigest=destinationDigest,
                    )
            if not inventFilename:
                return ImportOperation(
                    asset=asset,
                    outcome="conflict",
                    reason="same destination name with different content",
                    sourceDigest=sourceDigest,
                    destinationDigest=destinationDigest,
                )
            candidate = _incrementedPath(asset.destinationPath, counter)
            counter += 1
            continue

        resolvedAsset = replace(asset, destinationPath=candidate)
        reason = (
            "destination missing"
            if candidate == asset.destinationPath
            else "destination name occupied by different content; incremented filename"
        )
        return ImportOperation(
            asset=resolvedAsset,
            outcome="copy",
            reason=reason,
            sourceDigest=sourceDigest,
        )

    return ImportOperation(
        asset=asset,
        outcome="conflict",
        reason="no collision-free destination filename available",
        sourceDigest=sourceDigest,
    )


def _slrPairDates(
    files: tuple[CameraDetectedFile, ...],
) -> dict[Path, tuple[datetime, str]]:
    """Share one capture date across same-stem SLR RAW/JPEG pairs."""

    groups: dict[tuple[Path, str], list[CameraDetectedFile]] = {}
    for item in files:
        if item.cameraKind != "slr" or item.fileKind != "photo":
            continue
        key = (item.path.parent, item.path.stem.lower())
        groups.setdefault(key, []).append(item)

    paired: dict[Path, tuple[datetime, str]] = {}
    for items in groups.values():
        if len(items) < 2:
            continue
        preferred = _slrPreferredCapture(items)
        if preferred is None:
            continue
        for item in items:
            paired[item.path] = preferred
    return paired


def _slrPhotoRank(item: CameraDetectedFile) -> int:
    """Prefer RAW capture metadata when pairing a same-stem JPEG."""

    suffix = item.path.suffix.lower()
    if suffix == ".cr3":
        return 0
    if suffix in {".jpg", ".jpeg"}:
        return 1
    return 2


def _slrPreferredCapture(
    items: list[CameraDetectedFile],
) -> Optional[tuple[datetime, str]]:
    """Return the strongest shared capture date for one RAW/JPEG pair."""

    ranked = [_captureRead(item) for item in sorted(items, key=_slrPhotoRank)]
    for sourceName in ("metadata", "filename", "filesystem"):
        for captured, dateSource in ranked:
            if captured is not None and dateSource == sourceName:
                return captured, dateSource
    return None


def _incrementStart(path: Path) -> int:
    """Return the first counter used by the organiseMyPhotos naming convention."""

    match = _INCREMENT_SUFFIX.fullmatch(path.stem)
    if match is None:
        return 2
    return max(2, int(match.group("number")) + 1)


def _incrementedPath(path: Path, counter: int) -> Path:
    """Return ``name (N).ext`` while avoiding repeated counter suffixes."""

    stem = path.stem.strip()
    match = _INCREMENT_SUFFIX.fullmatch(stem)
    base = match.group("base").rstrip() if match is not None else stem
    return path.with_name(f"{base} ({counter}){path.suffix}")


def _sha256(path: Path) -> str:
    """Return the existing SHA-256 identity through the shared hash service."""

    return mediaHashCalculate(path, algorithm="sha256")
