"""Tests for persistent current-location metadata on numbered cards."""

from pathlib import Path

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo import cardLocation as cardLocationModule
from organiseMyVideo import constants
from organiseMyVideo.__main__ import _cameraInventoryLocationRun
from organiseMyVideo.cameraInventory import CameraInventory
from organiseMyVideo.cardLocation import cardLocationGet, cardLocationSet


def testCardLocationSetAndGet(tmp_path: Path):
    databasePath = tmp_path / "mediaCatalogue.sqlite"

    cardLocationSet(
        17,
        "Car JSZ5017",
        databasePath=databasePath,
        dryRun=False,
    )

    assert cardLocationGet(17, databasePath=databasePath) == "Car JSZ5017"


def testDryRunLocationDoesNotReserveCard(tmp_path: Path):
    databasePath = tmp_path / "mediaCatalogue.sqlite"

    result = cardLocationSet(
        7,
        "missing",
        databasePath=databasePath,
        dryRun=True,
    )

    assert result == "missing"
    assert not databasePath.exists()


def testRegisteredLocationReservesCardIdForSuggestions(tmp_path: Path):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    cardLocationSet(1, "drawer", databasePath=databasePath, dryRun=False)
    cardLocationSet(2, "camera bag", databasePath=databasePath, dryRun=False)
    cardLocationSet(3, "missing", databasePath=databasePath, dryRun=False)

    assert service._cardIdsStored() == {1, 2, 3}
    assert service._cardIdNextAvailable() == 4


def testLocationCliCanRegisterMissingCard(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    monkeypatch.setattr(cardLocationModule, "CAMERA_INVENTORY_DATABASE", databasePath)

    status = _cameraInventoryLocationRun(["--card", "7", "--set", "missing"])

    output = capsys.readouterr().out
    assert status == 0
    assert "CARD 7 LOCATION" in output
    assert "missing" in output
    assert "Persisted:        yes" in output
    assert cardLocationGet(7, databasePath=databasePath) == "missing"


def testLocationCliShowsKnownLocation(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    monkeypatch.setattr(cardLocationModule, "CAMERA_INVENTORY_DATABASE", databasePath)
    cardLocationSet(
        17,
        "Car JSZ5017",
        databasePath=databasePath,
        dryRun=False,
    )

    status = _cameraInventoryLocationRun(["--card", "17"])

    output = capsys.readouterr().out
    assert status == 0
    assert "Car JSZ5017" in output


def testCameraLocationDirectCommand(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)

    assert applicationMain.main(
        ["camera", "location", "--card", "18", "--set", "CarBMW"]
    ) == 0
    assert cardLocationGet(18, databasePath=databasePath) == "CarBMW"
    output = capsys.readouterr().out
    assert "CarBMW" in output
    assert "Persisted:        yes" in output

    assert applicationMain.main(["camera", "location", "--card", "18"]) == 0
    output = capsys.readouterr().out
    assert "CarBMW" in output
