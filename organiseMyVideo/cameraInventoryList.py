"""Read-only listing views for the numbered camera-card inventory."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cameraInventory import CameraInventory, CardInventoryRecord, _cardVolumeSummary
from .cardLocation import cardLocationGet
from .constants import CAMERA_INVENTORY_DATABASE, applicationStateDirectory


@dataclass(frozen=True)
class CardInventoryListEntry:
    """One known card with its latest inventory and current lifecycle evidence."""

    cardId: int
    inventory: Optional[CardInventoryRecord]
    location: Optional[str]
    snapshotCount: int
    archived: bool


def cameraInventoryList(
    *,
    databasePath: Optional[Path] = None,
    cardId: Optional[int] = None,
    manifestDirectory: Optional[Path] = None,
) -> tuple[CardInventoryListEntry, ...]:
    """Return known cards, optionally restricted to one numeric card ID."""

    path = Path(databasePath) if databasePath else CAMERA_INVENTORY_DATABASE
    manifests = Path(
        manifestDirectory or applicationStateDirectory() / "cameraImports"
    )
    service = CameraInventory(dryRun=True, databasePath=path)
    ids = sorted(service._cardIdsStored())
    if cardId is not None:
        if isinstance(cardId, bool) or not isinstance(cardId, int) or cardId < 1:
            raise ValueError("card ID must be a positive integer")
        ids = [value for value in ids if value == cardId]

    return tuple(
        CardInventoryListEntry(
            cardId=value,
            inventory=service.inventoryShow(value),
            location=cardLocationGet(value, databasePath=path),
            snapshotCount=_snapshotCount(path, value),
            archived=_latestSnapshotArchived(path, manifests, value),
        )
        for value in ids
    )


def cameraInventoryListSummary(entries: tuple[CardInventoryListEntry, ...]) -> str:
    """Return a compact one-row-per-card inventory register."""

    if not entries:
        return "CAMERA CARD INVENTORY\n\nNo cards registered.\n"

    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for entry in entries:
        record = entry.inventory
        size = (
            f"{record.cardRatedGigabytes} GB"
            if record is not None and record.cardRatedGigabytes
            else "-"
        )
        mediaType = record.volumeKind if record is not None and record.volumeKind else "-"
        camera = "-"
        if record is not None and _status(entry) != "missing":
            camera = " ".join(
                part for part in (record.manufacturer, record.cameraModel) if part
            ) or "-"
        latest = record.inventoriedAt[:19].replace("T", " ") if record is not None else "-"
        rows.append(
            (
                f"{entry.cardId:03d}",
                _status(entry),
                mediaType,
                size,
                camera,
                entry.location or "-",
                latest,
            )
        )

    headers = (
        "Card",
        "Status",
        "Type",
        "Size",
        "Camera",
        "Location",
        "Last inventory",
    )
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    def line(values: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values)).rstrip()

    separator = tuple("-" * width for width in widths)
    body = "\n".join(line(row) for row in rows)
    return f"CAMERA CARD INVENTORY\n\n{line(headers)}\n{line(separator)}\n{body}\n"


def cameraInventoryFullSummary(entry: CardInventoryListEntry) -> str:
    """Return detailed current metadata for one known card."""

    header = (
        f"CAMERA CARD {entry.cardId:03d}\n"
        f"  Status:           {_status(entry)}\n"
        f"  Location:         {entry.location or 'unknown'}\n"
        f"  Snapshots:        {entry.snapshotCount}\n"
        f"  Latest archived:  {'yes' if entry.archived else 'no'}\n"
    )
    if entry.inventory is None:
        return header + "  Inventory:        none\n"

    record = entry.inventory
    return (
        header
        + f"  Last inventoried: {record.inventoriedAt}\n\n"
        + _cardVolumeSummary(record)
    )


def _status(entry: CardInventoryListEntry) -> str:
    """Return the current lifecycle status for one known card."""

    location = (entry.location or "").strip().lower()
    if location == "missing":
        return "missing"
    if location and location not in {"archive", "archived"}:
        return "in use"

    record = entry.inventory
    if record is None or record.capacity.contentBytes <= 0:
        return "empty"
    if entry.archived:
        return "available"
    return "to archive"


def _latestSnapshotArchived(
    databasePath: Path,
    manifestDirectory: Path,
    cardId: int,
) -> bool:
    """Return whether the latest inventory snapshot was imported successfully."""

    snapshotId = _latestSnapshotId(databasePath, cardId)
    if snapshotId is None or not manifestDirectory.is_dir():
        return False

    for path in manifestDirectory.glob("camera-import-*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("snapshotId") != snapshotId:
            continue
        assets = payload.get("assets")
        if not isinstance(assets, list):
            continue
        if all(
            isinstance(asset, dict)
            and asset.get("outcome") in {"copied", "alreadyPresent"}
            for asset in assets
        ):
            return True
    return False


def _latestSnapshotId(databasePath: Path, cardId: int) -> Optional[str]:
    if not databasePath.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{databasePath}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not {"cardInventory", "cardInventorySnapshotIdentity"}.issubset(tables):
            return None
        row = connection.execute(
            """
            SELECT identity.snapshotId
            FROM cardInventory AS inventory
            LEFT JOIN cardInventorySnapshotIdentity AS identity
              ON identity.inventoryId = inventory.inventoryId
            WHERE inventory.cardId = ?
            ORDER BY inventory.inventoryId DESC
            LIMIT 1
            """,
            (cardId,),
        ).fetchone()
        return None if row is None or row[0] is None else str(row[0])
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _snapshotCount(databasePath: Path, cardId: int) -> int:
    if not databasePath.is_file():
        return 0
    try:
        connection = sqlite3.connect(f"file:{databasePath}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0
    try:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cardInventory'"
        ).fetchone()
        if table is None:
            return 0
        row = connection.execute(
            "SELECT COUNT(*) FROM cardInventory WHERE cardId = ?",
            (cardId,),
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0
    finally:
        connection.close()
