"""Confirmed camera-media import service for REQ-004 acceptance criteria 8-12."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .cameraPlan import CameraImportPlanner, ImportOperation, ImportPlan
from .filesystemOperations import FilesystemOperations


@dataclass(frozen=True)
class CameraImportResult:
    """Result from one camera import request."""

    plan: ImportPlan
    confirmed: bool
    manifestPath: Optional[Path]
    copied: int
    alreadyPresent: int
    failed: int


class CameraImporter:
    """Plan camera imports and, when confirmed, copy and verify source assets."""

    def __init__(
        self,
        *,
        planner: CameraImportPlanner,
        manifestDirectory: Path,
        dryRun: bool = True,
    ) -> None:
        self.planner = planner
        self.manifestDirectory = Path(manifestDirectory)
        self.dryRun = dryRun

    def importMedia(self, source: Path) -> CameraImportResult:
        """Plan or execute one camera-media import."""

        plan = self.planner.importPlan(source)
        conflicts = [item for item in plan.operations if item.outcome == "conflict"]
        if conflicts:
            destinations = ", ".join(str(item.asset.destinationPath) for item in conflicts)
            raise RuntimeError(f"camera import has destination conflicts: {destinations}")

        alreadyPresent = sum(
            1 for item in plan.operations if item.outcome == "alreadyPresent"
        )
        if self.dryRun:
            return CameraImportResult(
                plan=plan,
                confirmed=False,
                manifestPath=None,
                copied=0,
                alreadyPresent=alreadyPresent,
                failed=0,
            )

        filesystem = FilesystemOperations(dryRun=False)
        records: list[dict] = []
        copied = 0
        failed = 0
        for operation in plan.operations:
            if operation.outcome == "alreadyPresent":
                records.append(self._recordBuild(operation, outcome="alreadyPresent"))
                continue
            try:
                filesystem.copyFile(
                    operation.asset.sourcePath,
                    operation.asset.destinationPath,
                    preserveMetadata=True,
                    stateKind="camera-media",
                )
            except Exception as error:
                failed += 1
                records.append(
                    self._recordBuild(
                        operation,
                        outcome="failed",
                        error=str(error),
                    )
                )
                continue
            copied += 1
            records.append(self._recordBuild(operation, outcome="copied"))

        manifestPath = self._manifestWrite(plan, records)
        return CameraImportResult(
            plan=plan,
            confirmed=True,
            manifestPath=manifestPath,
            copied=copied,
            alreadyPresent=alreadyPresent,
            failed=failed,
        )

    def _recordBuild(
        self,
        operation: ImportOperation,
        *,
        outcome: str,
        error: Optional[str] = None,
    ) -> dict:
        asset = operation.asset
        sourceDigest = _sha256(asset.sourcePath)
        destinationDigest = None
        if asset.destinationPath.is_file():
            destinationDigest = _sha256(asset.destinationPath)
        record = {
            "sourcePath": str(asset.sourcePath),
            "relativePath": asset.relativePath,
            "destinationPath": str(asset.destinationPath),
            "cameraKind": asset.cameraKind,
            "fileKind": asset.fileKind,
            "captureAt": asset.captureAt.isoformat(),
            "dateSource": asset.dateSource,
            "sizeBytes": asset.sourcePath.stat().st_size,
            "sourceDigest": sourceDigest,
            "destinationDigest": destinationDigest,
            "companion": asset.fileKind in {"sidecar", "preview", "thumbnail"},
            "outcome": outcome,
        }
        if error is not None:
            record["error"] = error
        return record

    def _manifestWrite(self, plan: ImportPlan, records: list[dict]) -> Path:
        createdAt = datetime.now(timezone.utc)
        manifestPath = self.manifestDirectory / (
            f"camera-import-{createdAt.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        )
        payload = {
            "schemaVersion": 1,
            "createdAt": createdAt.isoformat(),
            "source": {
                "path": str(plan.sourcePath),
                "resolvedPath": str(plan.sourcePath.resolve()),
            },
            "assets": records,
            "excludedPaths": list(plan.excludedPaths),
            "unknownPaths": list(plan.unknownPaths),
        }
        FilesystemOperations(dryRun=False).writeText(
            manifestPath,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            stateKind="camera-import-manifest",
        )
        return manifestPath


def cameraImportRun(
    *,
    source: Path,
    goproDestination: Path,
    droneDestination: Path,
    dashcamDestination: Path,
    manifestDirectory: Path,
    dryRun: bool = True,
    includeGoproCompanions: bool = False,
) -> CameraImportResult:
    """Run camera import through the public application-service boundary."""

    planner = CameraImportPlanner(
        goproDestination=Path(goproDestination),
        droneDestination=Path(droneDestination),
        dashcamDestination=Path(dashcamDestination),
        includeGoproCompanions=includeGoproCompanions,
    )
    importer = CameraImporter(
        planner=planner,
        manifestDirectory=Path(manifestDirectory),
        dryRun=dryRun,
    )
    return importer.importMedia(Path(source))


def cameraImportSummary(result: CameraImportResult) -> str:
    """Return a concise CLI-neutral summary for one camera import result."""

    plannedCopies = sum(
        1 for operation in result.plan.operations if operation.outcome == "copy"
    )
    manifest = str(result.manifestPath) if result.manifestPath is not None else "(none)"
    return f"""CAMERA IMPORT SUMMARY
Source:            {result.plan.sourcePath}
Mode:              {'confirmed' if result.confirmed else 'dry-run'}
Planned copies:    {plannedCopies}
Copied:            {result.copied}
Already present:   {result.alreadyPresent}
Failed:            {result.failed}
Excluded:          {len(result.plan.excludedPaths)}
Unknown:           {len(result.plan.unknownPaths)}
Manifest:          {manifest}
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
