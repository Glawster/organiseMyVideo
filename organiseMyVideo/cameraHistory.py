"""Read-only camera import-history reconciliation for REQ-028."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile

from organiseMyProjects.logUtils import getLogger
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .cameraImport import cameraImportHistory
from .constants import applicationStateDirectory
from .terminalProgress import TerminalProgress


@dataclass(frozen=True)
class CameraHistoryAsset:
    """Reconciliation result for one archived asset."""

    manifestPath: Path
    cardId: Optional[int]
    recordedPath: Path
    currentPath: Optional[Path]
    status: str
    digest: Optional[str]
    matches: tuple[Path, ...] = ()


def cameraHistoryCheck(
    manifestDirectory: Path,
    *,
    cardId: Optional[int] = None,
    archiveRoots: Optional[Iterable[Path]] = None,
) -> tuple[CameraHistoryAsset, ...]:
    """Check recorded import assets without mutating manifests or archive files."""

    records = cameraImportHistory(Path(manifestDirectory), cardId=cardId)
    manifests: list[tuple[Path, Optional[int], dict]] = []
    for record in records:
        payload = _manifestRead(record.manifestPath)
        if payload is not None:
            manifests.append((record.manifestPath, record.cardId, payload))

    roots = (
        tuple(Path(root) for root in archiveRoots)
        if archiveRoots is not None
        else _archiveRootsInfer(manifests)
    )
    digestIndex: Optional[dict[tuple[int, str], list[Path]]] = None
    indexComplete = True
    results: list[CameraHistoryAsset] = []
    assets = list(_manifestAssets(manifests))
    progress = TerminalProgress(len(assets), "Checking camera history")
    completed = 0
    progress.render(completed)

    try:
        for manifestPath, manifestCardId, asset in assets:
            recordedPath = Path(str(asset["destinationPath"]))
            digest = _recordedDigest(asset)
            size = _recordedSize(asset)

            # Absence permits reconciliation; read/stat failures do not prove absence.
            status = _recordedPathCheck(recordedPath, digest)
            if status is not None:
                results.append(
                    CameraHistoryAsset(
                        manifestPath,
                        manifestCardId,
                        recordedPath,
                        recordedPath,
                        status,
                        digest,
                    )
                )
            elif digest is None:
                results.append(
                    CameraHistoryAsset(
                        manifestPath,
                        manifestCardId,
                        recordedPath,
                        None,
                        "missing",
                        None,
                    )
                )
            else:
                if digestIndex is None:
                    progress.finish()
                    digestIndex, indexComplete = _digestIndexBuild(roots)
                    progress.render(completed, recordedPath.name)
                matches = tuple(
                    sorted(
                        path
                        for (
                            candidateSize,
                            candidateDigest,
                        ), paths in digestIndex.items()
                        if candidateDigest == digest
                        and (size < 0 or candidateSize == size)
                        for path in paths
                    )
                )
                if not indexComplete:
                    status = "unreadable"
                    currentPath = None
                elif len(matches) == 1:
                    status = "moved"
                    currentPath = matches[0]
                elif len(matches) > 1:
                    status = "ambiguous"
                    currentPath = None
                else:
                    status = "missing"
                    currentPath = None
                results.append(
                    CameraHistoryAsset(
                        manifestPath,
                        manifestCardId,
                        recordedPath,
                        currentPath,
                        status,
                        digest,
                        matches,
                    )
                )
            completed += 1
            progress.render(completed, recordedPath.name)
    finally:
        progress.finish()
    return tuple(results)


def cameraHistorySummary(
    results: tuple[CameraHistoryAsset, ...], *, cardId: Optional[int] = None
) -> str:
    """Render a compact reconciliation report."""

    title = "CAMERA HISTORY CHECK"
    if cardId is not None:
        title += f" — CARD {cardId:03d}"
    lines = [
        title,
        "",
        "Status      Recorded destination                              Current destination",
        "------      --------------------                              -------------------",
    ]
    if not results:
        lines.append("No recorded archive assets.")
        return "\n".join(lines) + "\n"
    for result in results:
        if result.status == "ok":
            current = "same"
        elif result.status == "ambiguous":
            current = f"{len(result.matches)} matches"
        elif result.currentPath is None:
            current = "-"
        else:
            current = str(result.currentPath)
        lines.append(f"{result.status:<11} {str(result.recordedPath):<49} {current}")
    return "\n".join(lines) + "\n"


def _manifestAssets(manifests: list[tuple[Path, Optional[int], dict]]):
    """Yield archive assets that participate in history reconciliation."""
    for manifestPath, manifestCardId, payload in manifests:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict) or not asset.get("destinationPath"):
                continue
            if asset.get("outcome") not in {"copied", "alreadyPresent", None}:
                continue
            yield manifestPath, manifestCardId, asset


def _manifestRead(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _recordedDigest(asset: dict) -> Optional[str]:
    for key in ("destinationDigest", "sourceDigest", "sha256", "digest"):
        value = asset.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return None


def _recordedSize(asset: dict) -> int:
    try:
        return int(asset.get("sizeBytes", -1))
    except (TypeError, ValueError):
        return -1


def _archiveRootsInfer(
    manifests: list[tuple[Path, Optional[int], dict]],
) -> tuple[Path, ...]:
    roots: set[Path] = set()
    for _manifestPath, _cardId, payload in manifests:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict) or not asset.get("destinationPath"):
                continue
            path = Path(str(asset["destinationPath"]))
            root = _cameraArchiveRoot(path, str(asset.get("cameraKind") or ""))
            if root is not None:
                roots.add(root)
    return tuple(sorted(roots))


def _cameraArchiveRoot(path: Path, cameraKind: str) -> Optional[Path]:
    parts = path.parts
    names = {
        "gopro": "GoPro",
        "dji": "Drone",
        "drone": "Drone",
        "dashcam": "Dashcam",
    }
    marker = names.get(cameraKind.lower())
    if marker and marker in parts:
        index = parts.index(marker)
        return Path(*parts[: index + 1])
    if "By Date" in parts:
        index = parts.index("By Date")
        return Path(*parts[: index + 1])
    # Legacy manifests may not carry cameraKind. A date hierarchy normally
    # follows one of these well-known archive directories.
    for markerName in ("GoPro", "Drone", "Dashcam"):
        if markerName in parts:
            index = parts.index(markerName)
            return Path(*parts[: index + 1])
    return None


def _recordedPathCheck(path: Path, digest: Optional[str]) -> Optional[str]:
    """Distinguish missing paths from evidence that cannot be read safely."""
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            return None
        if digest is None or _fileSha256(path) == digest:
            return "ok"
        return "changed"
    except FileNotFoundError:
        return None
    except OSError as error:
        getLogger().value("History destination unreadable", f"{path}: {error}")
        return "unreadable"


def _digestIndexBuild(
    roots: tuple[Path, ...],
) -> tuple[dict[tuple[int, str], list[Path]], bool]:
    index: dict[tuple[int, str], list[Path]] = {}
    seen: set[Path] = set()
    estimatedTotal = _archiveFileCountRead(roots)
    label = "Indexing camera archive" + (" (estimated)" if estimatedTotal else "")
    progress = TerminalProgress(estimatedTotal, label)
    completed = 0
    complete = True

    def failed(error: OSError) -> None:
        nonlocal complete
        complete = False
        getLogger().value("History archive scan incomplete", str(error))

    progress.render(completed)
    try:
        for root in roots:
            # walk reports directory races/permissions through onerror and keeps
            # scanning other branches; an incomplete index cannot prove uniqueness.
            for directory, _directories, filenames in os.walk(root, onerror=failed):
                for filename in filenames:
                    path = Path(directory) / filename
                    if path in seen:
                        continue
                    seen.add(path)
                    try:
                        metadata = path.stat()
                        if not stat.S_ISREG(metadata.st_mode):
                            continue
                        digest = _fileSha256(path)
                    except OSError as error:
                        failed(error)
                        continue
                    index.setdefault((metadata.st_size, digest), []).append(path)
                    completed += 1
                    progress.render(completed, path.name)
    finally:
        progress.finish()
    if complete:
        _archiveFileCountWrite(roots, completed)
    return index, complete


def _archiveFileCountKey(roots: tuple[Path, ...]) -> str:
    """Return a stable key for one set of archive roots."""

    return "|".join(str(Path(root).expanduser().resolve()) for root in sorted(roots))


def _archiveFileCountRead(roots: tuple[Path, ...]) -> int:
    """Return the previous completed archive file count as a progress estimate."""

    path = applicationStateDirectory() / "cameraHistoryProgress.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        counts = payload.get("archiveFileCounts", {})
        value = int(counts.get(_archiveFileCountKey(roots), 0))
    except (OSError, ValueError, TypeError, RuntimeError, AttributeError):
        return 0
    return max(value, 0)


def _archiveFileCountWrite(roots: tuple[Path, ...], count: int) -> None:
    """Persist the completed archive file count for the next progress display."""

    temporary: Optional[Path] = None
    try:
        path = applicationStateDirectory() / "cameraHistoryProgress.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        counts = payload.get("archiveFileCounts")
        if not isinstance(counts, dict):
            counts = {}
        counts[_archiveFileCountKey(roots)] = max(int(count), 0)
        payload["archiveFileCounts"] = counts
        path.parent.mkdir(parents=True, exist_ok=True)
        # Unique sibling temporaries prevent concurrent checks sharing a staging file.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name,
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        getLogger().value("History progress cache unavailable", str(error))
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                getLogger().value(
                    "History progress temporary cleanup failed", str(error)
                )


def _fileSha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        before = os.fstat(handle.fileno())
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(handle.fileno())
        current = path.stat()

        def signature(value: os.stat_result) -> tuple[int, ...]:
            return (
                value.st_dev,
                value.st_ino,
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )

        if signature(before) != signature(after) or signature(after) != signature(
            current
        ):
            raise OSError(f"File changed while hashing: {path}")
    return digest.hexdigest()
