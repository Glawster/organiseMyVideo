"""Tests for suggesting the next free camera-card ID on first inventory."""

from pathlib import Path

import pytest

from cameraFixtures import cardTreeBuild
from organiseMyVideo.cameraInventory import CameraInventory


def testUnlabelledCardSuggestsOneWhenCatalogueIsEmpty(tmp_path: Path):
    card = cardTreeBuild(tmp_path / "card")
    databasePath = tmp_path / "state" / "cameraInventory.sqlite"
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    with pytest.raises(ValueError) as error:
        service.inventoryScan(card)

    message = str(error.value)
    assert "no card ID found on this card" in message
    assert "existing card IDs: none" in message
    assert "suggested card ID: 1" in message
    assert "re-run with --card 1" in message
    assert not databasePath.exists()


def testUnlabelledCardSuggestsLowestGap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    card = cardTreeBuild(tmp_path / "card")
    service = CameraInventory(
        dryRun=True,
        databasePath=tmp_path / "state" / "cameraInventory.sqlite",
    )
    monkeypatch.setattr(service, "_cardIdsStored", lambda: {1, 2, 4, 5})

    with pytest.raises(ValueError) as error:
        service.inventoryScan(card)

    message = str(error.value)
    assert "existing card IDs: 1, 2, 4, 5" in message
    assert "suggested card ID: 3" in message
    assert "re-run with --card 3" in message


def testNextAvailableCardIdDoesNotCreateMissingDatabase(tmp_path: Path):
    databasePath = tmp_path / "state" / "cameraInventory.sqlite"
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    assert service._cardIdNextAvailable() == 1
    assert not databasePath.exists()
