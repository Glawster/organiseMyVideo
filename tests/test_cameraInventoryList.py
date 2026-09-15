"""Tests for compact and full camera-card inventory register views."""

import json
import sqlite3
from pathlib import Path

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo import constants
from organiseMyVideo.cameraInventory import CameraInventory
from organiseMyVideo.cameraInventoryList import (
    cameraInventoryFullSummary,
    cameraInventoryList,
    cameraInventoryListSummary,
)
from organiseMyVideo.cardLocation import cardLocationSet


def _inventoryCreate(tmpPath: Path, cardId: int, *, empty: bool = False) -> Path:
    databasePath = tmpPath / "state" / "mediaCatalogue.sqlite"
    card = tmpPath / f"card-{cardId}"
    (card / "DCIM").mkdir(parents=True)
    if not empty:
        (card / "DCIM" / "note.txt").write_text("inventory fixture", encoding="utf-8")
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    record = service.inventoryScan(card, cardId)
    service.inventoryPersist(record)
    return databasePath


def _latestSnapshotArchive(
    databasePath: Path,
    manifestDirectory: Path,
    cardId: int,
) -> None:
    snapshotId = f"snapshot-{cardId}"
    with sqlite3.connect(databasePath) as connection:
        inventoryId = connection.execute(
            "SELECT MAX(inventoryId) FROM cardInventory WHERE cardId = ?",
            (cardId,),
        ).fetchone()[0]
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cardInventorySnapshotIdentity (
                inventoryId INTEGER PRIMARY KEY,
                snapshotId TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            "INSERT INTO cardInventorySnapshotIdentity (inventoryId, snapshotId) VALUES (?, ?)",
            (inventoryId, snapshotId),
        )
        connection.commit()

    manifestDirectory.mkdir(parents=True)
    payload = {
        "snapshotId": snapshotId,
        "assets": [{"outcome": "copied"}],
    }
    (manifestDirectory / "camera-import-test.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def testListIncludesInventoriedAndLocationOnlyCards(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 3)
    cardLocationSet(7, "missing", databasePath=databasePath, dryRun=False)

    entries = cameraInventoryList(
        databasePath=databasePath,
        manifestDirectory=tmp_path / "manifests",
    )

    assert [entry.cardId for entry in entries] == [3, 7]
    assert entries[0].inventory is not None
    assert entries[0].snapshotCount == 1
    assert entries[1].inventory is None
    assert entries[1].location == "missing"

    summary = cameraInventoryListSummary(entries)
    assert "Status" in summary
    assert "Type" in summary
    assert "003" in summary
    assert "to archive" in summary
    assert "007" in summary
    assert "missing" in summary


def testInUseStatusForKnownCardWithLocation(tmp_path: Path):
    databasePath = tmp_path / "state" / "mediaCatalogue.sqlite"
    cardLocationSet(8, "Desk drawer", databasePath=databasePath, dryRun=False)

    summary = cameraInventoryListSummary(
        cameraInventoryList(
            databasePath=databasePath,
            manifestDirectory=tmp_path / "manifests",
        )
    )

    assert "008" in summary
    assert "in use" in summary
    assert "Desk drawer" in summary


def testEmptyStatusForEmptyUnlocatedCard(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 10, empty=True)

    summary = cameraInventoryListSummary(
        cameraInventoryList(
            databasePath=databasePath,
            manifestDirectory=tmp_path / "manifests",
        )
    )

    assert "010" in summary
    assert "empty" in summary


def testArchivedContentMakesUnlocatedCardAvailable(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 11)
    manifestDirectory = tmp_path / "manifests"
    _latestSnapshotArchive(databasePath, manifestDirectory, 11)

    entries = cameraInventoryList(
        databasePath=databasePath,
        manifestDirectory=manifestDirectory,
    )
    summary = cameraInventoryListSummary(entries)

    assert entries[0].archived is True
    assert "011" in summary
    assert "available" in summary
    assert "to archive" not in summary


def testMissingCardDoesNotPresentOldCameraAsCurrent(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 12)
    with sqlite3.connect(databasePath) as connection:
        connection.execute(
            "UPDATE cardInventory SET manufacturer = 'GoPro', cameraModel = 'HERO9' WHERE cardId = 12"
        )
        connection.commit()
    cardLocationSet(12, "missing", databasePath=databasePath, dryRun=False)

    summary = cameraInventoryListSummary(
        cameraInventoryList(
            databasePath=databasePath,
            manifestDirectory=tmp_path / "manifests",
        )
    )

    row = next(line for line in summary.splitlines() if line.startswith("012"))
    assert "missing" in row
    assert "GoPro" not in row
    assert "HERO9" not in row


def testFullListShowsLatestInventoryAndSnapshotCount(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 4)
    cardLocationSet(4, "Car JSZ5017", databasePath=databasePath, dryRun=False)

    entry = cameraInventoryList(
        databasePath=databasePath,
        cardId=4,
        manifestDirectory=tmp_path / "manifests",
    )[0]
    summary = cameraInventoryFullSummary(entry)

    assert "CAMERA CARD 004" in summary
    assert "Status:           in use" in summary
    assert "Location:         Car JSZ5017" in summary
    assert "Snapshots:        1" in summary
    assert "Latest archived:  no" in summary
    assert "Last inventoried:" in summary
    assert "CAMERA CARD INVENTORY" in summary


def testInventoryListCliSupportsFullCardView(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    databasePath = tmp_path / "state" / "mediaCatalogue.sqlite"
    cardLocationSet(9, "missing", databasePath=databasePath, dryRun=False)
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)

    assert applicationMain.main(["camera", "inventory", "--list"]) == 0
    compact = capsys.readouterr().out
    assert "Status" in compact
    assert "Type" in compact
    assert "009" in compact
    assert "missing" in compact

    assert applicationMain.main(
        ["camera", "inventory", "--list", "--full", "--card", "9"]
    ) == 0
    full = capsys.readouterr().out
    assert "CAMERA CARD 009" in full
    assert "Status:           missing" in full
    assert "Location:         missing" in full
    assert "Inventory:        none" in full
