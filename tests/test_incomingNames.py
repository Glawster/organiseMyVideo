"""Incoming preparation boundaries and read-only classification acceptance."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from organiseMyVideo import VideoOrganizer
from organiseMyVideo import mainLegacy
from organiseMyVideo.incomingNames import incomingNameNormalise, mediaNameIsAncillary
from organiseMyVideo.showFolders import movieFilesystemSafeTitle


@pytest.mark.parametrize("site", ["www.UIndex.org", "www.Torrenting.com"])
def testPureCandidate(site, tmp_path):
    name = f"{site}    -    Avatar 2024 S02E02.mkv"
    source = tmp_path / name
    source.write_bytes(b"feature")
    with patch("pathlib.Path.rename", side_effect=AssertionError("mutation")):
        assert incomingNameNormalise(name) == "Avatar 2024 S02E02.mkv"
    assert source.exists()


@pytest.mark.parametrize("confirmed", [False, True])
def testCleanSourceBoundary(confirmed, tmp_path):
    source = tmp_path / "incoming"
    source.mkdir()
    library = tmp_path / "library"
    library.mkdir()
    external = library / "empty"
    external.mkdir()
    (source / "escape").symlink_to(library, target_is_directory=True)
    staged = source / "www.UIndex.org - Movie (2020)"
    staged.mkdir()
    (staged / "Movie (2020).mkv").write_bytes(b"feature")
    sample = source / "sample-only"
    sample.mkdir()
    (sample / "EVO-sample.mkv").write_bytes(b"sample")
    empty = source / "empty"
    empty.mkdir()
    organizer = VideoOrganizer(str(source), dryRun=not confirmed)
    organizer.cleanNames()
    organizer.cleanEmptyFolders()
    assert external.exists()
    assert (source / "escape").is_symlink()
    assert sample.exists() is not confirmed
    assert empty.exists() is not confirmed
    for operation in organizer.filesystem.operations:
        for path in (operation.source, operation.destination):
            if path is not None:
                Path(path).resolve().relative_to(source.resolve())
    # Retained quarantine must not be recursively cleaned by subsequent runs.
    organizer.cleanEmptyFolders()
    if confirmed:
        assert list(source.glob(".organiseMyVideo-quarantine/**/*.mkv"))


def testCleanNeverDiscoversLibraries(tmp_path):
    organizer = VideoOrganizer(str(tmp_path), dryRun=False)
    with (
        patch("organiseMyVideo.VideoOrganizer", return_value=organizer),
        patch.object(
            organizer,
            "scanStorageLocations",
            side_effect=AssertionError("library scan"),
        ),
        patch.object(
            mainLegacy, "_normaliseSeasonFolders", side_effect=AssertionError("repair")
        ),
    ):
        assert (
            mainLegacy.main(["media", "clean", "-s", str(tmp_path), "--confirm"]) == 0
        )


def testScanCompatibilityConfirmationIsObservation(tmp_path):
    organizer = MagicMock()
    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer) as factory:
        assert mainLegacy.main(["media", "scan", "-s", str(tmp_path), "--confirm"]) == 0
    assert factory.call_args.kwargs["dryRun"] is True
    organizer.cleanNames.assert_not_called()
    organizer.cleanEmptyFolders.assert_not_called()


def testFeatureWinsOverNoisyParent(tmp_path):
    folder = tmp_path / "undecidable release garbage"
    folder.mkdir()
    feature = folder / "www.UIndex.org - Aladdin (2019).mkv"
    feature.write_bytes(b"feature")
    organizer = VideoOrganizer(str(tmp_path))
    tv, movie = organizer._classifyVideoFile(feature, None)
    assert tv is None
    assert movie["title"] == "Aladdin"
    assert feature.exists()


def testCleanedFolderFallback(tmp_path):
    folder = tmp_path / "www.UIndex.org - Aladdin (2019)"
    folder.mkdir()
    feature = folder / "feature.mkv"
    feature.write_bytes(b"feature")
    organizer = VideoOrganizer(str(tmp_path))
    assert organizer._classifyVideoFile(feature, None)[1]["title"] == "Aladdin"
    assert feature.exists()


@pytest.mark.parametrize(
    "name",
    [
        "Sample.mkv",
        "sample - includes commentary track.mkv",
        "sample - extended german market version - multi audio english german russian.mkv",
        "EVO-sample.mkv",
        "RARBG.COM.mp4",
    ],
)
def testAncillaryVariants(name, tmp_path):
    organizer = VideoOrganizer(str(tmp_path))
    assert organizer._isResetMovieAncillaryFile(tmp_path, tmp_path / name)
    assert not organizer._summaryInvestigations


def testSampleDirectoryAndTokenBoundaries(tmp_path):
    organizer = VideoOrganizer(str(tmp_path))
    assert organizer._isResetMovieAncillaryFile(
        tmp_path, tmp_path / "Sample" / "clip.mkv"
    )
    assert not mediaNameIsAncillary("Resampled (2020).mkv")


def testMultipartKeepsDistinctDestination(tmp_path):
    organizer = VideoOrganizer(str(tmp_path))
    info = {"title": "Aladdin", "year": "2019"}
    assert (
        organizer._buildMovieDestinationFilename(
            tmp_path / "Aladdin (2019)-part2.mkv", info
        )
        == "Aladdin (2019)-part2.mkv"
    )


def testReadableTitle():
    assert (
        movieFilesystemSafeTitle("TAYLOR SWIFT | THE ERAS TOUR")
        == "Taylor Swift - The Eras Tour"
    )
    assert movieFilesystemSafeTitle("Anyone But You") == "Anyone But You"


def testConfirmedScanRealMediaPipeline(tmp_path):
    """Run real metadata parsing, collision planning and summaries through the CLI."""
    source = tmp_path / "incoming"
    source.mkdir()
    storage = tmp_path / "movies"
    folder = storage / "Aladdin (2019)"
    folder.mkdir(parents=True)
    for name in (
        "Aladdin (2019).mkv",
        "Aladdin (2019)-part2.mkv",
        "EVO-sample.mkv",
        "RARBG.COM.mp4",
        "Aladdin.2019.1080p.mkv",
    ):
        (folder / name).write_bytes(b"video")
    (folder / "movie.xml").write_text(
        "<Title><LocalTitle>Aladdin</LocalTitle><ProductionYear>2019</ProductionYear></Title>"
    )
    before = {
        p.relative_to(storage): p.read_bytes()
        for p in storage.rglob("*")
        if p.is_file()
    }
    instances = []

    def construct(**kwargs):
        instance = VideoOrganizer(**kwargs)
        instances.append(instance)
        return instance

    with (
        patch("organiseMyVideo.VideoOrganizer", side_effect=construct),
        patch.object(
            VideoOrganizer, "scanStorageLocations", return_value=([storage], [])
        ),
        patch.object(VideoOrganizer, "_prepareMetadataLibrary"),
        patch.object(VideoOrganizer, "_mediaCatalogueReplace"),
        patch.object(
            VideoOrganizer, "_enrichMovieMetadata", side_effect=lambda value: value
        ),
        patch.object(VideoOrganizer, "_fetchMovieArtwork"),
        patch.object(
            mainLegacy, "_getSummaryReportPath", return_value=tmp_path / "summary.txt"
        ),
    ):
        assert mainLegacy.main(["media", "scan", "-s", str(source), "--confirm"]) == 0
    after = {
        p.relative_to(storage): p.read_bytes()
        for p in storage.rglob("*")
        if p.is_file()
    }
    assert after == before
    assert not instances[0].filesystem.operations
    report = (tmp_path / "summary.txt").read_text()
    assert "possible duplicate" in report
    investigation = report.split("Needs further investigation:")[1]
    assert "EVO-sample" not in investigation
    assert "RARBG" not in investigation
    assert "part2" not in investigation


def testCleanRejectsExternalQuarantine(tmp_path):
    source = tmp_path / "incoming"
    source.mkdir()
    empty = source / "empty"
    empty.mkdir()
    organizer = VideoOrganizer(str(source), dryRun=False)
    organizer.filesystem.quarantineRoot = tmp_path / "outside"
    assert organizer.cleanEmptyFolders()["errors"] == 1
    assert empty.exists()
    assert not (tmp_path / "outside").exists()


def testCleanRejectsSymlinkedQuarantine(tmp_path):
    source = tmp_path / "incoming"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (source / ".organiseMyVideo-quarantine").symlink_to(
        outside, target_is_directory=True
    )
    empty = source / "empty"
    empty.mkdir()
    organizer = VideoOrganizer(str(source), dryRun=False)
    assert organizer.cleanEmptyFolders()["errors"] == 1
    assert empty.exists()
    assert not list(outside.iterdir())


def testMovieScanUsesCleanedParentWithoutRename(tmp_path):
    folder = tmp_path / "www.UIndex.org - Aladdin (2019)"
    folder.mkdir()
    feature = folder / "feature.mkv"
    feature.write_bytes(b"video")
    organizer = VideoOrganizer(str(tmp_path))
    with patch.object(
        organizer, "_enrichMovieMetadata", side_effect=lambda value: value
    ):
        info = organizer._resolveResetMovieInfo(feature)
    assert info["title"] == "Aladdin"
    assert feature.exists()
    assert not organizer.filesystem.operations


def testCleanUsesConfiguredSource(tmp_path):
    organizer = VideoOrganizer(str(tmp_path))
    with (
        patch.object(mainLegacy, "_configuredSource", return_value=str(tmp_path)),
        patch("organiseMyVideo.VideoOrganizer", return_value=organizer) as factory,
    ):
        assert mainLegacy.main(["media", "clean"]) == 0
    assert factory.call_args.kwargs["sourceDir"] == str(tmp_path)


def testCleanRejectsEscapedCandidate(tmp_path):
    entry = tmp_path / "www.UIndex.org - .."
    entry.mkdir()
    organizer = VideoOrganizer(str(tmp_path), dryRun=False)
    assert organizer.cleanNames()["errors"] == 1
    assert entry.exists()
    assert not organizer.filesystem.operations
