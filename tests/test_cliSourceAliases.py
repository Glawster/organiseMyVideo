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

    # Explicit options win regardless of their position relative to SOURCE.
    for arguments in (["/unused", option, path], [option, path, "/unused"]):
        combined = applicationMain._normalizeArguments(
            parser.parse_args([*prefix, *arguments])
        )
        assert getattr(combined, dest) == path


@pytest.mark.parametrize("option", ["-s", "--source"])
def testCameraScanSourceOptionRunsThroughValidation(tmp_path: Path, option: str):
    from cameraFixtures import cardTreeBuild

    card = cardTreeBuild(tmp_path / "card")

    status = applicationMain.main(
        ["camera", "scan", option, str(card), "--card", "12"]
    )

    assert status == 0
