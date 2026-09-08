"""Typed, non-mutating camera import planning for REQ-004."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .cameraDetect import CameraDetectedFile, cameraDetect
from .cameraMetadata import (
    metadataFilenameCaptureRead,
    metadataJpegCaptureRead,
    metadataMp4CaptureRead,
)


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
        includeGoproCompanions: bool = False,
    ):
        self.goproDestination = Path(goproDestination)
        self.droneDestination = Path(droneDestination)
        self.dashcamDestination = Path(dashcamDestination)
        self.includeGoproCompanions = includeGoproCompanions

    def importPlan(self, source: Path) -> ImportPlan:
        """Return the complete non-mutating plan for *source*."""

        detection = cameraDetect(source)
        excluded: list[str] = []
        operations: list[ImportOperation] = []

        detectedByStem = {
            (item.path.parent, item.path.stem.lower()): item for item in detection.files
        }
        for item in detection.files:
            if item.cameraKind == "gopro" and item.fileKind in {"preview", "thumbnail"}:
                if not self.includeGoproCompanions:
                    excluded.append(item.relativePath)
                    continue

            if item.cameraKind == "dji" and item.fileKind == "sidecar":
                primary = detectedByStem.get((item.path.parent, item.path.stem.lower()))
                if primary is None or primary.fileKind != "video":
                    excluded.append(item.relativePath)
                    continue

            captureAt, dateSource = _captureRead(item)
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
            operations.append(_operationBuild(asset))

        return ImportPlan(
            sourcePath=detection.sourcePath,
            operations=tuple(operations),
            excludedPaths=tuple(sorted(excluded)),
            unknownPaths=detection.unknownPaths,
        )

    def _destinationFor(self, item: CameraDetectedFile, captureAt: datetime) -> Path:
        root = {
            "gopro": self.goproDestination,
            "dji": self.droneDestination,
            "dashcam": self.dashcamDestination,
        }[item.cameraKind]
        return root / captureAt.strftime("%Y/%m/%d") / item.path.name


def _captureRead(item: CameraDetectedFile) -> tuple[Optional[datetime], str]:
    """Read embedded/filename capture metadata, then filesystem mtime fallback."""

    captured: Optional[datetime] = None
    suffix = item.path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".thm"}:
        captured = metadataJpegCaptureRead(item.path)
    elif suffix in {".mp4", ".mov"}:
        captured = metadataMp4CaptureRead(item.path)
    if captured is not None:
        return captured, "metadata"

    captured = metadataFilenameCaptureRead(item.path)
    if captured is not None:
        return captured, "filename"

    try:
        return datetime.fromtimestamp(item.path.stat().st_mtime), "filesystem"
    except OSError:
        return None, "unavailable"


def _operationBuild(asset: CameraAsset) -> ImportOperation:
    """Classify destination state without writing either source or destination."""

    destination = asset.destinationPath
    if not destination.exists():
        return ImportOperation(asset=asset, outcome="copy", reason="destination missing")
    if not destination.is_file():
        return ImportOperation(asset=asset, outcome="conflict", reason="destination is not a file")

    sourceDigest = _sha256(asset.sourcePath)
    destinationDigest = _sha256(destination)
    if sourceDigest == destinationDigest:
        return ImportOperation(
            asset=asset,
            outcome="alreadyPresent",
            reason="identical destination content",
            sourceDigest=sourceDigest,
            destinationDigest=destinationDigest,
        )
    return ImportOperation(
        asset=asset,
        outcome="conflict",
        reason="same destination name has different content",
        sourceDigest=sourceDigest,
        destinationDigest=destinationDigest,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
