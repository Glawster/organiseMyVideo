"""Tests for compact and full camera-card inventory register views."""

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


def _inventoryCreate(tmpPath: Path, cardId: int) -> Path:
    databasePath = tmpPath / "state" / "mediaCatalogue.sqlite"
    card = tmpPath / f"card-{cardId}"
    (card / "DCIM").mkdir(parents=True)
    (card / "DCIM" / "note.txt").write_text("inventory fixture", encoding="utf-8")
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    record = service.inventoryScan(card, cardId)
    service.inventoryPersist(record)
    return databasePath


def testListIncludesInventoriedAndLocationOnlyCards(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 3)
    cardLocationSet(7, "missing", databasePath=databasePath, dryRun=False)

    entries = cameraInventoryList(databasePath=databasePath)

    assert [entry.cardId for entry in entries] == [3, 7]
    assert entries[0].inventory is not None
    assert entries[0].snapshotCount == 1
    assert entries[1].inventory is None
    assert entries[1].location == "missing"

    summary = cameraInventoryListSummary(entries)
    assert "003" in summary
    assert "007" in summary
    assert "missing" in summary


def testFullListShowsLatestInventoryAndSnapshotCount(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 4)
    cardLocationSet(4, "Car JSZ5017", databasePath=databasePath, dryRun=False)

    entry = cameraInventoryList(databasePath=databasePath, cardId=4)[0]
    summary = cameraInventoryFullSummary(entry)

    assert "CAMERA CARD 004" in summary
    assert "Location:         Car JSZ5017" in summary
    assert "Snapshots:        1" in summary
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
    assert "009" in compact
    assert "missing" in compact

    assert applicationMain.main(
        ["camera", "inventory", "--list", "--full", "--card", "9"]
    ) == 0
    full = capsys.readouterr().out
    assert "CAMERA CARD 009" in full
    assert "Location:         missing" in full
    assert "Inventory:        none" in full
