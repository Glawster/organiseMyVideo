"""Detailed read-only views of camera import manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .cameraImport import CameraImportHistoryRecord


def cameraImportHistoryFullSummary(
    records: tuple[CameraImportHistoryRecord, ...],
    *,
    cardId: Optional[int] = None,
) -> str:
    """Return per-file camera import history from the recorded manifests."""

    title = "CAMERA IMPORT HISTORY"
    if cardId is not None:
        title += f" — CARD {cardId:03d}"
    if not records:
        return f"{title}\nNo recorded imports.\n"

    lines = [title]
    archivedCount = 0
    failedCount = 0
    for record in records:
        lines.extend(
            [
                "",
                f"Import {_historyDateDisplay(record.createdAt)}",
                f"  Source:   {record.sourcePath}",
                f"  Manifest: {_pathDisplay(record.manifestPath)}",
                "  Files:",
            ]
        )
        assets = _manifestAssetsRead(record.manifestPath)
        if not assets:
            lines.append("    none recorded")
            continue

        for asset in assets:
            outcome = str(asset.get("outcome") or "unknown")
            source = str(asset.get("sourcePath") or asset.get("relativePath") or "unknown")
            destination = str(asset.get("destinationPath") or "unknown")
            if outcome in {"copied", "alreadyPresent"}:
                archivedCount += 1
            elif outcome == "failed":
                failedCount += 1

            line = f"    {_outcomeDisplay(outcome):<15} {source} -> {destination}"
            error = asset.get("error")
            if outcome == "failed" and error:
                line += f" | error: {error}"
            lines.append(line)

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
