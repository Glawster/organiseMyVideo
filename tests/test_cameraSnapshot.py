import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

from organiseMyVideo.cameraImport import cameraImportRun
from organiseMyVideo.mediaCatalogue import catalogueSchemaApply


def fileMtimeSet(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def inventorySnapshotInsert(
    databasePath: Path,
    *,
    cardId: int,
    relativePath: str,
    sizeBytes: int,
    inventoriedAt: str,
) -> int:
    with sqlite3.connect(databasePath) as connection:
        catalogueSchemaApply(connection)
        cursor = connection.execute(
            """
            INSERT INTO cardInventory (
                cardId, inventoriedAt, sourcePath, contentBytes, dateSource,
                cameraKinds, videoCount, photoCount, thumbnailCount,
                previewCount, sidecarCount, otherCount, thumbnailSampled,
                contentSummary, visionStatus
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cardId,
                inventoriedAt,
                "/media/card",
                sizeBytes,
                "filesystem",
                "gopro",
                1,
                0,
                0,
                0,
                0,
                0,
                0,
                "",
                "unavailable",
            ),
        )
        inventoryId = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO cardInventoryFile (
                inventoryId, relativePath, sizeBytes, modifiedAt, captureAt,
                kind, cameraKind
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inventoryId,
                relativePath,
                sizeBytes,
                None,
                None,
                "video",
                "gopro",
            ),
        )
        connection.commit()
        return inventoryId


def testConfirmedImportLinksMatchingInventorySnapshot(tmp_path: Path):
    card = tmp_path / "mounted-card"
    source = card / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    (card / "organiseMyVideo.006").write_text(
        json.dumps({"cardId": 6}), encoding="utf-8"
    )
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")
    fileMtimeSet(media, datetime(2024, 4, 20, 12, 0, 0))

    database = tmp_path / "state" / "mediaCatalogue.sqlite"
    database.parent.mkdir(parents=True)
    matchingInventoryId = inventorySnapshotInsert(
        database,
        cardId=6,
        relativePath="DCIM/100GOPRO/GH010111.MP4",
        sizeBytes=media.stat().st_size,
        inventoriedAt="2026-09-12T10:00:00",
    )
    inventorySnapshotInsert(
        database,
        cardId=6,
        relativePath="DCIM/100GOPRO/GH999999.MP4",
        sizeBytes=999,
        inventoriedAt="2026-09-13T10:00:00",
    )

    result = cameraImportRun(
        source=source,
        goproDestination=tmp_path / "archive" / "GoPro",
        droneDestination=tmp_path / "archive" / "Drone",
        dashcamDestination=tmp_path / "archive" / "Dashcam",
        manifestDirectory=tmp_path / "state" / "cameraImports",
        inventoryDatabase=database,
        dryRun=False,
    )

    assert result.cardId == 6
    assert result.snapshotId is not None
    UUID(result.snapshotId)
    manifest = json.loads(result.manifestPath.read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 3
    assert manifest["snapshotId"] == result.snapshotId

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT inventoryId, snapshotId
            FROM cardInventorySnapshotIdentity
            WHERE snapshotId = ?
            """,
            (result.snapshotId,),
        ).fetchone()
    assert row == (matchingInventoryId, result.snapshotId)


def testDryRunDoesNotAssignSnapshotIdentity(tmp_path: Path):
    card = tmp_path / "mounted-card"
    source = card / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    (card / "organiseMyVideo.006").write_text("6\n", encoding="utf-8")
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")
    fileMtimeSet(media, datetime(2024, 4, 20, 12, 0, 0))

    database = tmp_path / "state" / "mediaCatalogue.sqlite"
    database.parent.mkdir(parents=True)
    inventorySnapshotInsert(
        database,
        cardId=6,
        relativePath="DCIM/100GOPRO/GH010111.MP4",
        sizeBytes=media.stat().st_size,
        inventoriedAt="2026-09-12T10:00:00",
    )

    result = cameraImportRun(
        source=source,
        goproDestination=tmp_path / "archive" / "GoPro",
        droneDestination=tmp_path / "archive" / "Drone",
        dashcamDestination=tmp_path / "archive" / "Dashcam",
        manifestDirectory=tmp_path / "state" / "cameraImports",
        inventoryDatabase=database,
        dryRun=True,
    )

    assert result.snapshotId is None
    with sqlite3.connect(database) as connection:
        table = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'cardInventorySnapshotIdentity'
            """
        ).fetchone()
    assert table is None
