"""Confirmed camera-media import service for REQ-004 acceptance criteria 8-18."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .cameraPlan import CameraImportPlanner, ImportOperation, ImportPlan
from .cameraSnapshot import cameraSnapshotMatch
from .constants import CAMERA_INVENTORY_DATABASE
from .filesystemOperations import FilesystemOperations

CARD_LABEL_PATTERN = re.compile(r"^organiseMyVideo\.(\d{3,})$")
CameraImportProgress = Callable[[int, int, str], None]


@dataclass(frozen=True)
class CameraImportResult:
    """Result from one camera import request."""

    plan: ImportPlan
    confirmed: bool
    manifestPath: Optional[Path]
    copied: int
    alreadyPresent: int
    failed: int
    cardId: Optional[int] = None
    importId: Optional[str] = None
    snapshotId: Optional[str] = None


@dataclass(frozen=True)
class CameraImportHistoryRecord:
    """One confirmed camera import reconstructed from its JSON manifest."""

    manifestPath: Path
    importId: str
    createdAt: str
    cardId: Optional[int]
    snapshotId: Optional[str]
    sourcePath: str
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
        progressCallback: Optional[CameraImportProgress] = None,
        inventoryDatabase: Optional[Path] = None,
    ) -> None:
        self.planner = planner
        self.manifestDirectory = Path(manifestDirectory)
        self.dryRun = dryRun
        self.progressCallback = progressCallback
        self.inventoryDatabase = Path(inventoryDatabase or CAMERA_INVENTORY_DATABASE)

    def importMedia(
        self,
        source: Path,
        *,
        cardId: Optional[int] = None,
    ) -> CameraImportResult:
        """Plan or execute one camera-media import."""

        plan = self.planner.importPlan(source)
        _plannedDestinationCollisionsRaise(plan)
        conflicts = [item for item in plan.operations if item.outcome == "conflict"]
        if conflicts and not self.dryRun:
            destinations = ", ".join(
                str(item.asset.destinationPath) for item in conflicts
            )
            raise RuntimeError(
                f"camera import has destination conflicts: {destinations}"
            )

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
                cardId=cardId,
            )

        snapshotId = None
        if cardId is not None:
            snapshotId = cameraSnapshotMatch(
                cardId=cardId,
                operations=plan.operations,
                databasePath=self.inventoryDatabase,
                assignIdentity=True,
            )

        copyOperations = [
            operation for operation in plan.operations if operation.outcome == "copy"
        ]
        _destinationSpaceValidate(copyOperations)
        totalBytes = sum(
            operation.asset.sourcePath.stat().st_size for operation in copyOperations
        )
        completedBytes = 0
        if totalBytes and self.progressCallback is not None:
            self.progressCallback(0, totalBytes, "")

        filesystem = FilesystemOperations(dryRun=False)
        records: list[dict] = []
        copied = 0
        failed = 0
        for operation in plan.operations:
            if operation.outcome == "alreadyPresent":
                records.append(self._recordBuild(operation, outcome="alreadyPresent"))
                continue
            sourceSize = operation.asset.sourcePath.stat().st_size
            sourceName = operation.asset.sourcePath.name
            try:
                filesystem.copyFile(
                    operation.asset.sourcePath,
                    operation.asset.destinationPath,
                    preserveMetadata=True,
                    stateKind="camera-media",
                    progressCallback=(
                        None
                        if self.progressCallback is None
                        else lambda fileBytes, _fileTotal, base=completedBytes, name=sourceName: self.progressCallback(
                            base + fileBytes, totalBytes, name
                        )
                    ),
                )
            except Exception as error:
                failed += 1
                records.append(
                    self._recordBuild(
                        operation,
                        outcome="failed",
                        error=_errorDisplay(error),
                    )
                )
            else:
                copied += 1
                records.append(self._recordBuild(operation, outcome="copied"))
            finally:
                completedBytes += sourceSize
                if self.progressCallback is not None:
                    self.progressCallback(completedBytes, totalBytes, sourceName)

        manifestPath, importId = self._manifestWrite(
            plan,
            records,
            cardId=cardId,
            snapshotId=snapshotId,
        )
        return CameraImportResult(
            plan=plan,
            confirmed=True,
            manifestPath=manifestPath,
            copied=copied,
            alreadyPresent=alreadyPresent,
            failed=failed,
            cardId=cardId,
            importId=importId,
            snapshotId=snapshotId,
        )

    def _recordBuild(
        self,
        operation: ImportOperation,
        *,
        outcome: str,
        error: Optional[str] = None,
    ) -> dict:
        asset = operation.asset
        sourceDigest = _fileSha256(asset.sourcePath)
        destinationDigest = None
        if asset.destinationPath.is_file():
            destinationDigest = _fileSha256(asset.destinationPath)
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

    def _manifestWrite(
        self,
        plan: ImportPlan,
        records: list[dict],
        *,
        cardId: Optional[int],
        snapshotId: Optional[str],
    ) -> tuple[Path, str]:
        createdAt = datetime.now(timezone.utc)
        importId = str(uuid.uuid4())
        manifestPath = self.manifestDirectory / (
            f"camera-import-{createdAt.strftime('%Y%m%dT%H%M%S%fZ')}.json"
        )
        payload = {
            "schemaVersion": 3,
            "importId": importId,
            "snapshotId": snapshotId,
            "createdAt": createdAt.isoformat(),
            "source": {
                "cardId": cardId,
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
        return manifestPath, importId


def cameraCardIdResolve(source: Path) -> Optional[int]:
    """Resolve an ``organiseMyVideo.NNN`` card identity above *source*."""

    current = Path(source).expanduser().resolve()
    if current.is_file():
        current = current.parent
    while True:
        found: set[int] = set()
        try:
            children = list(current.iterdir())
        except OSError:
            children = []
        for path in children:
            if not path.is_file():
                continue
            match = CARD_LABEL_PATTERN.fullmatch(path.name)
            if match is None:
                continue
            cardId = _cardLabelIdRead(path, int(match.group(1)))
            if cardId is not None:
                found.add(cardId)
        if len(found) > 1:
            values = ", ".join(str(value) for value in sorted(found))
            raise ValueError(f"multiple camera card IDs found at {current}: {values}")
        if found:
            return next(iter(found))
        parent = current.parent
        if parent == current or os.path.ismount(str(current)):
            return None
        current = parent


def cameraImportRun(
    *,
    source: Path,
    goproDestination: Path,
    droneDestination: Path,
    dashcamDestination: Path,
    manifestDirectory: Path,
    dryRun: bool = True,
    includeGoproCompanions: bool = False,
    expectedCardId: Optional[int] = None,
    progressCallback: Optional[CameraImportProgress] = None,
    inventoryDatabase: Optional[Path] = None,
    photoDestination: Optional[Path] = None,
    videoDestination: Optional[Path] = None,
) -> CameraImportResult:
    """Run camera import through the public application-service boundary."""

    source = Path(source)
    cardId = cameraCardIdResolve(source)
    if expectedCardId is not None and cardId != expectedCardId:
        actual = "unknown" if cardId is None else str(cardId)
        raise RuntimeError(
            f"camera card identity mismatch: expected {expectedCardId}, found {actual}"
        )
    if not dryRun and cardId is None:
        raise RuntimeError(
            "confirmed camera import requires a numbered organiseMyVideo card label"
        )
    planner = CameraImportPlanner(
        goproDestination=Path(goproDestination),
        droneDestination=Path(droneDestination),
        dashcamDestination=Path(dashcamDestination),
        photoDestination=Path(photoDestination) if photoDestination else None,
        videoDestination=Path(videoDestination) if videoDestination else None,
        includeGoproCompanions=includeGoproCompanions,
    )
    importer = CameraImporter(
        planner=planner,
        manifestDirectory=Path(manifestDirectory),
        dryRun=dryRun,
        progressCallback=progressCallback,
        inventoryDatabase=inventoryDatabase,
    )
    return importer.importMedia(source, cardId=cardId)


def cameraImportHistory(
    manifestDirectory: Path,
    *,
    cardId: Optional[int] = None,
) -> tuple[CameraImportHistoryRecord, ...]:
    """Return confirmed import history, optionally filtered by durable card ID."""

    directory = Path(manifestDirectory)
    if not directory.is_dir():
        return ()
    records: list[CameraImportHistoryRecord] = []
    for path in directory.glob("camera-import-*.json"):
        record = _manifestHistoryRead(path)
        if record is None:
            continue
        if cardId is not None and record.cardId != cardId:
            continue
        records.append(record)
    records.sort(
        key=lambda item: (item.createdAt, item.manifestPath.name), reverse=True
    )
    return tuple(records)


def cameraImportSummary(result: CameraImportResult) -> str:
    """Return a compact operational summary for one camera import result."""

    plannedCopies = sum(
        1 for operation in result.plan.operations if operation.outcome == "copy"
    )
    conflicts = sum(
        1 for operation in result.plan.operations if operation.outcome == "conflict"
    )
    card = _cardDisplay(result.cardId)
    mode = "CONFIRMED" if result.confirmed else "DRY-RUN"
    lines = [
        "",
        "CAMERA IMPORT COMPLETE" if result.confirmed else "CAMERA IMPORT PLAN",
        "",
        f"Card {card}   {_pathDisplay(result.plan.sourcePath)}",
        f"Mode        {mode}",
        "",
        "Files",
        f"  Planned             {plannedCopies}",
        f"  Copied              {result.copied}",
    ]
    if result.alreadyPresent:
        lines.append(f"  Already present     {result.alreadyPresent}")
    if conflicts:
        lines.append(f"  Conflicts           {conflicts}")
    if result.failed:
        lines.append(f"  Failed              {result.failed}")
    excluded = len(result.plan.excludedPaths)
    unknown = len(result.plan.unknownPaths)
    if excluded:
        lines.append(f"  Excluded            {excluded}")
    if unknown:
        lines.append(f"  Unknown             {unknown}")
    lines.extend(_importContentLines(result.plan))

    lines.extend(["", "Result"])
    if not result.confirmed:
        conflictNote = (
            f"; {conflicts} conflict{'s' if conflicts != 1 else ''} must be resolved"
            if conflicts
            else ""
        )
        lines.append(
            f"  Dry-run — {plannedCopies} file{'s' if plannedCopies != 1 else ''} would be copied{conflictNote}"
        )
    elif result.failed:
        lines.append(
            f"  WARNING: import incomplete — {result.copied} copied, {result.failed} failed"
        )
    else:
        lines.append(
            f"  OK: import complete — {result.copied} file{'s' if result.copied != 1 else ''} copied successfully"
        )

    if result.failed and result.manifestPath is not None:
        failures = _manifestFailureGroups(result.manifestPath)
        if failures:
            lines.extend(["", "Failure reasons"])
            for error, count, examples in failures:
                lines.append(f"  {count} × {error}")
                for example in examples:
                    lines.append(f"      {example}")
            lines.append("  See the manifest for the complete failed-file list.")

    if result.manifestPath is not None:
        lines.extend(
            [
                "",
                "Manifest",
                f"  {_pathDisplay(result.manifestPath.parent)}/",
                f"  {result.manifestPath.name}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def cameraImportHistorySummary(
    records: tuple[CameraImportHistoryRecord, ...],
    *,
    cardId: Optional[int] = None,
) -> str:
    """Return a concise table-like summary of previous confirmed imports."""

    title = "CAMERA IMPORT HISTORY"
    if cardId is not None:
        title += f" — CARD {_cardDisplay(cardId)}"
    if not records:
        return f"{title}\nNo recorded imports.\n"
    lines = [
        title,
        "Card  Date                 Copied  Present  Failed  Source",
    ]
    for record in records:
        lines.append(
            f"{_cardDisplay(record.cardId):<5} "
            f"{_historyDateDisplay(record.createdAt):<19} "
            f"{record.copied:>6} "
            f"{record.alreadyPresent:>8} "
            f"{record.failed:>7}  "
            f"{record.sourcePath}"
        )
    lines.append("")
    lines.append(f"{len(records)} import{'s' if len(records) != 1 else ''}")
    return "\n".join(lines) + "\n"


def _naiveCapture(value: datetime) -> datetime:
    """Return a naive UTC datetime so mixed JPEG/MP4 timestamps can be ordered."""

    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _importContentLines(plan: ImportPlan) -> list[str]:
    """Return CR3/JPEG/MP4 counts and capture-date provenance for a plan."""

    from .cameraDetect import cameraMediaSuffixCounts

    relativePaths = tuple(operation.asset.relativePath for operation in plan.operations)
    counts = cameraMediaSuffixCounts(relativePaths)
    slrPresent = any(
        operation.asset.cameraKind == "slr" for operation in plan.operations
    )
    if not slrPresent and counts["cr3"] == 0:
        return []

    captures = [
        _naiveCapture(operation.asset.captureAt) for operation in plan.operations
    ]
    fallbacks = [
        operation.asset.dateSource
        for operation in plan.operations
        if operation.asset.dateSource != "metadata"
    ]
    lines = [
        f"  CR3                 {counts['cr3']}",
        f"  JPEG                {counts['jpeg']}",
        f"  MP4                 {counts['mp4']}",
    ]
    if captures:
        start = min(captures).date().isoformat()
        end = max(captures).date().isoformat()
        dateRange = start if start == end else f"{start} to {end}"
        lines.append(f"  Date range          {dateRange}")
    if fallbacks:
        unique = ", ".join(sorted(set(fallbacks)))
        lines.append(f"  Fallback dates      {len(fallbacks)} ({unique})")
    return lines


def _plannedDestinationCollisionsRaise(plan: ImportPlan) -> None:
    """Reject multiple planned copies targeting the same final archive path."""

    byDestination: dict[Path, list[ImportOperation]] = {}
    for operation in plan.operations:
        if operation.outcome != "copy":
            continue
        byDestination.setdefault(operation.asset.destinationPath, []).append(operation)

    collisions = [
        (destination, operations)
        for destination, operations in byDestination.items()
        if len(operations) > 1
    ]
    if not collisions:
        return

    lines = ["camera import has planned destination collisions:"]
    for destination, operations in collisions[:10]:
        lines.append(f"  {destination}")
        for operation in operations:
            lines.append(f"    <- {operation.asset.relativePath}")
    if len(collisions) > 10:
        lines.append(f"  ...and {len(collisions) - 10} more collision(s)")
    raise RuntimeError("\n".join(lines))


def _destinationSpaceValidate(copyOperations: list[ImportOperation]) -> None:
    """Reject confirmed imports that cannot fit on their destination filesystems."""

    requiredByDevice: dict[int, int] = {}
    samplePathByDevice: dict[int, Path] = {}
    for operation in copyOperations:
        destination = operation.asset.destinationPath
        existing = destination.parent
        while not existing.exists() and existing.parent != existing:
            existing = existing.parent
        stats = os.stat(existing)
        device = stats.st_dev
        requiredByDevice[device] = (
            requiredByDevice.get(device, 0) + operation.asset.sourcePath.stat().st_size
        )
        samplePathByDevice.setdefault(device, existing)

    failures: list[str] = []
    for device, required in requiredByDevice.items():
        path = samplePathByDevice[device]
        free = shutil.disk_usage(path).free
        if required > free:
            failures.append(
                f"need {_byteDisplay(required)}, free {_byteDisplay(free)} at {path}"
            )
    if failures:
        raise RuntimeError(
            "insufficient destination disk space; "
            + "; ".join(failures)
            + "; import not started"
        )


def _manifestFailureGroups(path: Path) -> list[tuple[str, int, tuple[str, ...]]]:
    """Group failed manifest assets by error text with representative filenames."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return []

    grouped: dict[str, list[str]] = {}
    for item in assets:
        if not isinstance(item, dict) or item.get("outcome") != "failed":
            continue
        error = str(item.get("error") or "unspecified error").strip()
        relative = str(item.get("relativePath") or item.get("sourcePath") or "unknown")
        grouped.setdefault(error, []).append(relative)

    ordered = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    return [(error, len(paths), tuple(paths[:3])) for error, paths in ordered]


def _errorDisplay(error: Exception) -> str:
    """Return an actionable exception description for manifests and summaries."""

    message = str(error).strip()
    name = type(error).__name__
    if isinstance(error, OSError) and error.errno is not None:
        detail = error.strerror or message or "operating system error"
        return f"{name} [{error.errno}]: {detail}"
    if message:
        return f"{name}: {message}"
    return name


def _byteDisplay(value: int) -> str:
    """Return a compact binary byte count."""

    amount = float(max(value, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{amount:.1f} TiB"


def _pathDisplay(path: Path) -> str:
    """Return a terminal-friendly path using ``~`` for the user's home."""

    resolved = Path(path).expanduser()
    try:
        relative = resolved.relative_to(Path.home())
    except ValueError:
        return str(resolved)
    return "~" if not relative.parts else f"~/{relative.as_posix()}"


def _cardLabelIdRead(path: Path, filenameId: int) -> Optional[int]:
    """Return the label card ID, rejecting filename/content disagreement."""

    try:
        raw = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return filenameId
    if not raw:
        return filenameId
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = raw
    if isinstance(loaded, dict):
        loaded = loaded.get("cardId")
    try:
        payloadId = int(loaded)
    except (TypeError, ValueError):
        return filenameId
    if payloadId != filenameId:
        raise ValueError(
            f"card label {path} name is {filenameId} but contents are {payloadId}"
        )
    return payloadId


def _manifestHistoryRead(path: Path) -> Optional[CameraImportHistoryRecord]:
    """Read one import manifest into a history record."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    source = payload.get("source")
    if not isinstance(source, dict):
        source = {}
    rawCardId = source.get("cardId", payload.get("cardId"))
    try:
        cardId = int(rawCardId) if rawCardId is not None else None
    except (TypeError, ValueError):
        cardId = None
    snapshotId = payload.get("snapshotId")
    if not isinstance(snapshotId, str) or not snapshotId.strip():
        snapshotId = None
    assets = payload.get("assets")
    if not isinstance(assets, list):
        assets = []
    outcomes = [item.get("outcome") for item in assets if isinstance(item, dict)]
    return CameraImportHistoryRecord(
        manifestPath=path,
        importId=str(payload.get("importId") or path.stem),
        createdAt=str(payload.get("createdAt") or ""),
        cardId=cardId,
        snapshotId=snapshotId,
        sourcePath=str(source.get("path") or source.get("resolvedPath") or "(unknown)"),
        copied=outcomes.count("copied"),
        alreadyPresent=outcomes.count("alreadyPresent"),
        failed=outcomes.count("failed"),
    )


def _cardDisplay(cardId: Optional[int]) -> str:
    """Return a stable human-readable card identifier."""

    return "unknown" if cardId is None else f"{cardId:03d}"


def _historyDateDisplay(value: str) -> str:
    """Return compact local-neutral display text from an ISO timestamp."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:19] or "unknown"
    return parsed.strftime("%Y-%m-%d %H:%M")


def _fileSha256(path: Path) -> str:
    """Return the SHA-256 digest of *path*."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
