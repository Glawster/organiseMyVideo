"""Detailed read-only views of camera import manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .cameraImport import CameraImportHistoryRecord



def cameraImportHistoryFullSummary(
    records: tuple[CameraImportHistoryRecord, ...],
    *,
    cardId: Optional[int] = None,
) -> str:
    """Return a compact per-file camera import history from recorded manifests."""

    title = "CAMERA IMPORT HISTORY"
    if cardId is not None:
        title += f" — CARD {cardId:03d}"
    if not records:
        return f"{title}\nNo recorded imports.\n"

    lines = [title]
    archivedCount = 0
    failedCount = 0
    for record in records:
        assets = _manifestAssetsRead(record.manifestPath)
        sourceRoot = Path(record.sourcePath)
        archiveRoot = _archiveRoot(assets)

        lines.extend(
            [
                "",
                f"IMPORT {_historyDateDisplay(record.createdAt)}",
                f"  Source root:   {sourceRoot}",
                f"  Archive root:  {archiveRoot or '-'}",
                f"  Manifest:      {_pathDisplay(record.manifestPath)}",
                f"  Result:        {_resultDisplay(record)}",
                "",
            ]
        )

        if not assets:
            lines.append("  No files recorded.")
            continue

        rows: list[tuple[str, str, str]] = []
        for asset in assets:
            outcome = str(asset.get("outcome") or "unknown")
            destination = str(asset.get("destinationPath") or "unknown")
            error = str(asset.get("error") or "")

            if outcome in {"copied", "alreadyPresent"}:
                archivedCount += 1
            elif outcome == "failed":
                failedCount += 1

            rows.append((_outcomeDisplay(outcome), destination, error))

        resultWidth = max(len("Result"), *(len(row[0]) for row in rows))
        lines.append(
            f"  {'Result'.ljust(resultWidth)}  Output"
        )
        lines.append(
            f"  {'-' * resultWidth}  {'-' * len('Output')}"
        )
        for result, output, error in rows:
            line = f"  {result.ljust(resultWidth)}  {output}"
            if error:
                line += f"  | {error}"
            lines.append(line.rstrip())

    lines.extend(
        [
            "",
            f"{len(records)} import{'s' if len(records) != 1 else ''}",
            f"{archivedCount} archived file{'s' if archivedCount != 1 else ''}",
        ]
    )
    if failedCount:
        lines.append(f"{failedCount} failed file{'s' if failedCount != 1 else ''}")
    return "\n".join(lines) + "\n"


def _manifestAssetsRead(path: Path) -> tuple[dict, ...]:
    """Return asset dictionaries from one import manifest."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, dict):
        return ()
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return ()
    return tuple(item for item in assets if isinstance(item, dict))


def _archiveRoot(assets: tuple[dict, ...]) -> Optional[Path]:
    """Return the deepest common destination directory for one import."""

    destinations = [
        Path(str(asset["destinationPath"]))
        for asset in assets
        if asset.get("destinationPath")
    ]
    if not destinations:
        return None
    parents = [str(path.parent) for path in destinations]
    try:
        return Path(os.path.commonpath(parents))
    except ValueError:
        return None


def _relativeDisplay(pathValue: str, root: Optional[Path]) -> str:
    """Return a path relative to the displayed root when possible."""

    path = Path(pathValue)
    if root is None:
        return str(path)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)



def _resultDisplay(record: CameraImportHistoryRecord) -> str:
    """Return a concise per-import result summary."""

    parts = [f"{record.copied} copied"]
    if record.alreadyPresent:
        parts.append(f"{record.alreadyPresent} already present")
    if record.failed:
        parts.append(f"{record.failed} failed")
    return ", ".join(parts)


def _outcomeDisplay(outcome: str) -> str:
    if outcome == "alreadyPresent":
        return "already present"
    return outcome.replace("_", " ")


def _historyDateDisplay(value: str) -> str:
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:19] or "unknown"
    return parsed.strftime("%Y/%m/%d %H:%M")


def _pathDisplay(path: Path) -> str:
    expanded = Path(path).expanduser()
    try:
        relative = expanded.relative_to(Path.home())
    except ValueError:
        return str(expanded)
    return "~" if not relative.parts else f"~/{relative.as_posix()}"
