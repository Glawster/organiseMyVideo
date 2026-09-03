"""Production-path and compatibility tests for the command-line architecture."""

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import organiseMyVideo.__main__ as applicationMain


@pytest.mark.parametrize(
    ("legacy", "canonical", "mode"),
    [
        (["--source", "/tmp"], ["media", "organise", "/tmp"], "process"),
        (["--source", "/tmp", "--clean"], ["media", "clean", "/tmp"], "clean"),
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


def testEntryPointConfiguresEstablishedLogging(tmp_path: Path):
    organizer = MagicMock()
    configuredLogger = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        with patch.object(
            applicationMain, "getLogger", return_value=configuredLogger
        ) as getLogger:
            status = applicationMain.main(
                ["media", "organise", str(tmp_path), "--verbose"]
            )

    assert status == 0
    getLogger.assert_called_once_with(
        includeConsole=True, dryRun=True, level=applicationMain.logging.DEBUG
    )


def testHandledGalleryFailureReturnsNonzeroStatus():
    gallery = MagicMock()
    gallery.downloadGeneratedMedia.side_effect = RuntimeError("gallery unavailable")

    with patch("organiseMyVideo.grokGallery.GrokGallery", return_value=gallery):
        status = applicationMain.main(["gallery", "download"])

    assert status == 1


def testPackageImportDoesNotMutateMedia(tmp_path: Path):
    media = tmp_path / "camera-original.mp4"
    media.write_bytes(b"original-media")

    import organiseMyVideo

    importlib.reload(organiseMyVideo)

    assert media.read_bytes() == b"original-media"
