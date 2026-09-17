"""List the latest camera-card inventory snapshots with operator status cues."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .mediaCatalogue import catalogueSchemaApply

ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_RESET = "\033[0m"


@dataclass(frozen=True)
class CameraInventoryListRecord:
    """Latest inventory state for one numbered card."""

    cardId: int
    inventoriedAt: str
    cardBrand: Optional[str]
    cardRatedGigabytes: Optional[int]
    freeBytes: Optional[int]
    contentBytes: int
    volumeKind: str
    snapshotId: Optional[str]
    archived: bool

    @property
    def status(self) -> str:
        """Return the operator-facing card state."""

        if self.contentBytes == 0:
            return "EMPTY"
        if self.archived:
            return "ARCHIVED"
        return "ACTIVE"


def cameraInventoryList(
    databasePath: Path,
    *,
    manifestDirectory: Optional[Path] = None,
) -> tuple[CameraInventoryListRecord, ...]:
    """Return the latest snapshot for every card, including archive state."""

    databasePath = Path(databasePath)
    if not databasePath.is_file():
        return ()

    successfulSnapshots = _successfulSnapshotIds(manifestDirectory)
    with sqlite3.connect(databasePath) as connection:
        connection.row_factory = sqlite3.Row
        catalogueSchemaApply(connection)
        snapshotTable = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'cardInventorySnapshotIdentity'
            """
        ).fetchone()
        snapshotJoin = ""
        snapshotColumn = "NULL AS snapshotId"
        if snapshotTable is not None:
            snapshotJoin = (
                "LEFT JOIN cardInventorySnapshotIdentity identity "
                "ON identity.inventoryId = c.inventoryId"
            )
            snapshotColumn = "identity.snapshotId AS snapshotId"
        rows = connection.execute(
            f"""
            SELECT c.cardId, c.inventoriedAt, c.cardBrand,
                   c.cardRatedGigabytes, c.freeBytes, c.contentBytes,
                   c.volumeKind, {snapshotColumn}
            FROM cardInventory c
            INNER JOIN (
                SELECT cardId, MAX(inventoryId) AS inventoryId
                FROM cardInventory
                GROUP BY cardId
            ) latest ON c.inventoryId = latest.inventoryId
            {snapshotJoin}
            ORDER BY c.cardId
            """
        ).fetchall()

    return tuple(
        CameraInventoryListRecord(
            cardId=int(row["cardId"]),
            inventoriedAt=str(row["inventoriedAt"]),
            cardBrand=row["cardBrand"],
            cardRatedGigabytes=row["cardRatedGigabytes"],
            freeBytes=row["freeBytes"],
            contentBytes=int(row["contentBytes"] or 0),
            volumeKind=str(row["volumeKind"] or "sd"),
            snapshotId=row["snapshotId"],
            archived=(
                row["snapshotId"] is not None
                and str(row["snapshotId"]) in successfulSnapshots
            ),
        )
        for row in rows
    )


def cameraInventoryListSummary(
    records: tuple[CameraInventoryListRecord, ...],
    *,
    useColour: bool = False,
) -> str:
    """Return a compact list with green empty and red archived rows."""

    if not records:
        return "CAMERA CARD INVENTORY\nNo inventoried cards.\n"

    lines = [
        "CAMERA CARD INVENTORY",
        "Card  Status     Brand          Size    Free       Content    Type",
    ]
    for record in records:
        brand = record.cardBrand or "unknown"
        size = (
            f"{record.cardRatedGigabytes} GB"
            if record.cardRatedGigabytes is not None
            else "unknown"
        )
        line = (
            f"{record.cardId:03d}   {record.status:<10} "
            f"{brand[:14]:<14} {size:<7} "
            f"{_bytesFormat(record.freeBytes):<10} "
            f"{_bytesFormat(record.contentBytes):<10} "
            f"{record.volumeKind}"
        )
        lines.append(_statusColour(line, record.status, useColour=useColour))
    lines.append("")
    lines.append(f"{len(records)} card{'s' if len(records) != 1 else ''}")
    return "\n".join(lines) + "\n"


def _successfulSnapshotIds(manifestDirectory: Optional[Path]) -> set[str]:
    """Return snapshot IDs from confirmed imports with no failed assets."""

    if manifestDirectory is None:
        return set()
    directory = Path(manifestDirectory)
    if not directory.is_dir():
        return set()

    snapshotIds: set[str] = set()
    for path in directory.glob("camera-import-*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        snapshotId = payload.get("snapshotId")
        assets = payload.get("assets")
        if not isinstance(snapshotId, str) or not snapshotId.strip():
            continue
        if not isinstance(assets, list):
            continue
        outcomes = [
            asset.get("outcome") for asset in assets if isinstance(asset, dict)
        ]
        if outcomes and "failed" not in outcomes:
            snapshotIds.add(snapshotId)
    return snapshotIds


def _statusColour(line: str, status: str, *, useColour: bool) -> str:
    """Colour one complete row according to card status."""

    if not useColour:
        return line
    if status == "EMPTY":
        return f"{ANSI_GREEN}{line}{ANSI_RESET}"
    if status == "ARCHIVED":
        return f"{ANSI_RED}{line}{ANSI_RESET}"
    return line


def _bytesFormat(value: Optional[int]) -> str:
    """Return a short binary byte count for the list display."""

    if value is None:
        return "unknown"
    amount = float(max(value, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{amount:.1f} TiB"
