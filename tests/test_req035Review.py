"""Regression coverage for the final REQ-035 review findings."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from organiseMyVideo import VideoOrganizer
from organiseMyVideo.mediaLocate import locateTvShow
from organiseMyVideo.showFolders import (
    canonicalMovieFolderName,
    canonicalTvShowFolderName,
    movieFilesystemSafeTitle,
)


def _organizer(tmp_path: Path) -> VideoOrganizer:
    return VideoOrganizer(sourceDir=str(tmp_path), dryRun=True, useCurses=False)


def testColonTitleKeepsDisplayIdentityAndUsesFilesystemSeparator(tmp_path: Path):
    title = "The Walking Dead: Dead City"
    folder = tmp_path / canonicalTvShowFolderName(title)
    folder.mkdir()

    assert movieFilesystemSafeTitle(title) == "The Walking Dead - Dead City"
    assert canonicalTvShowFolderName(title) == "Walking Dead - Dead City, The"
    assert (
        canonicalMovieFolderName(f"{title} (2023)")
        == "Walking Dead - Dead City, The (2023)"
    )

    class Catalogue:
        def catalogueTvSeriesList(self, states=None):
            return [
                SimpleNamespace(
                    showName=title,
                    folderPath=str(folder),
                    locationState="current",
                )
            ]

    located = locateTvShow("dead city", catalogue=Catalogue())
    assert [item.name for item in located] == [title]
    assert located[0].folderPath == str(folder)


def testPathLikeMcmTitleBlocksEvenWhenNormalisedIdentityAgrees(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder = tmp_path / "Q - Movies - Entangled (2019)"
    folder.mkdir()
    feature = folder / "Q - Movies - Entangled (2019).mkv"
    feature.write_bytes(b"feature")
    movieInfo = {
        "title": r"Q:\Movies\Entangled (2019)",
        "year": "2019",
        "metadataSource": "mcm",
        "tmdbId": "641556",
    }

    with patch("organiseMyVideo.movieIdentityReview.logger.warning") as warning:
        assert organizer._refuseMovieIdentityChange(movieInfo, folder, feature) is True

    report = warning.call_args.args[1]
    assert report.startswith("movie metadata identity suspect\n")
    assert f"folder: {folder}" in report
    assert "reason: metadata title contains a filesystem path" in report
    assert "tmdb: 641556" in report


def _entangled(tmp_path: Path, title: str, runtime: str) -> tuple[Path, Path, dict]:
    folder = tmp_path / "Entangled (2019)"
    folder.mkdir()
    feature = folder / "Entangled (2019).mkv"
    feature.write_bytes(b"feature")
    movieInfo = {
        "title": title,
        "year": "2019",
        "metadataSource": "mcm",
        "runtime": runtime,
        "tmdbId": "641556",
    }
    return folder, feature, movieInfo


def testRuntimeContradictionAddsEvidenceToTitleConflict(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder, feature, movieInfo = _entangled(tmp_path, "One Second Forever", "3")

    probeResult = SimpleNamespace(durationSeconds=91 * 60)
    with patch(
        "organiseMediaStudio.video.probe.videoProbe", return_value=probeResult
    ) as probe:
        with patch("organiseMyVideo.movieIdentityReview.logger.warning") as warning:
            assert (
                organizer._refuseMovieIdentityChange(movieInfo, folder, feature) is True
            )

    probe.assert_called_once_with(feature)
    assert movieInfo["mediaRuntime"] == "91"
    report = warning.call_args.args[1]
    assert report.startswith("movie metadata identity suspect\n")
    assert f"folder: {folder}" in report
    assert "reason: metadata runtime conflicts materially with media runtime" in report
    assert "metadata runtime: 3" in report
    assert "media runtime: 91" in report


def testRuntimeContradictionAloneDoesNotBlockAgreeingIdentity(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder, feature, movieInfo = _entangled(tmp_path, "Entangled", "3")

    probeResult = SimpleNamespace(durationSeconds=91 * 60)
    with patch("organiseMediaStudio.video.probe.videoProbe", return_value=probeResult):
        with patch("organiseMyVideo.movieIdentityReview.logger.warning") as warning:
            assert (
                organizer._refuseMovieIdentityChange(movieInfo, folder, feature)
                is False
            )

    warning.assert_not_called()


def testZeroMetadataRuntimeIsNotReported(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder, feature, movieInfo = _entangled(tmp_path, "Entangled", "0")

    probeResult = SimpleNamespace(durationSeconds=89.5 * 60)
    with patch("organiseMediaStudio.video.probe.videoProbe", return_value=probeResult):
        with patch("organiseMyVideo.movieIdentityReview.logger.warning") as warning:
            assert (
                organizer._refuseMovieIdentityChange(movieInfo, folder, feature)
                is False
            )

    warning.assert_not_called()


def testShortFeatureIsReportedOnceAsPossiblyIncomplete(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder, feature, movieInfo = _entangled(tmp_path, "Entangled", "137")

    probeResult = SimpleNamespace(durationSeconds=12.9 * 60)
    with patch(
        "organiseMediaStudio.video.probe.videoProbe", return_value=probeResult
    ) as probe:
        with patch("organiseMyVideo.movieIdentityReview.logger.warning") as warning:
            assert (
                organizer._refuseMovieIdentityChange(movieInfo, folder, feature)
                is False
            )
            # The guard runs again after enrichment, without transient state.
            enriched = organizer._movieMetadataWithoutIdentityState(movieInfo)
            assert "mediaRuntime" not in enriched
            assert (
                organizer._refuseMovieIdentityChange(enriched, folder, feature) is False
            )

    probe.assert_called_once_with(feature)
    warning.assert_called_once()
    report = warning.call_args.args[1]
    assert report.startswith("movie file possibly incomplete\n")
    assert f"folder: {folder}" in report
    assert f"file: {feature.name}" in report
    assert "metadata runtime: 137" in report
    assert "media runtime: 12.9" in report


def testAncillaryDescriptorsDoNotConsumeRealFeatureTitles(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder = tmp_path / "Movies"
    folder.mkdir()

    interview = folder / "The Interview (2014).mkv"
    trailerPark = folder / "Trailer Park Boys (2006).mkv"
    behindScenes = folder / "Michael McIntyre - Behind The Scenes.mkv"
    for path in (interview, trailerPark, behindScenes):
        path.write_bytes(b"video")

    assert organizer._isResetMovieAncillaryFile(folder, interview) is False
    assert organizer._isResetMovieAncillaryFile(folder, trailerPark) is False
    assert organizer._isResetMovieAncillaryFile(folder, behindScenes) is True


def testOrdinaryIdentityConflictWarningIncludesFolderPath(tmp_path: Path):
    organizer = _organizer(tmp_path)
    folder = tmp_path / "13 minutes (2021)"
    folder.mkdir()
    feature = folder / "13 minutes (2021).mkv"
    feature.write_bytes(b"feature")
    movieInfo = {
        "title": "One Second Forever",
        "year": "2021",
        "metadataSource": "mcm",
    }

    with patch("organiseMyVideo.movieIdentityReview.logger.warning") as warning:
        assert organizer._refuseMovieIdentityChange(movieInfo, folder, feature) is True

    report = warning.call_args.args[1]
    assert report.startswith("movie identity conflict\n")
    assert f"folder: {folder}" in report
    assert "current: 13 minutes (2021)" in report
    assert "proposed: One Second Forever (2021)" in report
    assert "evidence: movie.xml" in report
