"""Persistent current-location metadata for numbered removable media."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .constants import CAMERA_INVENTORY_DATABASE


CARD_LOCATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS cardLocation (
    cardId INTEGER PRIMARY KEY,
    location TEXT NOT NULL,
    updatedAt TEXT NOT NULL
);
"""


def cardLocationGet(
    cardId: int,
    *,
    databasePath: Optional[Path] = None,
) -> Optional[str]:
    """Return the current stored physical location for *cardId*."""

    cardId = _cardIdValidate(cardId)
    path = Path(databasePath) if databasePath else CAMERA_INVENTORY_DATABASE
    if not path.is_file():
        return None
    with sqlite3.connect(path) as connection:
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cardLocation'"
        ).fetchone()
        if table is None:
            return None
        row = connection.execute(
            "SELECT location FROM cardLocation WHERE cardId = ?",
            (cardId,),
        ).fetchone()
    return None if row is None else str(row[0])


def cardLocationSet(
    cardId: int,
    location: str,
    *,
    databasePath: Optional[Path] = None,
    dryRun: bool = True,
) -> str:
    """Set the current physical location for *cardId* and return it."""

    cardId = _cardIdValidate(cardId)
    location = _locationValidate(location)
    if dryRun:
        return location

    path = Path(databasePath) if databasePath else CAMERA_INVENTORY_DATABASE
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(CARD_LOCATION_SCHEMA)
        connection.execute(
            """
            INSERT INTO cardLocation (cardId, location, updatedAt)
            VALUES (?, ?, ?)
            ON CONFLICT(cardId) DO UPDATE SET
                location = excluded.location,
                updatedAt = excluded.updatedAt
            """,
            (cardId, location, _timestampNow()),
        )
        connection.commit()
    return location


def cardLocationSummary(cardId: int, location: Optional[str]) -> str:
    """Return a concise user-facing location summary."""

    value = location or "unknown"
    return f"CARD {cardId} LOCATION\n  Location:         {value}\n"


def _cardIdValidate(cardId: int) -> int:
    if isinstance(cardId, bool) or not isinstance(cardId, int) or cardId < 1:
        raise ValueError("card ID must be a positive integer")
    return cardId


def _locationValidate(location: str) -> str:
    value = str(location).strip()
    if not value:
        raise ValueError("location must not be empty")
    return value


def _timestampNow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
