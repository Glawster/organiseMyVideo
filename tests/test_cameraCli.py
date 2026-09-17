"""Tests for the public camera lifecycle command family."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo import constants
from organiseMyVideo.cameraCli import _cameraParserBuild, _volumeKindResolve
from organiseMyVideo.cardLocation import cardLocationGet


def testCameraHelpExposesSettledActions():
    parser = _cameraParserBuild()
    helpText = parser.format_help()

    for action in ("list", "show", "scan", "archive", "history", "format", "location"):
        assert action in helpText
    assert "inventory" not in helpText
    assert "import" not in helpText


def testOldInventoryAndImportCommandsAreNotPublic():
    with pytest.raises(SystemExit):
        applicationMain.main(["camera", "inventory", "--list"])
    with pytest.raises(SystemExit):
        applicationMain.main(["camera", "import", "-s", "/media/card"])


def testCameraLocationUsesSetWithoutConfirm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)

    assert applicationMain.main(
        ["camera", "location", "--card", "18", "--set", "CarBMW"]
    ) == 0

    output = capsys.readouterr().out
    assert "CarBMW" in output
    assert "Persisted:        yes" in output
    assert cardLocationGet(18, databasePath=databasePath) == "CarBMW"


def testCameraFormatParserUsesCardArgument():
    parser = _cameraParserBuild()
    args = parser.parse_args(["format", "--card", "18"])

    assert args.cameraAction == "format"
    assert args.card == 18
    assert args.confirm is False


def testCameraScanParserUsesSourceAndOptionalCard():
    parser = _cameraParserBuild()
    args = parser.parse_args(["scan", "-s", "/media/card", "--card", "18"])

    assert args.cameraAction == "scan"
    assert args.source == "/media/card"
    assert args.card == 18


def testCameraIdentityKeepsEmptyCameraCardAsSd():
    record = SimpleNamespace(
        cameraKinds=(),
        manufacturer="GoPro",
        cameraModel="HERO",
        cameraSerial="serial",
        firmwareVersion="firmware",
        cameraWifiMac=None,
        goproCardId=None,
    )

    assert _volumeKindResolve(record) == "sd"


def testUnknownVolumeWithoutCameraEvidenceIsUsb():
    record = SimpleNamespace(
        cameraKinds=(),
        manufacturer=None,
        cameraModel=None,
        cameraSerial=None,
        firmwareVersion=None,
        cameraWifiMac=None,
        goproCardId=None,
    )

    assert _volumeKindResolve(record) == "usb"


def testCameraArchiveHelpOnlyShowsOperationalArguments():
    parser = _cameraParserBuild()
    archiveParser = parser._subparsers._group_actions[0].choices["archive"]
    helpText = archiveParser.format_help()

    assert "--source" in helpText
    assert "--card" in helpText
    assert "--confirm" in helpText
    for removed in (
        "--brand",
        "--gopro-destination",
        "--drone-destination",
        "--dashcam-destination",
        "--manifest-directory",
        "--include-gopro-companions",
    ):
        assert removed not in helpText


def testCameraHistoryRequiresCard():
    parser = _cameraParserBuild()
    args = parser.parse_args(["history", "--card", "18"])

    assert args.cameraAction == "history"
    assert args.card == 18

    with pytest.raises(SystemExit):
        parser.parse_args(["history"])


def testRemovedCameraOptionsAreRejected():
    parser = _cameraParserBuild()

    with pytest.raises(SystemExit):
        parser.parse_args(["scan", "-s", "/media/card", "--brand", "Transcend"])
    with pytest.raises(SystemExit):
        parser.parse_args(["archive", "-s", "/media/card", "--brand", "Transcend"])
    with pytest.raises(SystemExit):
        parser.parse_args([
            "archive",
            "-s",
            "/media/card",
            "--gopro-destination",
            "/tmp/gopro",
        ])
