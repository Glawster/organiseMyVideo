"""Production-path tests for the command-line architecture."""

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import organiseMyVideo.__main__ as applicationMain


@pytest.mark.parametrize(
    ("legacy", "canonical", "mode"),
    [
        (["--source", "/tmp"], ["media", "organise", "/tmp"], "process"),
        (["--source", "/tmp", "--clean"], ["media", "clean", "/tmp"], "clean"),
        (["--source", "/tmp", "--rescan"], ["media", "scan", "--source", "/tmp"], "rescan"),
        (
            ["--source", "/tmp", "--rescan", "--movie"],
            ["library", "rescan", "/tmp", "--target", "movies"],
            "rescan",
        ),
        (
            ["--source", "/tmp", "--torrent", "--clean"],
            ["torrent", "maintain", "/tmp", "--clean-names"],
            "torrent",
        ),
    ],
)
def testCanonicalAndLegacyArgumentsSelectEquivalentModes(legacy, canonical, mode):
    parser = applicationMain.buildParser()
    legacyArgs = applicationMain._normalizeArguments(parser.parse_args(legacy))
    canonicalArgs = applicationMain._normalizeArguments(parser.parse_args(canonical))

    assert applicationMain._selectedMode(legacyArgs) == mode
    assert applicationMain._selectedMode(canonicalArgs) == mode
    assert canonicalArgs.confirm == legacyArgs.confirm
    assert canonicalArgs.source == legacyArgs.source


def testCanonicalOrganiseDispatchesThroughExistingService(tmp_path: Path):
    organizer = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer) as constructor:
        status = applicationMain.main(["media", "organise", str(tmp_path)])

    assert status == 0
    constructor.assert_called_once_with(
        sourceDir=str(tmp_path),
        dryRun=True,
        refreshMetadataLibrary=False,
        useCurses=True,
    )
    organizer.processFiles.assert_called_once_with(interactive=True)


def testMediaScanDispatchesBothLibrariesThroughExistingService(tmp_path: Path):
    organizer = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        status = applicationMain.main(["media", "scan", "--source", str(tmp_path)])

    assert status == 0
    organizer.resetLibraryMetadata.assert_called_once_with(
        target="both", showFilter=None, deepScan=False
    )


def testMediaScanShowTargetsOneTvShowAcrossRoots(tmp_path: Path):
    organizer = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        status = applicationMain.main(
            ["media", "scan", "--source", str(tmp_path), "--show", "Farscape"]
        )

    assert status == 0
    organizer.resetLibraryMetadata.assert_called_once_with(
        target="tv", showFilter="Farscape", deepScan=False
    )


def testMediaScanAllRequestsDeepIntegrityPass(tmp_path: Path):
    organizer = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        status = applicationMain.main(
            ["media", "scan", "--source", str(tmp_path), "--all"]
        )

    assert status == 0
    organizer.resetLibraryMetadata.assert_called_once_with(
        target="both", showFilter=None, deepScan=True
    )


def testMediaScanUsesConfiguredSourceWhenOverrideIsOmitted(tmp_path: Path):
    organizer = MagicMock()
    configPath = tmp_path / "config.json"
    configPath.write_text(json.dumps({"source": str(tmp_path)}), encoding="utf-8")

    with patch.object(applicationMain, "APP_CONFIG_FILE", configPath):
        with patch(
            "organiseMyVideo.VideoOrganizer", return_value=organizer
        ) as constructor:
            status = applicationMain.main(["media", "scan"])

    assert status == 0
    constructor.assert_called_once_with(
        sourceDir=str(tmp_path),
        dryRun=True,
        refreshMetadataLibrary=False,
        useCurses=True,
    )
    organizer.resetLibraryMetadata.assert_called_once_with(
        target="both", showFilter=None, deepScan=False
    )


def testCanonicalMissingSourceFailsBeforeOrganizerConstruction(tmp_path: Path):
    missing = tmp_path / "missing"

    with patch("organiseMyVideo.VideoOrganizer") as constructor:
        with pytest.raises(SystemExit) as error:
            applicationMain.main(["media", "organise", str(missing)])

    assert error.value.code == 2
    constructor.assert_not_called()


def testConflictingLegacyModesFailBeforeOrganizerConstruction():
    with patch("organiseMyVideo.VideoOrganizer") as constructor:
        with pytest.raises(SystemExit) as error:
            applicationMain.main(["--rescan", "--torrent"])

    assert error.value.code == 2
    constructor.assert_not_called()


def testUniversalVersionAndNestedHelpAreSuccessful(capsys):
    with pytest.raises(SystemExit) as versionExit:
        applicationMain.main(["--version"])
    assert versionExit.value.code == 0
    assert applicationMain.APP_VERSION in capsys.readouterr().out

    with pytest.raises(SystemExit) as helpExit:
        applicationMain.main(["library", "--help"])
    assert helpExit.value.code == 0
    assert "rescan" in capsys.readouterr().out

    with pytest.raises(SystemExit) as mediaHelpExit:
        applicationMain.main(["media", "--help"])
    assert mediaHelpExit.value.code == 0
    assert "scan" in capsys.readouterr().out


def testEntryPointConfiguresEstablishedLogging(tmp_path: Path):
    organizer = MagicMock()
    configuredLogger = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        with patch.object(
            applicationMain, "getLogger", return_value=configuredLogger
        ) as getLogger:
            status = applicationMain.main(
                ["media", "organise", str(tmp_path), "--debug"]
            )

    assert status == 0
    getLogger.assert_called_once_with(
        includeConsole=True, dryRun=True, level=applicationMain.logging.DEBUG
    )


def testHandledGalleryFailureReturnsNonzeroStatus():
    gallery = MagicMock()
    gallery.downloadGeneratedMedia.side_effect = RuntimeError("gallery unavailable")

    with patch("organiseMyVideo.grokGallery.GrokGallery", return_value=gallery):
        status = applicationMain.main(["grok", "--scan"])

    assert status == 1


@pytest.mark.parametrize("removedOption", ["--non-interactive", "--no-curses"])
def testRemovedInteractionOptionsAreRejected(removedOption):
    with pytest.raises(SystemExit) as error:
        applicationMain.main([removedOption])

    assert error.value.code == 2


def testGrokRequiresExactlyOneAction():
    parser = applicationMain.buildParser()

    with pytest.raises(SystemExit) as missingAction:
        parser.parse_args(["grok"])
    with pytest.raises(SystemExit) as conflictingActions:
        parser.parse_args(["grok", "--scan", "--reset"])

    assert missingAction.value.code == 2
    assert conflictingActions.value.code == 2


def testGrokResetDispatchesToGalleryService():
    gallery = MagicMock()
    gallery.resetGrokConfig.return_value = {"deleted": [], "notFound": []}

    with patch("organiseMyVideo.grokGallery.GrokGallery", return_value=gallery):
        status = applicationMain.main(["grok", "--reset", "--confirm"])

    assert status == 0
    gallery.resetGrokConfig.assert_called_once_with()


def testCameraHelpListsSettledActions(capsys):
    with pytest.raises(SystemExit) as helpExit:
        applicationMain.main(["camera", "--help"])

    assert helpExit.value.code == 0
    output = capsys.readouterr().out
    for action in ("list", "show", "scan", "archive", "history", "location", "format"):
        assert action in output
    assert "inventory" not in output
    assert "import" not in output


def testCameraArchiveRequiresSourceOption():
    with pytest.raises(SystemExit) as error:
        applicationMain.main(["camera", "archive"])

    assert error.value.code == 2


def testCameraArchiveRejectsPositionalSource(tmp_path: Path):
    with pytest.raises(SystemExit) as error:
        applicationMain.main(["camera", "archive", str(tmp_path)])

    assert error.value.code == 2


def testCameraArchiveMissingSourceFailsBeforeService(tmp_path: Path):
    missing = tmp_path / "missing"

    with patch("organiseMyVideo.cameraImport.cameraImportRun") as importRun:
        with pytest.raises(SystemExit) as error:
            applicationMain.main(["camera", "archive", "-s", str(missing)])

    assert error.value.code == 2
    importRun.assert_not_called()


def testCameraScanDryRunDoesNotWriteDatabase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from cameraFixtures import cardTreeBuild
    from organiseMyVideo import constants

    databasePath = tmp_path / "mediaCatalogue.sqlite"
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)
    card = cardTreeBuild(tmp_path / "card")

    status = applicationMain.main(["camera", "scan", "-s", str(card), "--card", "12"])

    assert status == 0
    assert not databasePath.exists()


def testCameraScanConfirmPersistsAndShowReadsLatest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from cameraFixtures import cardTreeBuild
    from organiseMyVideo import constants
    from organiseMyVideo.cameraInventory import CameraInventory
    from organiseMyVideo.constants import cameraCardLabelFilename

    databasePath = tmp_path / "mediaCatalogue.sqlite"
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)
    card = cardTreeBuild(tmp_path / "card")
    monkeypatch.setattr(
        CameraInventory,
        "_contentDescribeLive",
        lambda self, paths: "harbour footage",
    )

    confirmStatus = applicationMain.main(
        ["camera", "scan", "-s", str(card), "--card", "12", "--confirm"]
    )
    showStatus = applicationMain.main(["camera", "show", "--card", "12"])

    assert confirmStatus == 0
    assert showStatus == 0
    assert databasePath.is_file()
    stored = CameraInventory(dryRun=True, databasePath=databasePath).inventoryShow(12)
    assert stored is not None
    assert stored.contentSummary == "harbour footage"
    assert (card / cameraCardLabelFilename(12)).is_file()


def testPackageImportDoesNotMutateMedia(tmp_path: Path):
    media = tmp_path / "camera-original.mp4"
    media.write_bytes(b"original-media")

    import organiseMyVideo

    importlib.reload(organiseMyVideo)

    assert media.read_bytes() == b"original-media"


@pytest.mark.parametrize("prefix", [[], ["media", "organise"]])
def testVerboseOptionIsRejected(prefix):
    parser = applicationMain.buildParser()

    with pytest.raises(SystemExit) as error:
        parser.parse_args([*prefix, "--verbose"])

    assert error.value.code == 2
    assert "--verbose" not in parser.format_help()
    assert "--debug" in parser.format_help()


def testCameraLabelPermissionFailurePreservesInventory(tmp_path, monkeypatch, capsys):
    from cameraFixtures import cardTreeBuild
    from organiseMyVideo.filesystemOperations import FilesystemOperations
    from organiseMyVideo import constants

    card = cardTreeBuild(tmp_path / "card")

    def denyWrite(self, path, *args, **kwargs):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(FilesystemOperations, "writeText", denyWrite)
    status = applicationMain.main(
        ["camera", "scan", "-s", str(card), "--card", "2", "-y"]
    )

    assert status == 0
    output = capsys.readouterr().out
    assert "organiseMyVideo.002 could not be written" in output
    assert "inventory snapshot was stored in the database" in output
    assert constants.CAMERA_INVENTORY_DATABASE.exists()
    assert not (card / "organiseMyVideo.002").exists()
