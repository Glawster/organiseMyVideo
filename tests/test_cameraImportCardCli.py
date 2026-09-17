"""Focused tests for ``camera import --card`` CLI identity handling."""

from pathlib import Path

import pytest

from organiseMyVideo import __main__ as applicationMain
from organiseMyVideo import cameraImport as cameraImportModule


def testCameraImportParserAcceptsExpectedCardId():
    parser = applicationMain._cameraImportParserBuild()

    args = parser.parse_args(["-s", "/media/card", "--card", "4"])

    assert args.importSource == "/media/card"
    assert args.card == 4


def testCameraImportCardOptionIsRemovedBeforeLegacyParser():
    arguments = [
        "camera",
        "import",
        "-s",
        "/media/card",
        "--card",
        "4",
        "--confirm",
    ]

    cleaned = applicationMain._cameraImportLegacyArguments(arguments)

    assert cleaned == [
        "camera",
        "import",
        "-s",
        "/media/card",
        "--confirm",
    ]


def testUnlabelledExpectedCardGivesInventoryCommand(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "card"
    source.mkdir()
    monkeypatch.setattr(cameraImportModule, "cameraCardIdResolve", lambda _source: None)
    monkeypatch.setattr(cameraImportModule, "cameraImportRun", lambda **_kwargs: None)

    _module, _original, run = applicationMain._cameraImportRunPatch(4)

    with pytest.raises(RuntimeError) as caught:
        run(source=source)

    message = str(caught.value)
    assert "no numbered card label" in message
    assert (
        f"organiseMyVideo camera inventory -s {source} --card 4 --confirm"
        in message
    )


def testLabelledCardPassesExpectedIdentityToImportService(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "card"
    source.mkdir()
    received = {}

    monkeypatch.setattr(cameraImportModule, "cameraCardIdResolve", lambda _source: 4)

    def fakeRun(**kwargs):
        received.update(kwargs)
        return "result"

    monkeypatch.setattr(cameraImportModule, "cameraImportRun", fakeRun)
    _module, _original, run = applicationMain._cameraImportRunPatch(4)

    result = run(source=source)

    assert result == "result"
    assert received["expectedCardId"] == 4
