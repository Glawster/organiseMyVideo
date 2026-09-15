"""Read-only listing views for the numbered camera-card inventory."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cameraInventory import CameraInventory, CardInventoryRecord, _cardVolumeSummary
from .cardLocation import cardLocationGet
from .constants import CAMERA_INVENTORY_DATABASE


@dataclass(frozen=True)
class CardInventoryListEntry:
    """One known card with its latest inventory and current location."""

    cardId: int
    inventory: Optional[CardInventoryRecord]
    location: Optional[str]
    snapshotCount: int


def cameraInventoryList(
    *,
    databasePath: Optional[Path] = None,
    cardId: Optional[int] = None,
) -> tuple[CardInventoryListEntry, ...]:
    """Return known cards, optionally restricted to one numeric card ID."""

    path = Path(databasePath) if databasePath else CAMERA_INVENTORY_DATABASE
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
        kind = ",".join(record.cameraKinds) if record is not None and record.cameraKinds else "-"
        camera = "-"
        if record is not None:
            camera = " ".join(
                part for part in (record.manufacturer, record.cameraModel) if part
            ) or "-"
        latest = record.inventoriedAt[:19].replace("T", " ") if record is not None else "-"
        rows.append(
            (
                f"{entry.cardId:03d}",
                _status(entry),
                size,
                kind,
                camera,
                entry.location or "-",
                latest,
            )
        )

    headers = (
        "Card",
        "Status",
        "Size",
        "Kind",
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
    if location in {"archive", "archived"}:
        return "archived"
    if location:
        return "in use"
    return "available"


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
