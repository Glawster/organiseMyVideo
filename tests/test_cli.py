"""Production-path and compatibility tests for the command-line architecture."""

import os
import subprocess
import sys
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


def testEntryPointInitializesLoggingOnce(tmp_path: Path):
    organizer = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        with patch.object(applicationMain, "initializeLogging") as initialize:
            status = applicationMain.main(
                ["media", "organise", str(tmp_path), "--verbose"]
            )

    assert status == 0
    initialize.assert_called_once_with(
        dryRun=True,
        level=applicationMain.logging.DEBUG,
        includeConsole=True,
    )


def testHandledGalleryFailureReturnsNonzeroStatus():
    gallery = MagicMock()
    gallery.downloadGeneratedMedia.side_effect = RuntimeError("gallery unavailable")

    with patch("organiseMyVideo.grokGallery.GrokGallery", return_value=gallery):
        status = applicationMain.main(["gallery", "download"])

    assert status == 1


def testPackageImportCreatesNoApplicationState(tmp_path: Path):
    home = tmp_path / "home"
    state = tmp_path / "state"
    home.mkdir()
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["XDG_STATE_HOME"] = str(state)

    result = subprocess.run(
        [sys.executable, "-c", "import organiseMyVideo"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert list(home.iterdir()) == []
    assert not state.exists()
