"""Tests for canonical positional SOURCE and -s/--source aliases."""

from pathlib import Path

import pytest

import organiseMyVideo.__main__ as applicationMain


@pytest.mark.parametrize(
    ("prefix", "dest"),
    [
        (["media", "organise"], "source"),
        (["media", "clean"], "source"),
        (["library", "rescan"], "source"),
        (["torrent", "maintain"], "source"),
        (["camera", "inventory", "--card", "12"], "inventorySource"),
    ],
)
@pytest.mark.parametrize("option", ["-s", "--source"])
def testCanonicalSourceAliasesMatchPositional(prefix, dest, option, tmp_path: Path):
    parser = applicationMain.buildParser()
    path = str(tmp_path)

    positional = applicationMain._normalizeArguments(parser.parse_args([*prefix, path]))
    optional = applicationMain._normalizeArguments(
        parser.parse_args([*prefix, option, path])
    )

    assert getattr(optional, dest) == path
    assert getattr(optional, dest) == getattr(positional, dest)


def testCameraInventorySourceAliasRunsThroughValidation(tmp_path: Path):
    from cameraFixtures import cardTreeBuild

    card = cardTreeBuild(tmp_path / "card")

    status = applicationMain.main(
        ["camera", "inventory", "-s", str(card), "--card", "12"]
    )

    assert status == 0
