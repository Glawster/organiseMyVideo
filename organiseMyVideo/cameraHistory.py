"""Read-only camera import-history reconciliation for REQ-028."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .cameraImport import cameraImportHistory


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

    roots = tuple(Path(root) for root in archiveRoots) if archiveRoots is not None else _archiveRootsInfer(manifests)
    digestIndex: Optional[dict[tuple[int, str], list[Path]]] = None
    results: list[CameraHistoryAsset] = []

    for manifestPath, manifestCardId, payload in manifests:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict) or not asset.get("destinationPath"):
                continue
            if asset.get("outcome") not in {"copied", "alreadyPresent", None}:
                continue
            recordedPath = Path(str(asset["destinationPath"]))
            digest = _recordedDigest(asset)
            size = _recordedSize(asset)

            if recordedPath.is_file():
                if digest is None or _fileSha256(recordedPath) == digest:
                    status = "ok"
                else:
                    status = "changed"
                results.append(
                    CameraHistoryAsset(
                        manifestPath, manifestCardId, recordedPath, recordedPath,
                        status, digest,
                    )
                )
                continue

            if digest is None:
                results.append(
                    CameraHistoryAsset(
                        manifestPath, manifestCardId, recordedPath, None,
                        "missing", None,
                    )
                )
                continue

            if digestIndex is None:
                digestIndex = _digestIndexBuild(roots)
            matches = tuple(sorted(digestIndex.get((size, digest), ())))
            if len(matches) == 1:
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
                    manifestPath, manifestCardId, recordedPath, currentPath,
                    status, digest, matches,
                )
            )
    return tuple(results)


def cameraHistorySummary(results: tuple[CameraHistoryAsset, ...], *, cardId: Optional[int] = None) -> str:
    """Render a compact reconciliation report."""

    title = "CAMERA HISTORY CHECK"
    if cardId is not None:
        title += f" — CARD {cardId:03d}"
    lines = [title, "", "Status      Recorded destination                              Current destination", "------      --------------------                              -------------------"]
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


def _archiveRootsInfer(manifests: list[tuple[Path, Optional[int], dict]]) -> tuple[Path, ...]:
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


def _digestIndexBuild(roots: tuple[Path, ...]) -> dict[tuple[int, str], list[Path]]:
    index: dict[tuple[int, str], list[Path]] = {}
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            try:
                size = path.stat().st_size
                digest = _fileSha256(path)
            except OSError:
                continue
            index.setdefault((size, digest), []).append(path)
    return index


def _fileSha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
