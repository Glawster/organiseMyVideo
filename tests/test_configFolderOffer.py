"""Tests for offering to save a folder given on the command line to config."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from organiseMyVideo import VideoOrganizer, mainLegacy


def _args(**values) -> argparse.Namespace:
    """Return the arguments an interactive run would carry."""

    return argparse.Namespace(**{"quiet": False, "auto": False, **values})


def _write(path: Path, content: dict) -> None:
    """Store *content* as the test configuration."""

    path.write_text(json.dumps(content), encoding="utf-8")


def _read(path: Path) -> dict:
    """Return the test configuration."""

    return json.loads(path.read_text(encoding="utf-8"))


def _offer(args, configPath, given, keys, *, answer="y", interactive=True):
    """Run one offer and return the mock standing in for the prompt."""

    with (
        patch.object(mainLegacy.sys.stdin, "isatty", return_value=interactive),
        patch("builtins.input", return_value=answer) as prompt,
    ):
        mainLegacy._offerConfigFolderUpdate(args, configPath, "Source", given, keys)
    return prompt


def testAcceptingReplacesValueAndKeepsOtherKeys(tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    configPath = tmp_path / "config.json"
    _write(configPath, {"source": "/old", "tvdb_api_key": "kept"})

    prompt = _offer(_args(), configPath, str(new), ("source",))

    prompt.assert_called_once()
    assert "/old" in prompt.call_args.args[0]
    assert str(new) in prompt.call_args.args[0]
    assert _read(configPath) == {"source": str(new), "tvdb_api_key": "kept"}


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def testAnythingButYesLeavesConfigUnchanged(answer, tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    configPath = tmp_path / "config.json"
    _write(configPath, {"source": "/old"})

    _offer(_args(), configPath, str(new), ("source",), answer=answer)

    assert _read(configPath) == {"source": "/old"}


def testNestedKeyIsReplaced(tmp_path):
    new = tmp_path / "gopro"
    new.mkdir()
    configPath = tmp_path / "config.json"
    _write(configPath, {"storage_locations": {"gopro": "/old", "drone": "/d"}})

    _offer(_args(), configPath, str(new), ("storage_locations", "gopro"))

    assert _read(configPath) == {
        "storage_locations": {"gopro": str(new), "drone": "/d"}
    }


def testMissingValueIsOffered(tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    configPath = tmp_path / "config.json"
    _write(configPath, {"other": 1})

    prompt = _offer(_args(), configPath, str(new), ("source",))

    assert "not set" in prompt.call_args.args[0]
    assert _read(configPath) == {"other": 1, "source": str(new)}


def testSameFolderWithTrailingSlashIsNotOffered(tmp_path):
    folder = tmp_path / "same"
    folder.mkdir()
    configPath = tmp_path / "config.json"
    _write(configPath, {"source": str(folder)})

    prompt = _offer(_args(), configPath, f"{folder}/", ("source",))

    prompt.assert_not_called()


@pytest.mark.parametrize(
    ("arguments", "interactive"),
    [
        ({"quiet": True}, True),
        ({"auto": True}, True),
        ({}, False),
    ],
    ids=["quiet", "auto", "notInteractive"],
)
def testNoOfferWhenItCannotBeAnswered(arguments, interactive, tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    configPath = tmp_path / "config.json"
    _write(configPath, {"source": "/old"})

    prompt = _offer(
        _args(**arguments),
        configPath,
        str(new),
        ("source",),
        interactive=interactive,
    )

    prompt.assert_not_called()
    assert _read(configPath) == {"source": "/old"}


def testMissingFolderIsNotOffered(tmp_path):
    configPath = tmp_path / "config.json"
    _write(configPath, {"source": "/old"})

    prompt = _offer(_args(), configPath, str(tmp_path / "absent"), ("source",))

    prompt.assert_not_called()


def testUnreadableConfigIsNotOverwritten(tmp_path):
    new = tmp_path / "new"
    new.mkdir()
    configPath = tmp_path / "config.json"
    configPath.write_text("{broken", encoding="utf-8")

    prompt = _offer(_args(), configPath, str(new), ("source",))

    prompt.assert_not_called()
    assert configPath.read_text(encoding="utf-8") == "{broken"


def _runClean(source: Path, stores: list[Path]):
    """Run media clean interactively and return the offer mock."""

    organizer = VideoOrganizer(str(source))
    with (
        patch("organiseMyVideo.VideoOrganizer", return_value=organizer),
        patch.object(
            organizer, "_loadConfiguredStorageLocations", return_value=([], stores)
        ),
        patch.object(mainLegacy, "_offerConfigFolderUpdate") as offer,
    ):
        mainLegacy.main(["media", "clean", "-s", str(source)])
    return offer


def testStagingSourceIsOfferedDuringARun(tmp_path):
    source = tmp_path / "video" / "toFile"
    source.mkdir(parents=True)

    offer = _runClean(source, [tmp_path / "video" / "TV"])

    offer.assert_called_once()
    assert offer.call_args.args[2:] == ("Source", str(source), ("source",))


def testSourceOverlappingLibraryIsNeverOffered(tmp_path):
    store = tmp_path / "video" / "TV"
    store.mkdir(parents=True)

    offer = _runClean(tmp_path / "video", [store])

    offer.assert_not_called()
