"""Tests for compact and detailed camera-card inventory views."""

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


def _inventoryCreate(
    tmpPath: Path,
    cardId: int,
    *,
    empty: bool = False,
    review: bool = False,
) -> Path:
    databasePath = tmpPath / "state" / "mediaCatalogue.sqlite"
    card = tmpPath / f"card-{cardId}"
    (card / "DCIM").mkdir(parents=True)
    if review:
        (card / "notes.csv").write_text("important,filesystem,data", encoding="utf-8")
    elif not empty:
        (card / "DCIM" / "clip.mp4").write_bytes(b"camera footage")
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    record = service.inventoryScan(card, cardId)
    service.inventoryPersist(record)
    return databasePath


def _latestSnapshotArchive(
    databasePath: Path,
    manifestDirectory: Path,
    cardId: int,
    *,
    createdAt: str = "2026-09-15T18:05:00+00:00",
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

    manifestDirectory.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshotId": snapshotId,
        "createdAt": createdAt,
        "source": {"cardId": cardId},
        "assets": [{"outcome": "copied"}],
    }
    (manifestDirectory / "camera-import-test.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def testListIncludesInventoriedAndLocationOnlyCards(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 3)
    cardLocationSet(7, "missing", databasePath=databasePath, dryRun=False)
    entries = cameraInventoryList(databasePath=databasePath, manifestDirectory=tmp_path / "manifests")
    assert [entry.cardId for entry in entries] == [3, 7]
    assert entries[0].snapshotCount == 1
    assert entries[1].location == "missing"
    summary = cameraInventoryListSummary(entries)
    assert "Status" in summary
    assert "Archived" in summary
    assert "003" in summary and "to archive" in summary
    assert "007" in summary and "missing" in summary


def testInUseStatusForKnownCardWithLocation(tmp_path: Path):
    databasePath = tmp_path / "state" / "mediaCatalogue.sqlite"
    cardLocationSet(8, "Desk drawer", databasePath=databasePath, dryRun=False)
    summary = cameraInventoryListSummary(
        cameraInventoryList(databasePath=databasePath, manifestDirectory=tmp_path / "manifests")
    )
    assert "008" in summary
    assert "in use" in summary
    assert "Desk drawer" in summary


def testEmptyStatusForEmptyUnlocatedCard(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 10, empty=True)
    summary = cameraInventoryListSummary(
        cameraInventoryList(databasePath=databasePath, manifestDirectory=tmp_path / "manifests")
    )
    assert "010" in summary
    assert "empty" in summary


def testReviewStatusForNonCameraFilesystemContent(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 10, review=True)
    entries = cameraInventoryList(
        databasePath=databasePath,
        manifestDirectory=tmp_path / "manifests",
    )
    summary = cameraInventoryListSummary(entries)
    detail = cameraInventoryFullSummary(entries[0])

    assert "010" in summary
    assert "review" in summary
    assert "to archive" not in summary
    assert "Other files:        1" in detail


def testArchivedContentMakesUnlocatedCardAvailable(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 11)
    manifests = tmp_path / "manifests"
    _latestSnapshotArchive(databasePath, manifests, 11)
    entries = cameraInventoryList(databasePath=databasePath, manifestDirectory=manifests)
    row = next(line for line in cameraInventoryListSummary(entries).splitlines() if line.startswith("011"))
    assert entries[0].archived is True
    assert entries[0].archiveDates == ("2026-09-15T18:05:00+00:00",)
    assert "available" in row
    assert "yes" in row


def testMissingCardDoesNotPresentOldCameraAsCurrent(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 12)
    with sqlite3.connect(databasePath) as connection:
        connection.execute(
            "UPDATE cardInventory SET manufacturer = 'GoPro', cameraModel = 'HERO9' WHERE cardId = 12"
        )
        connection.commit()
    cardLocationSet(12, "missing", databasePath=databasePath, dryRun=False)
    summary = cameraInventoryListSummary(
        cameraInventoryList(databasePath=databasePath, manifestDirectory=tmp_path / "manifests")
    )
    row = next(line for line in summary.splitlines() if line.startswith("012"))
    assert "missing" in row
    assert "GoPro" not in row and "HERO9" not in row


def testCardDetailShowsLifecycleArchiveHistoryAndUsefulInventory(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 18)
    manifests = tmp_path / "manifests"
    _latestSnapshotArchive(databasePath, manifests, 18)
    entry = cameraInventoryList(
        databasePath=databasePath,
        cardId=18,
        manifestDirectory=manifests,
    )[0]
    summary = cameraInventoryFullSummary(entry)
    assert "CAMERA CARD 018" in summary
    assert "Status:             available" in summary
    assert "Snapshots:          1" in summary
    assert "Last archived:      2026/09/15 18:05" in summary
    assert "Previous archives:  -" in summary
    assert "Last inventoried:" in summary
    assert "CAMERA CARD INVENTORY" in summary
    assert "Type:" in summary
    assert "Keywords:" in summary
    assert "Source:" not in summary
    assert "Volume:" not in summary
    assert "T" not in next(line for line in summary.splitlines() if "Last inventoried:" in line)


def testCameraCliUsesListAndShowCommands(tmp_path: Path, monkeypatch, capsys):
    databasePath = tmp_path / "state" / "mediaCatalogue.sqlite"
    cardLocationSet(9, "missing", databasePath=databasePath, dryRun=False)
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)

    assert applicationMain.main(["camera", "list"]) == 0
    compact = capsys.readouterr().out
    assert "Status" in compact and "009" in compact and "missing" in compact

    assert applicationMain.main(["camera", "show", "--card", "9"]) == 0
    detail = capsys.readouterr().out
    assert "CAMERA CARD 009" in detail
    assert "Status:             missing" in detail
    assert "Location:           missing" in detail
    assert "Inventory:          none" in detail
