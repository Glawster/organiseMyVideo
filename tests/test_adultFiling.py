"""Tests for REQ-046 adult scene filing."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo.adultFiling import (
    AdultRelease,
    adultFileName,
    adultFilingPlan,
    adultFilingRun,
    adultPathsValidate,
    adultPerformersSplit,
    adultReleaseParse,
    adultSafeName,
)


def _release(name: str, known=()) -> str:
    release = adultReleaseParse(name, known)
    assert release is not None
    return adultFileName(release, ".mp4")


def _sceneFolder(root: Path, name: str, video: str, *extra: str) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    (folder / video).write_bytes(b"video")
    for other in extra:
        (folder / other).write_text("tracker")
    return folder


## parsing


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]",
            "PervMom - 261004 - Lexi Luna.mp4",
        ),
        (
            "PureTaboo.26.05.26.Sophia.Locke.Her.Loss.His.Gain.XXX.480p.MP4-XXX[XC]",
            "PureTaboo - 260526 - Sophia Locke - Her Loss His Gain.mp4",
        ),
        (
            "PervTherapy.21.10.29.Kenzie.Reeves.And.Penny.Barber.Stepbrother.On.My.Mind.XXX.480p.MP4-XXX",
            "PervTherapy - 211029 - Kenzie Reeves, Penny Barber - Stepbrother On My Mind.mp4",
        ),
        (
            "MomSwap.26.02.26.Sophia.Locke.And.Whitney.OC.XXX.1080p.MP4-WRB[XC]",
            "MomSwap - 260226 - Sophia Locke, Whitney OC.mp4",
        ),
        (
            "Brazzers - Cory Chase, Sophia Locke - The Baddest Milf On The Block - Part 1 (08.05.2026) rq",
            "Brazzers - 260508 - Cory Chase, Sophia Locke - The Baddest Milf On The Block - Part 1.mp4",
        ),
        (
            "[TabooHeat] Cory Chase Halloween Bush or Bald (26.10.31)[720p][xFans]",
            "TabooHeat - 261031 - Cory Chase - Halloween Bush or Bald.mp4",
        ),
        (
            "[MySistersHotFriend] Britney Light (01.03.2018) rq",
            "MySistersHotFriend - 180301 - Britney Light.mp4",
        ),
        (
            "pervmom.26.10.04.lexi.luna",
            "Pervmom - 261004 - Lexi Luna.mp4",
        ),
    ],
)
def testReleaseNamesFollowConvention(name: str, expected: str):
    assert _release(name) == expected


@pytest.mark.parametrize(
    "name",
    ["SoLo-Hrhsbntobdmt1080", "i.dwc261011sl.480p", "Studio.26.13.40.Name.XXX"],
)
def testUnrecognisedNamesAreNotParsed(name: str):
    assert adultReleaseParse(name) is None


def testKnownPerformerFollowingAnotherIsAPerformer():
    name = "MommysGirl.26.08.22.Demi.Hawks.Sophia.Locke.Her.Pro-Domme.Stepmom.XXX.1080p"

    assert (
        _release(name)
        == "MommysGirl - 260822 - Demi Hawks - Sophia Locke Her Pro-Domme Stepmom.mp4"
    )
    assert (
        _release(name, ["Sophia Locke"])
        == "MommysGirl - 260822 - Demi Hawks, Sophia Locke - Her Pro-Domme Stepmom.mp4"
    )


def testKnownThreeWordPerformerIsKeptWhole():
    performers, title = adultPerformersSplit(
        "Mary Jane Doe Night Out".split(), ["Mary Jane Doe"]
    )

    assert performers == ("Mary Jane Doe",)
    assert title == "Night Out"


def testHyphenFormMarksPerformersExplicit():
    release = adultReleaseParse("Milfy - Penny Barber - Title (13.08.2025) rq")

    assert release == AdultRelease(
        "Milfy", date(2025, 8, 13), ("Penny Barber",), "Title", True
    )


def testSafeNameReplacesReservedCharacters():
    assert adultSafeName('A: B/C? "D" *E*') == "A - B - C D E"


## planning


def testPlanLearnsPerformersFromExplicitNames(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    source.mkdir()
    (
        source / "Brazzers - Cory Chase, Emma Shay - Title (08.05.2026) rq.mp4"
    ).write_bytes(b"a")
    (
        source / "[TabooHeat] Cory Chase Emma Shay First (26.10.13)[720p].mp4"
    ).write_bytes(b"b")

    items = adultFilingPlan(source, destination)

    names = sorted(item.destination.name for item in items)
    assert "TabooHeat - 261013 - Cory Chase, Emma Shay - First.mp4" in names


def testPlanFallsBackToFileNameWhenFolderIsUnparsed(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    _sceneFolder(source, "random folder", "PervMom.26.10.04.Lexi.Luna.mp4")

    [item] = adultFilingPlan(source, destination)

    assert (
        item.destination == destination / "PervMom" / "PervMom - 261004 - Lexi Luna.mp4"
    )


def testPlanMarksDuplicateDestinationsAsConflicts(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    _sceneFolder(source, "PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]", "a.mp4")
    _sceneFolder(source, "PervMom.26.10.04.Lexi.Luna.XXX.480p.MP4-XXX[XC]", "b.mp4")

    statuses = sorted(item.status for item in adultFilingPlan(source, destination))

    assert statuses == ["conflict", "move"]


def testPathsRefuseNestedOrEqualFolders(tmp_path: Path):
    inner = tmp_path / "inner"
    inner.mkdir()

    for destination in (tmp_path, inner):
        with pytest.raises(ValueError):
            adultPathsValidate(tmp_path, destination)
    with pytest.raises(ValueError):
        adultPathsValidate(inner, tmp_path)


## workflow


def testDryRunChangesNothing(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    folder = _sceneFolder(
        source,
        "PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]",
        "pervmom.26.10.04.lexi.luna.mp4",
        "Torrent Downloaded From XXXClub.to .nfo",
    )

    stats = adultFilingRun(source, destination, dryRun=True)

    assert stats.moved == 1
    assert (folder / "pervmom.26.10.04.lexi.luna.mp4").exists()
    assert list(destination.iterdir()) == []


def testConfirmedRunMovesVideoAndTidiesReleaseFolder(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    folder = _sceneFolder(
        source,
        "PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]",
        "pervmom.26.10.04.lexi.luna.mp4",
        "Torrent Downloaded From XXXClub.to .nfo",
    )

    stats = adultFilingRun(source, destination, dryRun=False)

    filed = destination / "PervMom" / "PervMom - 261004 - Lexi Luna.mp4"
    assert filed.read_bytes() == b"video"
    assert not folder.exists()
    quarantined = list((source / ".organiseMyVideo-quarantine").rglob("*.nfo"))
    assert len(quarantined) == 1
    assert (stats.moved, stats.errors) == (1, 0)


def testReleaseFolderWithOtherFilesIsKept(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    folder = _sceneFolder(
        source, "PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]", "v.mp4", "cover.jpg"
    )

    stats = adultFilingRun(source, destination, dryRun=False)

    assert (folder / "cover.jpg").exists()
    assert stats.foldersKept == 1


def testUnparsedAndExistingDestinationsAreLeftInPlace(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    unparsed = source / "SoLo-Hrhsbntobdmt1080.mp4"
    unparsed.write_bytes(b"x")
    existing = source / "[TabooHeat] Cory Chase Bald (26.10.31)[720p].mp4"
    existing.write_bytes(b"new")
    target = destination / "TabooHeat" / "TabooHeat - 261031 - Cory Chase - Bald.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old")

    stats = adultFilingRun(source, destination, dryRun=False)

    assert (stats.unparsed, stats.conflicts, stats.moved) == (1, 1, 0)
    assert unparsed.exists() and existing.read_bytes() == b"new"
    assert target.read_bytes() == b"old"


def testFailedMoveKeepsSourceAndCountsError(tmp_path: Path):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    source.mkdir()
    video = source / "[TabooHeat] Cory Chase Bald (26.10.31).mp4"
    video.write_bytes(b"x")

    with patch(
        "organiseMyVideo.filesystemOperations.FilesystemOperations.move",
        side_effect=OSError("disk full"),
    ):
        stats = adultFilingRun(source, destination, dryRun=False)

    assert stats.errors == 1
    assert video.exists()


## cli


@pytest.fixture(autouse=True)
def adultConfig(tmp_path: Path, monkeypatch):
    """Keep every test away from the real config and the real media stores.

    Config is read in ``mainLegacy``; ``__main__`` only re-exports it, so the
    patch must target ``mainLegacy``. The built-in defaults are redirected too,
    so a missing config value can never fall back to a real folder.
    """
    import organiseMyVideo.adultFiling as adultFiling
    import organiseMyVideo.mainLegacy as mainLegacy

    configPath = tmp_path / "config.json"
    monkeypatch.setattr(mainLegacy, "_getAppConfigPath", lambda: configPath)
    monkeypatch.setattr(
        adultFiling, "DEFAULT_ADULT_SOURCE", str(tmp_path / "missingSource")
    )
    monkeypatch.setattr(
        adultFiling, "DEFAULT_ADULT_DESTINATION", str(tmp_path / "missingDestination")
    )
    return configPath


def testDefaultsNeverReachRealStores(tmp_path: Path):
    # With no config, the redirected defaults do not exist, so the run is refused.
    with pytest.raises(SystemExit):
        applicationMain.main(["media", "organise", "--adult", "--confirm"])


def testCliConfirmedRunFilesAndDryRunDoesNot(tmp_path: Path, adultConfig):
    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    _sceneFolder(source, "PervMom.26.10.04.Lexi.Luna.XXX.1080p.MP4-WRB[XC]", "v.mp4")
    arguments = [
        "media",
        "organise",
        "--adult",
        str(source),
        "--destination",
        str(destination),
    ]

    assert applicationMain.main(arguments) == 0
    assert list(destination.iterdir()) == []

    assert applicationMain.main([*arguments, "--confirm"]) == 0
    assert (destination / "PervMom" / "PervMom - 261004 - Lexi Luna.mp4").exists()


def testCliUsesConfiguredFoldersAndPerformers(tmp_path: Path, adultConfig):
    import json

    source, destination = tmp_path / "in", tmp_path / "out"
    destination.mkdir()
    _sceneFolder(
        source, "MommysGirl.26.08.22.Demi.Hawks.Sophia.Locke.Stepmom.XXX", "v.mp4"
    )
    adultConfig.write_text(
        json.dumps(
            {
                "storage_locations": {
                    "adultSource": str(source),
                    "adultDestination": str(destination),
                },
                "adultPerformers": ["Sophia Locke"],
            }
        )
    )

    assert applicationMain.main(["media", "organise", "--adult", "--confirm"]) == 0
    assert (
        destination
        / "MommysGirl"
        / "MommysGirl - 260822 - Demi Hawks, Sophia Locke - Stepmom.mp4"
    ).exists()


def testCliRejectsAdultWithMerge(tmp_path: Path, adultConfig):
    with pytest.raises(SystemExit):
        applicationMain.main(
            [
                "media",
                "organise",
                "--adult",
                "--merge",
                str(tmp_path),
                "--destination",
                str(tmp_path),
            ]
        )


def testCliRejectsDestinationWithoutAdult(tmp_path: Path, adultConfig):
    with pytest.raises(SystemExit):
        applicationMain.main(
            ["media", "organise", str(tmp_path), "--destination", str(tmp_path)]
        )


def testCliRefusesDestinationInsideSource(tmp_path: Path, adultConfig):
    destination = tmp_path / "out"
    destination.mkdir()

    status = applicationMain.main(
        [
            "media",
            "organise",
            "--adult",
            str(tmp_path),
            "--destination",
            str(destination),
        ]
    )

    assert status != 0


def testAdultFoldersIgnoreGeneralSourceConfig(tmp_path: Path, adultConfig):
    import json

    general = tmp_path / "movieStaging"
    general.mkdir()
    adultConfig.write_text(json.dumps({"source": str(general)}))

    # Only adultSource may supply the --adult source; the redirected default
    # does not exist, so the run is refused rather than using "source".
    with pytest.raises(SystemExit):
        applicationMain.main(["media", "organise", "--adult"])


def testGivenFoldersCanBeSavedToTheirOwnConfigKeys(
    tmp_path: Path, adultConfig, monkeypatch
):
    import json

    source, destination = tmp_path / "in", tmp_path / "out"
    source.mkdir()
    destination.mkdir()
    adultConfig.write_text(json.dumps({"source": "/elsewhere"}))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    status = applicationMain.main(
        [
            "media",
            "organise",
            "--adult",
            "-s",
            str(source),
            "--destination",
            str(destination),
        ]
    )

    saved = json.loads(adultConfig.read_text())
    assert status == 0
    assert saved["source"] == "/elsewhere"
    assert saved["storage_locations"] == {
        "adultSource": str(source),
        "adultDestination": str(destination),
    }
