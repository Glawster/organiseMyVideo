"""Link confirmed camera imports to durable camera-inventory snapshots."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Iterable, Optional

from .cameraPlan import ImportOperation
from .constants import CAMERA_INVENTORY_DATABASE
from .mediaCatalogue import catalogueSchemaApply


SNAPSHOT_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS cardInventorySnapshotIdentity (
    inventoryId INTEGER PRIMARY KEY,
    snapshotId TEXT NOT NULL UNIQUE,
    FOREIGN KEY (inventoryId) REFERENCES cardInventory(inventoryId)
);
"""


def cameraSnapshotMatch(
    *,
    cardId: int,
    operations: Iterable[ImportOperation],
    databasePath: Optional[Path] = None,
    assignIdentity: bool = False,
) -> Optional[str]:
    """Return the newest inventory snapshot matching the import evidence.

    Matching uses durable ``cardId`` plus relative-path suffix and file size.
    The suffix rule allows import to start at the card root, ``DCIM`` directory,
    or a supported camera-media directory while inventory remains rooted at the
    complete card snapshot.  Ambiguous per-file matches are rejected.

    ``assignIdentity`` may create the UUID mapping for an older inventory row
    that predates explicit snapshot IDs.  Callers must only enable it for a
    confirmed operation; dry-run must leave application state unchanged.
    """

    path = Path(databasePath or CAMERA_INVENTORY_DATABASE)
    if not path.is_file():
        return None

    evidence = _operationEvidence(operations)
    if not evidence:
        return None

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        catalogueSchemaApply(connection)
        connection.executescript(SNAPSHOT_IDENTITY_SCHEMA)
        snapshots = connection.execute(
            """
            SELECT inventoryId
            FROM cardInventory
            WHERE cardId = ?
            ORDER BY inventoryId DESC
            """,
            (cardId,),
        ).fetchall()
        for snapshot in snapshots:
            inventoryId = int(snapshot["inventoryId"])
            rows = connection.execute(
                """
                SELECT relativePath, sizeBytes
                FROM cardInventoryFile
                WHERE inventoryId = ?
                """,
                (inventoryId,),
            ).fetchall()
            if not _snapshotEvidenceMatches(evidence, rows):
                continue
            identity = connection.execute(
                """
                SELECT snapshotId
                FROM cardInventorySnapshotIdentity
                WHERE inventoryId = ?
                """,
                (inventoryId,),
            ).fetchone()
            if identity is not None:
                return str(identity["snapshotId"])
            if not assignIdentity:
                return None
            snapshotId = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO cardInventorySnapshotIdentity (inventoryId, snapshotId)
                VALUES (?, ?)
                """,
                (inventoryId, snapshotId),
            )
            connection.commit()
            return snapshotId
    return None


def _operationEvidence(
    operations: Iterable[ImportOperation],
) -> tuple[tuple[str, int], ...]:
    """Return unique relative-path/size evidence for considered import assets."""

    evidence: set[tuple[str, int]] = set()
    for operation in operations:
        source = operation.asset.sourcePath
        try:
            size = source.stat().st_size
        except OSError:
            continue
        relative = operation.asset.relativePath.replace("\\", "/").lstrip("/")
        if relative:
            evidence.add((relative, size))
    return tuple(sorted(evidence))


def _snapshotEvidenceMatches(
    evidence: tuple[tuple[str, int], ...], rows: Iterable[sqlite3.Row]
) -> bool:
    """Return True when every import asset uniquely matches the snapshot."""

    inventory = [
        (str(row["relativePath"]).replace("\\", "/").lstrip("/"), int(row["sizeBytes"]))
        for row in rows
    ]
    for relative, size in evidence:
        matches = [
            item
            for item in inventory
            if item[1] == size
            and (item[0] == relative or item[0].endswith("/" + relative))
        ]
        if len(matches) != 1:
            return False
    return True
