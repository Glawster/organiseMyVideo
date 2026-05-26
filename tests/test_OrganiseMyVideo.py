"""Tests for organiseMyVideo.py"""

import errno
import io
import json
import logging
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# conftest.py stubs organiseMyProjects before this import
import organiseMyVideo.__main__ as omv_main
from organiseMyVideo import VideoOrganizer
from organiseMyVideo import video as video_module
from organiseMyVideo.video import (
    _FILE_PROCESS_SEPARATOR,
    _XML_BINARY_CHECK_WINDOW,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sourceDir(tmp_path: Path) -> Path:
    """Return an empty temporary source directory."""
    src = tmp_path / "source"
    src.mkdir()
    return src


@pytest.fixture()
def organizer(sourceDir: Path) -> VideoOrganizer:
    """VideoOrganizer in dry-run mode (default) pointing at a temp source."""
    return VideoOrganizer(sourceDir=str(sourceDir), dryRun=True)


@pytest.fixture()
def confirmedOrganizer(sourceDir: Path) -> VideoOrganizer:
    """VideoOrganizer with dryRun=False (confirm mode)."""
    return VideoOrganizer(sourceDir=str(sourceDir), dryRun=False)


# ---------------------------------------------------------------------------
# VideoOrganizer.__init__
# ---------------------------------------------------------------------------


def testDefaultDryRunIsTrue():
    """dryRun must default to True (safe mode)."""
    org = VideoOrganizer()
    assert org.dryRun is True


def testExplicitDryRunFalse(tmp_path: Path):
    org = VideoOrganizer(sourceDir=str(tmp_path), dryRun=False)
    assert org.dryRun is False


def testLoggerMultilineRendersIndentedEntries(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("INFO"):
        video_module.logger.multiline("tv show", "old.mkv", "new.mkv")

    assert "...tv show:\n     old.mkv\n     new.mkv" in caplog.text


def _savedAfterLifeMetadataLibrary() -> dict:
    """Return a minimal saved metadata library for After Life S01E04."""
    return {
        "version": 1,
        "movies": {},
        "tv": {
            "series": {
                "series:347507": {
                    "type": "tv",
                    "showName": "After Life",
                    "seriesId": "347507",
                    "imdbId": None,
                    "metadataSource": "mcm",
                    "metadataUpdatedAt": "2026-05-11T00:00:00+00:00",
                },
                "show:afterlife": {
                    "type": "tv",
                    "showName": "After Life",
                    "seriesId": "347507",
                    "imdbId": None,
                    "metadataSource": "mcm",
                    "metadataUpdatedAt": "2026-05-11T00:00:00+00:00",
                },
            },
            "episodes": {
                "series:347507:s01e04": {
                    "type": "tv",
                    "showName": "After Life",
                    "season": 1,
                    "episode": 4,
                    "episodeTitle": "Sic Semper Systema",
                    "seriesId": "347507",
                    "episodeId": "10751471",
                    "metadataSource": "mcm",
                    "metadataUpdatedAt": "2026-05-11T00:00:00+00:00",
                },
                "show:afterlife:s01e04": {
                    "type": "tv",
                    "showName": "After Life",
                    "season": 1,
                    "episode": 4,
                    "episodeTitle": "Sic Semper Systema",
                    "seriesId": "347507",
                    "episodeId": "10751471",
                    "metadataSource": "mcm",
                    "metadataUpdatedAt": "2026-05-11T00:00:00+00:00",
                },
            },
        },
    }


def testOptionalFlagsDefaults():
    org = VideoOrganizer()
    assert org.refreshMetadataLibrary is False
    assert org.useCurses is True


# ---------------------------------------------------------------------------
# parseTvFilename
# ---------------------------------------------------------------------------


def testParseTvFilenameValid(organizer: VideoOrganizer):
    result = organizer.parseTvFilename("Breaking.Bad.S01E01.Pilot.mkv")
    assert result is not None
    assert result["showName"] == "Breaking Bad"
    assert result["season"] == 1
    assert result["episode"] == 1
    assert result["episodeTitle"] == "Pilot"
    assert result["type"] == "tv"


def testParseTvFilenameHighSeasonEpisode(organizer: VideoOrganizer):
    result = organizer.parseTvFilename("The.Office.S12E25.Finale.mkv")
    assert result is not None
    assert result["showName"] == "The Office"
    assert result["season"] == 12
    assert result["episode"] == 25


def testParseTvFilenameWithoutEpisodeTitle(organizer: VideoOrganizer):
    result = organizer.parseTvFilename("Virgin.River.S06E01.mkv")
    assert result is not None
    assert result["showName"] == "Virgin River"
    assert result["season"] == 6
    assert result["episode"] == 1
    assert result["episodeTitle"] is None


def testParseTvFilenameWithSpaces(organizer: VideoOrganizer):
    result = organizer.parseTvFilename("The Pitt S01E13 7 00 P M (1080).mkv")
    assert result is not None
    assert result["showName"] == "The Pitt"
    assert result["season"] == 1
    assert result["episode"] == 13
    assert result["episodeTitle"] == "7 00 P M (1080)"
    assert result["type"] == "tv"


def testParseTvFilenameStripsTrailingReleaseNoise(organizer: VideoOrganizer):
    result = organizer.parseTvFilename(
        "The.Pitt.S02E05.Pilot.1080p.WEB.h264.successfulcrab.EZTVx.to.mkv"
    )
    assert result is not None
    assert result["showName"] == "The Pitt"
    assert result["episodeTitle"] == "Pilot"


def testParseTvFilenameStripsTrailingBracketMetadataNoise(organizer: VideoOrganizer):
    result = organizer.parseTvFilename(
        "24.S08E13.Day 8 4AM-5AM[Action-Drama-Mystery][2010].avi"
    )
    assert result is not None
    assert result["showName"] == "24"
    assert result["episodeTitle"] == "Day 8 4.00am-5.00am"


def testParseTvFilenameDropsNoiseOnlyEpisodeTitle(organizer: VideoOrganizer):
    result = organizer.parseTvFilename(
        "The.Pitt.S02E05.1080p.WEB.h264.successfulcrab.EZTVx.to.mkv"
    )
    assert result is not None
    assert result["showName"] == "The Pitt"
    assert result["episodeTitle"] is None


def testParseTvFilenameReturnsNoneForMovie(organizer: VideoOrganizer):
    assert organizer.parseTvFilename("Inception (2010).mp4") is None


def testParseTvFilenameReturnsNoneForRandomName(organizer: VideoOrganizer):
    assert organizer.parseTvFilename("some random file.mkv") is None


# ---------------------------------------------------------------------------
# parseMovieFilename
# ---------------------------------------------------------------------------


def testParseMovieFilenameParenthetical(organizer: VideoOrganizer):
    result = organizer.parseMovieFilename("Inception (2010).mp4")
    assert result is not None
    assert result["title"] == "Inception"
    assert result["year"] == "2010"
    assert result["type"] == "movie"


def testParseMovieFilenameDotSeparated(organizer: VideoOrganizer):
    result = organizer.parseMovieFilename("The.Matrix.1999.mkv")
    assert result is not None
    assert result["year"] == "1999"
    assert result["type"] == "movie"


def testParseMovieFilenameReturnsNoneForUnparseable(organizer: VideoOrganizer):
    assert organizer.parseMovieFilename("randomfile.mkv") is None


# ---------------------------------------------------------------------------
# MCM metadata hints
# ---------------------------------------------------------------------------


def testReadMcmHintsReturnsMovieMetadata(sourceDir: Path, organizer: VideoOrganizer):
    movieDir = sourceDir / "3 from Hell (2019)"
    movieDir.mkdir()
    movieFile = movieDir / "clip.mp4"
    movieFile.write_bytes(b"x" * 50)
    (movieDir / "movie.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Title>
    <LocalTitle>3 from Hell</LocalTitle>
    <ProductionYear>2019</ProductionYear>
    <IMDbId>tt8134742</IMDbId>
    <TMDbId>489064</TMDbId>
</Title>
""",
        encoding="utf-8",
    )

    hints = organizer._readMcmHints(movieFile)

    assert hints == {
        "type": "movie",
        "title": "3 from Hell",
        "year": "2019",
        "imdbId": "tt8134742",
        "tmdbId": "489064",
        "metadataSource": "mcm",
        "mcm": {
            "movieXmlExists": True,
            "dvdIdXmlExists": False,
            "artworkExists": False,
        },
    }


def testReadMcmHintsReturnsTvMetadata(sourceDir: Path, organizer: VideoOrganizer):
    showDir = sourceDir / "After Life"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    videoFile = seasonDir / "episode.mkv"
    videoFile.write_bytes(b"x" * 50)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>After Life</SeriesName>
    <SeriesID>347507</SeriesID>
</Series>
""",
        encoding="utf-8",
    )
    (metadataDir / "episode.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>10751471</EpisodeID>
    <EpisodeNumber>4</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeName>Sic Semper Systema</EpisodeName>
    <IMDB_ID>tt21357478</IMDB_ID>
</Item>
""",
        encoding="utf-8",
    )

    hints = organizer._readMcmHints(videoFile)

    assert hints == {
        "type": "tv",
        "showName": "After Life",
        "season": 1,
        "episode": 4,
        "episodeTitle": "Sic Semper Systema",
        "imdbId": "tt21357478",
        "seriesId": "347507",
        "episodeId": "10751471",
        "metadataSource": "mcm",
        "mcm": {
            "showXmlExists": True,
            "dvdIdXmlExists": False,
            "seasonMetadataFolderExists": True,
            "episodeXmlExists": True,
            "artworkExists": False,
        },
    }


def testReadMcmHintsInfersTvSeasonFromSeriesAndPath(
    sourceDir: Path, organizer: VideoOrganizer
):
    showDir = sourceDir / "Virgin River"
    seasonDir = showDir / "Season 6"
    seasonDir.mkdir(parents=True)
    videoFile = seasonDir / "new-episode.mkv"
    videoFile.write_bytes(b"x" * 50)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Virgin River</SeriesName>
    <SeriesID>117581</SeriesID>
</Series>
""",
        encoding="utf-8",
    )

    hints = organizer._readMcmHints(videoFile)

    assert hints == {
        "type": "tv",
        "showName": "Virgin River",
        "season": 6,
        "episode": None,
        "episodeTitle": None,
        "imdbId": None,
        "seriesId": "117581",
        "episodeId": None,
        "metadataSource": "mcm",
        "mcm": {
            "showXmlExists": True,
            "dvdIdXmlExists": False,
            "seasonMetadataFolderExists": False,
            "episodeXmlExists": False,
            "artworkExists": False,
        },
    }


def testReadMcmHintsFallsBackToEpisodeSeriesIdWhenSeriesXmlBlank(
    sourceDir: Path, organizer: VideoOrganizer
):
    showDir = sourceDir / "After Life"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    videoFile = seasonDir / "episode.mkv"
    videoFile.write_bytes(b"x" * 50)
    (showDir / "series.xml").write_text("<Series />", encoding="utf-8")
    (metadataDir / "episode.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>10751471</EpisodeID>
    <EpisodeNumber>4</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeName>Sic Semper Systema</EpisodeName>
    <SeriesID>347507</SeriesID>
</Item>
""",
        encoding="utf-8",
    )

    hints = organizer._readMcmHints(videoFile)

    assert hints is not None
    assert hints["seriesId"] == "347507"


def testReadMcmHintsIgnoresBinaryEpisodeXmlWithoutWarning(
    sourceDir: Path, organizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    showDir = sourceDir / "Royal Marines Commando School"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    videoFile = seasonDir / "episode.mkv"
    videoFile.write_bytes(b"x" * 50)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Royal Marines Commando School</SeriesName>
    <SeriesID>999999</SeriesID>
</Series>
""",
        encoding="utf-8",
    )
    (metadataDir / "episode.xml").write_bytes(b"\x00" * _XML_BINARY_CHECK_WINDOW)

    with caplog.at_level("WARNING"):
        hints = organizer._readMcmHints(videoFile)

    assert hints == {
        "type": "tv",
        "showName": "Royal Marines Commando School",
        "season": 1,
        "episode": None,
        "episodeTitle": None,
        "imdbId": None,
        "seriesId": "999999",
        "episodeId": None,
        "metadataSource": "mcm",
        "mcm": {
            "showXmlExists": True,
            "dvdIdXmlExists": False,
            "seasonMetadataFolderExists": True,
            "episodeXmlExists": True,
            "artworkExists": False,
        },
    }
    assert "could not parse metadata XML" not in caplog.text


def testReadTvSeriesMcmHintsFallsBackToDvdIdSeriesIdWhenSeriesXmlMissing(
    sourceDir: Path, organizer: VideoOrganizer
):
    showDir = sourceDir / "Virgin River"
    showDir.mkdir()
    (showDir / "mcm_id__117581.dvdid.xml").write_text(
        "<Item><SeriesID>117581</SeriesID></Item>", encoding="utf-8"
    )

    hints = organizer._readTvSeriesMcmHints(showDir)

    assert hints is not None
    assert hints["seriesId"] == "117581"
    assert hints["mcm"]["showXmlExists"] is False
    assert hints["mcm"]["dvdIdXmlExists"] is True


def testReadMcmHintsDetectsMovieArtworkWithoutMovieXml(
    sourceDir: Path, organizer: VideoOrganizer
):
    movieDir = sourceDir / "3 from Hell (2019)"
    movieDir.mkdir()
    movieFile = movieDir / "clip.mp4"
    movieFile.write_bytes(b"x" * 50)
    (movieDir / "folder.jpg").write_bytes(b"poster")
    (movieDir / "mcm_id__tt8134742-489064.dvdid.xml").write_text(
        "<Disc />", encoding="utf-8"
    )

    hints = organizer._readMcmHints(movieFile)

    assert hints == {
        "type": "movie",
        "title": None,
        "year": None,
        "imdbId": None,
        "tmdbId": None,
        "metadataSource": "mcm",
        "mcm": {
            "movieXmlExists": False,
            "dvdIdXmlExists": True,
            "artworkExists": True,
        },
    }


def testReadTvSeriesMcmHintsReportsShowEpisodeXmlAndArtwork(
    sourceDir: Path, organizer: VideoOrganizer
):
    showDir = sourceDir / "After Life"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    (showDir / "series.xml").write_text("<Series />", encoding="utf-8")
    (showDir / "folder.jpg").write_bytes(b"poster")
    (metadataDir / "episode.xml").write_text("<Item />", encoding="utf-8")

    hints = organizer._readTvSeriesMcmHints(showDir)

    assert hints is not None
    assert hints["mcm"] == {
        "showXmlExists": True,
        "dvdIdXmlExists": False,
        "seasonMetadataFolderExists": True,
        "episodeXmlExists": True,
        "artworkExists": True,
    }


# ---------------------------------------------------------------------------
# scanStorageLocations
# ---------------------------------------------------------------------------


def testScanStorageLocationsFindsMovieDirs(tmp_path: Path, organizer: VideoOrganizer):
    """movie<n> directories are detected as movie storage."""
    mnt = tmp_path / "mnt"
    (mnt / "movie1").mkdir(parents=True)
    (mnt / "movie2").mkdir(parents=True)
    with patch("organiseMyVideo.video.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert len(movieDirs) == 2
    assert len(videoDirs) == 0


def testScanStorageLocationsFindsMyPicturesAsMovieStorage(
    tmp_path: Path, organizer: VideoOrganizer
):
    """/mnt/myPictures root is used as movie storage when no Movies subdir exists."""
    mnt = tmp_path / "mnt"
    (mnt / "myPictures").mkdir(parents=True)
    with patch("organiseMyVideo.video.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert any(d.name == "myPictures" for d in movieDirs)
    assert len(videoDirs) == 0


def testScanStorageLocationsUsesMyPicturesMoviesSubdir(
    tmp_path: Path, organizer: VideoOrganizer
):
    """/mnt/myPictures/Movies is used as movie storage when the Movies subdir exists."""
    mnt = tmp_path / "mnt"
    (mnt / "myPictures" / "Movies").mkdir(parents=True)
    with patch("organiseMyVideo.video.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert any(d.name == "Movies" for d in movieDirs)
    assert len(videoDirs) == 0


def testScanStorageLocationsFindsMyVideoAsTvStorage(
    tmp_path: Path, organizer: VideoOrganizer
):
    """/mnt/myVideo/TV is detected as TV storage."""
    mnt = tmp_path / "mnt"
    tvDir = mnt / "myVideo" / "TV"
    tvDir.mkdir(parents=True)
    with patch("organiseMyVideo.video.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert len(movieDirs) == 0
    assert any(d.name == "TV" for d in videoDirs)


def testScanStorageLocationsFindsAllLocationTypes(
    tmp_path: Path, organizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    """movie<n>, myPictures, video<n>/TV, and myVideo/TV are all detected."""
    mnt = tmp_path / "mnt"
    (mnt / "movie1").mkdir(parents=True)
    (mnt / "myPictures").mkdir(parents=True)
    (mnt / "video1" / "TV").mkdir(parents=True)
    (mnt / "myVideo" / "TV").mkdir(parents=True)
    with patch("organiseMyVideo.video.Path") as mockPath:
        mockPath.return_value = mnt
        with caplog.at_level("INFO"):
            movieDirs, videoDirs = organizer.scanStorageLocations()
    assert len(movieDirs) == 2
    assert len(videoDirs) == 2
    assert "movie storage location found" in caplog.text
    assert "TV storage location found" in caplog.text


# ---------------------------------------------------------------------------
# findExistingMovieDir
# ---------------------------------------------------------------------------


def testFindExistingMovieDirFound(tmp_path: Path, organizer: VideoOrganizer):
    movieRoot = tmp_path / "movie1"
    (movieRoot / "Inception (2010)").mkdir(parents=True)
    result = organizer.findExistingMovieDir("Inception", "2010", [movieRoot])
    assert result is not None
    assert result.name == "Inception (2010)"


def testFindExistingMovieDirCaseInsensitive(tmp_path: Path, organizer: VideoOrganizer):
    movieRoot = tmp_path / "movie1"
    (movieRoot / "inception (2010)").mkdir(parents=True)
    result = organizer.findExistingMovieDir("Inception", "2010", [movieRoot])
    assert result is not None


def testFindExistingMovieDirNotFound(tmp_path: Path, organizer: VideoOrganizer):
    movieRoot = tmp_path / "movie1"
    movieRoot.mkdir()
    result = organizer.findExistingMovieDir("Inception", "2010", [movieRoot])
    assert result is None


# ---------------------------------------------------------------------------
# findExistingTvShowDir
# ---------------------------------------------------------------------------


def testFindExistingTvShowDirFound(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    (tvRoot / "Breaking Bad").mkdir(parents=True)
    result = organizer.findExistingTvShowDir("Breaking Bad", [tvRoot])
    assert result is not None
    assert result.name == "Breaking Bad"


def testFindExistingTvShowDirCaseInsensitive(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    (tvRoot / "breaking bad").mkdir(parents=True)
    result = organizer.findExistingTvShowDir("Breaking Bad", [tvRoot])
    assert result is not None


def testFindExistingTvShowDirMatchesTrailingTheFolderName(
    tmp_path: Path, organizer: VideoOrganizer
):
    tvRoot = tmp_path / "TV"
    (tvRoot / "Office, The").mkdir(parents=True)
    result = organizer.findExistingTvShowDir("The Office", [tvRoot])
    assert result is not None
    assert result.name == "Office, The"


def testFindExistingTvShowDirPrefersTrailingTheFolderNameWhenBothExist(
    tmp_path: Path, organizer: VideoOrganizer
):
    tvRoot = tmp_path / "TV"
    (tvRoot / "The Office").mkdir(parents=True)
    (tvRoot / "Office, The").mkdir(parents=True)
    result = organizer.findExistingTvShowDir("The Office", [tvRoot])
    assert result is not None
    assert result.name == "Office, The"


def testFindExistingTvShowDirNotFound(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    result = organizer.findExistingTvShowDir("Breaking Bad", [tvRoot])
    assert result is None


# ---------------------------------------------------------------------------
# findBestMatchingTvShow
# ---------------------------------------------------------------------------


def testFindBestMatchingTvShowExactMatch(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Breaking Bad").mkdir()
    result = organizer.findBestMatchingTvShow("Breaking Bad", [tvRoot])
    assert result == "Breaking Bad"


def testFindBestMatchingTvShowMatchesTrailingTheFolderName(
    tmp_path: Path, organizer: VideoOrganizer
):
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Office, The").mkdir()
    result = organizer.findBestMatchingTvShow("The Office", [tvRoot])
    assert result == "Office, The"


def testFindBestMatchingTvShowFuzzyMatchReturnsFolder(
    tmp_path: Path, organizer: VideoOrganizer
):
    """Folder name is returned even when the parsed show name differs slightly."""
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Law and Order Special Victims Unit").mkdir()
    # Simulates a parsed show name that omits the trailing word
    result = organizer.findBestMatchingTvShow(
        "Law and Order Special Victims Unit", [tvRoot]
    )
    assert result == "Law and Order Special Victims Unit"


def testFindBestMatchingTvShowCaseInsensitive(
    tmp_path: Path, organizer: VideoOrganizer
):
    """Fuzzy matching is case-insensitive enough to match mixed-case folder names."""
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Breaking Bad").mkdir()
    result = organizer.findBestMatchingTvShow("breaking bad", [tvRoot])
    assert result == "Breaking Bad"


def testFindBestMatchingTvShowNoMatch(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Breaking Bad").mkdir()
    result = organizer.findBestMatchingTvShow("Completely Different Show", [tvRoot])
    assert result is None


def testFindBestMatchingTvShowEmptyDirs(organizer: VideoOrganizer):
    result = organizer.findBestMatchingTvShow("Breaking Bad", [])
    assert result is None


# ---------------------------------------------------------------------------
# _isSampleLikeFolder
# ---------------------------------------------------------------------------


def testIsSampleLikeFolderLowercase(organizer: VideoOrganizer):
    assert organizer._isSampleLikeFolder(Path("sample")) is True


def testIsSampleLikeFolderMixedCase(organizer: VideoOrganizer):
    assert organizer._isSampleLikeFolder(Path("Sample")) is True


def testIsSampleLikeFolderContainsSample(organizer: VideoOrganizer):
    assert organizer._isSampleLikeFolder(Path("sample-video")) is True


def testIsSampleLikeFolderRegular(organizer: VideoOrganizer):
    assert organizer._isSampleLikeFolder(Path("Season 01")) is False


# ---------------------------------------------------------------------------
# _hasRealVideoContent
# ---------------------------------------------------------------------------


def testHasRealVideoContentWithRealFile(tmp_path: Path, organizer: VideoOrganizer):
    movieDir = tmp_path / "MovieA"
    movieDir.mkdir()
    (movieDir / "MovieA.mkv").write_bytes(b"x" * 100)
    assert organizer._hasRealVideoContent(movieDir) is True


def testHasRealVideoContentEmptyDir(tmp_path: Path, organizer: VideoOrganizer):
    emptyDir = tmp_path / "Empty"
    emptyDir.mkdir()
    assert organizer._hasRealVideoContent(emptyDir) is False


def testHasRealVideoContentSampleOnly(tmp_path: Path, organizer: VideoOrganizer):
    movieDir = tmp_path / "MovieB"
    sampleSubDir = movieDir / "Sample"
    sampleSubDir.mkdir(parents=True)
    (sampleSubDir / "sample.mkv").write_bytes(b"x" * 50)
    assert organizer._hasRealVideoContent(movieDir) is False


def testHasRealVideoContentRealAndSample(tmp_path: Path, organizer: VideoOrganizer):
    movieDir = tmp_path / "MovieC"
    sampleSubDir = movieDir / "Sample"
    sampleSubDir.mkdir(parents=True)
    (sampleSubDir / "sample.mkv").write_bytes(b"x" * 50)
    (movieDir / "MovieC.mkv").write_bytes(b"x" * 200)
    assert organizer._hasRealVideoContent(movieDir) is True


def testHasRealVideoContentNonVideoFilesOnly(tmp_path: Path, organizer: VideoOrganizer):
    movieDir = tmp_path / "MovieD"
    movieDir.mkdir()
    (movieDir / "readme.txt").write_text("notes")
    assert organizer._hasRealVideoContent(movieDir) is False


# ---------------------------------------------------------------------------
# cleanEmptyFolders — dry-run
# ---------------------------------------------------------------------------


def testCleanEmptyFoldersDryRunDoesNotRemove(
    sourceDir: Path, organizer: VideoOrganizer
):
    emptyDir = sourceDir / "EmptyDir"
    emptyDir.mkdir()
    stats = organizer.cleanEmptyFolders()
    assert emptyDir.exists(), "dry-run must not remove the folder"
    assert stats["removed"] == 1
    assert stats["errors"] == 0


def testCleanEmptyFoldersDryRunKeepsRealContent(
    sourceDir: Path, organizer: VideoOrganizer
):
    realDir = sourceDir / "MovieA"
    realDir.mkdir()
    (realDir / "MovieA.mkv").write_bytes(b"x" * 100)
    stats = organizer.cleanEmptyFolders()
    assert realDir.exists()
    assert stats["skipped"] == 1
    assert stats["removed"] == 0


def testCleanEmptyFoldersDryRunSampleOnlyCountedAsRemoved(
    sourceDir: Path, organizer: VideoOrganizer
):
    sampleDir = sourceDir / "MovieB"
    (sampleDir / "Sample").mkdir(parents=True)
    (sampleDir / "Sample" / "sample.mkv").write_bytes(b"x" * 50)
    stats = organizer.cleanEmptyFolders()
    assert sampleDir.exists(), "dry-run must not remove sample-only folder"
    assert stats["removed"] == 1


# ---------------------------------------------------------------------------
# cleanEmptyFolders — confirm mode (actual removal)
# ---------------------------------------------------------------------------


def testCleanEmptyFoldersRemovesEmptyDir(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    emptyDir = sourceDir / "EmptyDir"
    emptyDir.mkdir()
    stats = confirmedOrganizer.cleanEmptyFolders()
    assert not emptyDir.exists()
    assert stats["removed"] == 1


def testCleanEmptyFoldersRemovesSampleOnlyDir(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    sampleDir = sourceDir / "MovieB"
    (sampleDir / "Sample").mkdir(parents=True)
    (sampleDir / "Sample" / "sample.mkv").write_bytes(b"x" * 50)
    stats = confirmedOrganizer.cleanEmptyFolders()
    assert not sampleDir.exists()
    assert stats["removed"] == 1


def testCleanEmptyFoldersKeepsRealContentDir(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    realDir = sourceDir / "MovieA"
    realDir.mkdir()
    (realDir / "MovieA.mkv").write_bytes(b"x" * 100)
    confirmedOrganizer.cleanEmptyFolders()
    assert realDir.exists()


def testCleanEmptyFoldersMissingSrcReturnsZeroStats(tmp_path: Path):
    org = VideoOrganizer(sourceDir=str(tmp_path / "nonexistent"), dryRun=False)
    stats = org.cleanEmptyFolders()
    assert stats == {"removed": 0, "skipped": 0, "errors": 0}


def testCleanEmptyFoldersMixedDirs(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    realDir = sourceDir / "MovieA"
    realDir.mkdir()
    (realDir / "MovieA.mkv").write_bytes(b"x" * 100)

    emptyDir = sourceDir / "EmptyDir"
    emptyDir.mkdir()

    sampleDir = sourceDir / "MovieB"
    (sampleDir / "Sample").mkdir(parents=True)
    (sampleDir / "Sample" / "sample.mkv").write_bytes(b"x" * 50)

    stats = confirmedOrganizer.cleanEmptyFolders()
    assert stats["removed"] == 2
    assert stats["skipped"] == 2  # MovieA + MovieB/Sample (has direct video content)
    assert stats["errors"] == 0
    assert realDir.exists()
    assert not emptyDir.exists()
    assert not sampleDir.exists()


def testCleanEmptyFoldersRemovesNestedEmptyDir(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    """An empty subdirectory nested inside a real-content dir is removed."""
    realDir = sourceDir / "MovieA"
    realDir.mkdir()
    (realDir / "MovieA.mkv").write_bytes(b"x" * 100)
    nestedEmpty = realDir / "Extras"
    nestedEmpty.mkdir()
    stats = confirmedOrganizer.cleanEmptyFolders()
    assert realDir.exists()
    assert not nestedEmpty.exists()
    assert stats["removed"] == 1


# ---------------------------------------------------------------------------
# processFiles — video files in subdirectories
# ---------------------------------------------------------------------------


def testProcessFilesFindsVideoInSubdirectory(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    """Files inside a subdirectory of sourceDir are found and moved."""
    subDir = confirmedOrganizer.sourceDir / "One Mile (2026)"
    subDir.mkdir(parents=True)
    srcFile = subDir / "One.Mile.2026.1080p.WEBRip.x264.mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tmp_path / "TV"]),
    ):
        with patch.object(
            confirmedOrganizer,
            "promptUserConfirmation",
            return_value={"name": "One Mile (2026)", "type": "movie"},
        ):
            confirmedOrganizer.processFiles(interactive=True)

    destFile = movieStorage / "One Mile (2026)" / "One Mile (2026).mp4"
    assert destFile.exists()
    assert not srcFile.exists()


def testProcessFilesIgnoresFeaturettesSubdirectory(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    """Featurettes files are skipped during local source scanning."""
    normalFile = confirmedOrganizer.sourceDir / "One.Mile.2026.mp4"
    normalFile.write_bytes(b"x" * 100)
    featurettesDir = confirmedOrganizer.sourceDir / "Featurettes"
    featurettesDir.mkdir()
    ignoredFile = featurettesDir / "Bonus.Feature.2026.mp4"
    ignoredFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "TV"
    tvStorage.mkdir()

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        with patch.object(confirmedOrganizer, "_prepareMetadataLibrary"):
            with patch.object(
                confirmedOrganizer,
                "_classifyVideoFile",
                return_value=(
                    None,
                    {"title": "One Mile", "year": "2026", "extension": ".mp4"},
                ),
            ):
                with patch.object(
                    confirmedOrganizer, "moveMovie", return_value=True
                ) as mockMoveMovie:
                    confirmedOrganizer.processFiles(interactive=False)

    assert [call.args[0] for call in mockMoveMovie.call_args_list] == [normalFile]
    assert ignoredFile.exists()


def testProcessFilesRenamesExtrasFolderToFeaturettes(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    """Extras folders are normalised to Featurettes before scanning source files."""
    extrasDir = confirmedOrganizer.sourceDir / "Extras"
    extrasDir.mkdir()
    extraFile = extrasDir / "Bonus.Feature.2026.mp4"
    extraFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "TV"
    tvStorage.mkdir()

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        with patch.object(confirmedOrganizer, "_prepareMetadataLibrary"):
            with patch.object(
                confirmedOrganizer, "moveMovie", return_value=True
            ) as mockMoveMovie:
                confirmedOrganizer.processFiles(interactive=False)

    featurettesDir = confirmedOrganizer.sourceDir / "Featurettes"
    assert not extrasDir.exists()
    assert featurettesDir.exists()
    assert (featurettesDir / "Bonus.Feature.2026.mp4").exists()
    mockMoveMovie.assert_not_called()


def testProcessFilesUsesMovieMcmHintsWhenFilenameCannotBeParsed(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieSourceDir = confirmedOrganizer.sourceDir / "3 from Hell (2019)"
    movieSourceDir.mkdir()
    srcFile = movieSourceDir / "clip.mp4"
    srcFile.write_bytes(b"x" * 100)
    (movieSourceDir / "movie.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Title>
    <LocalTitle>3 from Hell</LocalTitle>
    <ProductionYear>2019</ProductionYear>
</Title>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        confirmedOrganizer.processFiles(interactive=False)

    destFile = movieStorage / "3 from Hell (2019)" / "3 from Hell (2019).mp4"
    assert destFile.exists()
    assert not srcFile.exists()


def testProcessFilesLogsSeparatorBeforeProcessingMessage(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer, "scanStorageLocations", return_value=([], [tvStorage])
    ):
        with caplog.at_level("INFO"):
            confirmedOrganizer.processFiles(interactive=False)

    messages = [record.getMessage() for record in caplog.records]
    separatorIndex = next(
        (
            i
            for i, message in enumerate(messages)
            if message.endswith(_FILE_PROCESS_SEPARATOR)
        ),
        None,
    )
    processingIndex = next(
        (i for i, message in enumerate(messages) if "processing TV show:" in message),
        None,
    )
    assert separatorIndex is not None, f"missing separator log in: {messages}"
    assert processingIndex is not None, f"missing processing log in: {messages}"
    assert separatorIndex < processingIndex


def testProcessFilesPrefersMovieMcmHintsBeforeFilenameClassification(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieSourceDir = confirmedOrganizer.sourceDir / "3 from Hell (2019)"
    movieSourceDir.mkdir()
    srcFile = movieSourceDir / "clip.mp4"
    srcFile.write_bytes(b"x" * 100)
    (movieSourceDir / "movie.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Title>
    <LocalTitle>3 from Hell</LocalTitle>
    <ProductionYear>2019</ProductionYear>
</Title>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    mcmHints = confirmedOrganizer._readMcmHints(srcFile)
    with patch.object(confirmedOrganizer, "parseTvFilename") as mockParseTvFilename:
        tvInfo, movieInfo = confirmedOrganizer._classifyVideoFile(srcFile, mcmHints)
        assert tvInfo is None
        assert movieInfo is not None
        assert movieInfo["title"] == "3 from Hell"
        assert movieInfo["year"] == "2019"
        assert movieInfo["type"] == "movie"
        mockParseTvFilename.assert_not_called()


def testProcessFilesUsesTvMcmHintsWhenFilenameCannotBeParsed(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showDir = confirmedOrganizer.sourceDir / "After Life"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    srcFile = seasonDir / "episode.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>After Life</SeriesName>
    <SeriesID>347507</SeriesID>
</Series>
""",
        encoding="utf-8",
    )
    (metadataDir / "episode.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>10751471</EpisodeID>
    <EpisodeNumber>4</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeName>Sic Semper Systema</EpisodeName>
</Item>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        confirmedOrganizer.processFiles(interactive=False)

    destFile = (
        tvStorage
        / "After Life"
        / "Season 01"
        / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()


def testProcessFilesPrefersTvMcmShowNameOverFilenameMismatch(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showDir = confirmedOrganizer.sourceDir / "Breaking Bad"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    srcFile = seasonDir / "Braking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Breaking Bad</SeriesName>
    <SeriesID>81189</SeriesID>
</Series>
""",
        encoding="utf-8",
    )
    (metadataDir / "Braking.Bad.S01E01.Pilot.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>3492321</EpisodeID>
    <EpisodeNumber>1</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeName>Pilot</EpisodeName>
</Item>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        confirmedOrganizer.processFiles(interactive=False)

    destFile = (
        tvStorage / "Breaking Bad" / "Season 01" / "Breaking.Bad.S01E01.Pilot.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()


def testProcessFilesUsesSeriesMcmHintsForNewEpisodeWithoutEpisodeXml(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showDir = confirmedOrganizer.sourceDir / "Virgin River"
    seasonDir = showDir / "Season 6"
    seasonDir.mkdir(parents=True)
    srcFile = seasonDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Virgin River</SeriesName>
    <SeriesID>117581</SeriesID>
</Series>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        confirmedOrganizer.processFiles(interactive=False)

    destSeasonDir = tvStorage / "Virgin River" / "Season 06"
    destFile = destSeasonDir / "Virgin.River.S06E01.mkv"
    episodeXml = destSeasonDir / "metadata" / "Virgin.River.S06E01.xml"
    assert destFile.exists()
    assert not srcFile.exists()
    assert episodeXml.exists()
    xmlText = episodeXml.read_text(encoding="utf-8")
    assert "<EpisodeNumber>1</EpisodeNumber>" in xmlText
    assert "<SeasonNumber>6</SeasonNumber>" in xmlText
    assert "<seriesid>117581</seriesid>" in xmlText


def testProcessFilesUsesMetadataLibraryToRenameLaterScan(tmp_path: Path):
    libraryPath = tmp_path / "metadataLibrary.json"

    firstSource = tmp_path / "source1"
    firstSource.mkdir()
    firstOrganizer = VideoOrganizer(sourceDir=str(firstSource), dryRun=False)
    showDir = firstOrganizer.sourceDir / "After Life"
    seasonDir = showDir / "Season 1"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    firstFile = seasonDir / "episode.mkv"
    firstFile.write_bytes(b"x" * 100)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>After Life</SeriesName>
    <SeriesID>347507</SeriesID>
</Series>
""",
        encoding="utf-8",
    )
    (metadataDir / "episode.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>10751471</EpisodeID>
    <EpisodeNumber>4</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeName>Sic Semper Systema</EpisodeName>
</Item>
""",
        encoding="utf-8",
    )

    secondSource = tmp_path / "source2"
    secondSource.mkdir()
    secondOrganizer = VideoOrganizer(sourceDir=str(secondSource), dryRun=False)
    secondFile = secondOrganizer.sourceDir / "After.Life.S01E04.mkv"
    secondFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        firstOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            firstOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            firstOrganizer.processFiles(interactive=False)
    assert libraryPath.exists()
    firstLibrary = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert (
        firstLibrary["tv"]["episodes"]["series:347507:s01e04"]["episodeTitle"]
        == "Sic Semper Systema"
    )

    with patch.object(
        secondOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            secondOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(
                secondOrganizer, "_fetchTvMetadataFromScraper"
            ) as mockFetch:
                secondOrganizer.processFiles(interactive=False)

    destFile = (
        tvStorage
        / "After Life"
        / "Season 01"
        / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    )
    assert destFile.exists()
    assert not secondFile.exists()
    mockFetch.assert_not_called()


def testProcessFilesScrapesMissingEpisodeTitleAndWritesItBack(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    libraryPath = tmp_path / "metadataLibrary.json"
    showDir = confirmedOrganizer.sourceDir / "Virgin River"
    seasonDir = showDir / "Season 6"
    seasonDir.mkdir(parents=True)
    srcFile = seasonDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Virgin River</SeriesName>
    <SeriesID>117581</SeriesID>
</Series>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    scraped = {
        "type": "tv",
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "episodeTitle": "The Beginning",
        "seriesId": "117581",
        "episodeId": "9999",
        "metadataSource": "tvdb",
    }

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(
                confirmedOrganizer, "_fetchTvMetadataFromScraper", return_value=scraped
            ) as mockFetch:
                confirmedOrganizer.processFiles(interactive=False)

    destSeasonDir = tvStorage / "Virgin River" / "Season 06"
    destFile = destSeasonDir / "Virgin.River.S06E01.The.Beginning.mkv"
    episodeXml = destSeasonDir / "metadata" / "Virgin.River.S06E01.The.Beginning.xml"
    assert destFile.exists()
    assert not srcFile.exists()
    assert episodeXml.exists()
    assert "<EpisodeName>The Beginning</EpisodeName>" in episodeXml.read_text(
        encoding="utf-8"
    )
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert "series:117581:s06e01" in library["tv"]["episodes"]
    assert (
        library["tv"]["episodes"]["series:117581:s06e01"]["episodeTitle"]
        == "The Beginning"
    )
    mockFetch.assert_called_once()


def testProcessFilesUsesLibraryCanonicalShowNameForPunctuationVariants(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    libraryPath = tmp_path / "metadataLibrary.json"
    libraryPath.write_text(
        json.dumps(
            {
                "version": 1,
                "movies": {},
                "tv": {
                    "series": {
                        "show:lawordersvu": {
                            "type": "tv",
                            "showName": "Law & Order: SVU",
                            "seriesId": "75692",
                            "imdbId": None,
                            "metadataSource": "mcm",
                            "metadataUpdatedAt": "2026-05-11T00:00:00+00:00",
                        }
                    },
                    "episodes": {
                        "show:lawordersvu:s03e02": {
                            "type": "tv",
                            "showName": "Law & Order: SVU",
                            "season": 3,
                            "episode": 2,
                            "episodeTitle": "Wrath",
                            "seriesId": "75692",
                            "episodeId": "102",
                            "metadataSource": "mcm",
                            "metadataUpdatedAt": "2026-05-11T00:00:00+00:00",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    srcFile = confirmedOrganizer.sourceDir / "Law.Order.SVU.S03E02.mkv"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(
                confirmedOrganizer, "_fetchTvMetadataFromScraper"
            ) as mockFetch:
                confirmedOrganizer.processFiles(interactive=False)

    destFile = (
        tvStorage / "Law & Order: SVU" / "Season 03" / "Law.Order.SVU.S03E02.Wrath.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()
    mockFetch.assert_not_called()


def testUpdateMetadataLibraryLogsShowAddition(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    libraryPath = tmp_path / "metadataLibrary.json"

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with caplog.at_level("INFO"):
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "tv",
                    "showName": "After Life",
                    "season": 1,
                    "episode": 4,
                    "episodeTitle": "Episode 4",
                    "seriesId": "347507",
                    "episodeId": "10751471",
                    "metadataSource": "mcm",
                }
            )

    assert "adding show to library" in caplog.text
    assert "... After Life" in caplog.text
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["tv"]["series"]["series:347507"]["showName"] == "After Life"


def testUpdateMetadataLibraryLogsShowNameOnlyOncePerSeries(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    libraryPath = tmp_path / "metadataLibrary.json"

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with caplog.at_level("INFO"):
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "tv",
                    "showName": "Breaking Bad",
                    "season": 1,
                    "episode": 1,
                    "episodeTitle": "Pilot",
                    "seriesId": "81189",
                    "episodeId": "3492321",
                    "metadataSource": "mcm",
                }
            )
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "tv",
                    "showName": "Breaking Bad",
                    "season": 1,
                    "episode": 2,
                    "episodeTitle": "Cat's in the Bag...",
                    "seriesId": "81189",
                    "episodeId": "3492322",
                    "metadataSource": "mcm",
                }
            )

    messages = [record.getMessage() for record in caplog.records]
    assert sum("adding show to library" in message for message in messages) == 1
    assert sum("... Breaking Bad" in message for message in messages) == 1
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["tv"]["series"]["series:81189"]["showName"] == "Breaking Bad"
    assert "series:81189:s01e02" in library["tv"]["episodes"]


def testUpdateMetadataLibraryIgnoresEpisodeOnlySeriesChurnInLogs(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    libraryPath = tmp_path / "metadataLibrary.json"

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with caplog.at_level("INFO"):
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "tv",
                    "showName": "Imposters",
                    "seriesId": "328634",
                    "metadataSource": "mcm",
                }
            )
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "tv",
                    "showName": "Imposters",
                    "season": 1,
                    "episode": 1,
                    "episodeTitle": "My So-Called Wife",
                    "seriesId": "328634",
                    "episodeId": "600001",
                    "imdbId": "tt5212822",
                    "metadataSource": "mcm",
                }
            )
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "tv",
                    "showName": "Imposters",
                    "season": 1,
                    "episode": 2,
                    "episodeTitle": "Three River Strokes",
                    "seriesId": "328634",
                    "episodeId": "600002",
                    "imdbId": "tt5786096",
                    "metadataSource": "mcm",
                }
            )

    messages = [record.getMessage() for record in caplog.records]
    assert sum("adding show to library" in message for message in messages) == 1
    assert sum("... Imposters" in message for message in messages) == 1
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["tv"]["series"]["series:328634"] == {
        "type": "tv",
        "showName": "Imposters",
        "seriesId": "328634",
        "imdbId": None,
        "metadataSource": "mcm",
        "metadataUpdatedAt": library["tv"]["series"]["series:328634"][
            "metadataUpdatedAt"
        ],
    }
    assert (
        library["tv"]["episodes"]["episode:600002"]["episodeTitle"]
        == "Three River Strokes"
    )


def testUpdateMetadataLibraryLogsMovieAddition(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    libraryPath = tmp_path / "metadataLibrary.json"

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with caplog.at_level("INFO"):
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "movie",
                    "title": "Inception",
                    "year": "2010",
                    "imdbId": "tt1375666",
                    "metadataSource": "mcm",
                }
            )

    assert "adding movie to library" in caplog.text
    assert "... Inception" in caplog.text
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["movies"]["title:inception:2010"]["title"] == "Inception"


def testUpdateMetadataLibraryLogsMovieHeaderOnlyOnce(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    libraryPath = tmp_path / "metadataLibrary.json"

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with caplog.at_level("INFO"):
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "movie",
                    "title": "Inception",
                    "year": "2010",
                    "imdbId": "tt1375666",
                    "metadataSource": "mcm",
                }
            )
            confirmedOrganizer._updateMetadataLibraryFromHints(
                {
                    "type": "movie",
                    "title": "Interstellar",
                    "year": "2014",
                    "imdbId": "tt0816692",
                    "metadataSource": "mcm",
                }
            )

    messages = [record.getMessage() for record in caplog.records]
    assert sum("adding movie to library" in message for message in messages) == 1
    assert sum("... Inception" in message for message in messages) == 1
    assert sum("... Interstellar" in message for message in messages) == 1
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["movies"]["title:inception:2010"]["title"] == "Inception"
    assert library["movies"]["title:interstellar:2014"]["title"] == "Interstellar"


def testProcessFilesBuildsMetadataLibraryFromStorageBeforeSourceProcessing(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    libraryPath = tmp_path / "metadataLibrary.json"
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    showDir = tvStorage / "After Life"
    metadataDir = showDir / "Season 01" / "metadata"
    metadataDir.mkdir(parents=True)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>After Life</SeriesName>
    <SeriesID>347507</SeriesID>
</Series>
""",
        encoding="utf-8",
    )
    (metadataDir / "After.Life.S01E04.Sic.Semper.Systema.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>10751471</EpisodeID>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeNumber>4</EpisodeNumber>
    <EpisodeName>Sic Semper Systema</EpisodeName>
</Item>
""",
        encoding="utf-8",
    )

    srcFile = confirmedOrganizer.sourceDir / "After.Life.S01E04.mkv"
    srcFile.write_bytes(b"x" * 100)

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(
                confirmedOrganizer, "_fetchTvMetadataFromScraper"
            ) as mockFetch:
                with caplog.at_level("INFO"):
                    confirmedOrganizer.processFiles(interactive=False)

    destFile = (
        tvStorage
        / "After Life"
        / "Season 01"
        / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()
    mockFetch.assert_not_called()
    assert "building metadata library from storage" in caplog.text
    assert "adding show to library" in caplog.text
    messages = [record.getMessage() for record in caplog.records]

    def _findLogMessageIndex(searchText: str) -> int | None:
        return next(
            (i for i, message in enumerate(messages) if searchText in message),
            None,
        )

    buildIndex = _findLogMessageIndex("building metadata library from storage")
    processIndex = _findLogMessageIndex("found 1 video file(s) to process")
    assert (
        buildIndex is not None
    ), f'Expected "building metadata library from storage" in logs: {messages}'
    assert (
        processIndex is not None
    ), f'Expected "found 1 video file(s) to process" in logs: {messages}'
    assert buildIndex < processIndex

    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["tv"]["series"]["series:347507"]["showName"] == "After Life"
    assert (
        library["tv"]["episodes"]["series:347507:s01e04"]["episodeTitle"]
        == "Sic Semper Systema"
    )


def testUpdateMetadataLibraryPersistsEvenInDryRun(
    tmp_path: Path, organizer: VideoOrganizer
):
    libraryPath = tmp_path / "metadataLibrary.json"

    with patch.object(organizer, "_getMetadataLibraryPath", return_value=libraryPath):
        organizer._updateMetadataLibraryFromHints(
            {
                "type": "tv",
                "showName": "After Life",
                "season": 1,
                "episode": 4,
                "episodeTitle": "Sic Semper Systema",
                "seriesId": "347507",
                "episodeId": "10751471",
                "metadataSource": "mcm",
            }
        )

    assert libraryPath.exists()
    library = json.loads(libraryPath.read_text(encoding="utf-8"))
    assert library["tv"]["episodes"]["series:347507:s01e04"]["episodeTitle"] == (
        "Sic Semper Systema"
    )


def testProcessFilesUsesSavedMetadataLibraryWithoutStorageRescan(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    libraryPath = tmp_path / "metadataLibrary.json"
    libraryPath.write_text(
        json.dumps(_savedAfterLifeMetadataLibrary()),
        encoding="utf-8",
    )

    srcFile = confirmedOrganizer.sourceDir / "After.Life.S01E04.mkv"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(
                confirmedOrganizer, "_buildMetadataLibraryFromStorage"
            ) as mockBuild:
                with patch.object(
                    confirmedOrganizer, "_fetchTvMetadataFromScraper"
                ) as mockFetch:
                    with caplog.at_level("INFO"):
                        confirmedOrganizer.processFiles(interactive=False)

    destFile = (
        tvStorage
        / "After Life"
        / "Season 01"
        / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()
    mockBuild.assert_not_called()
    mockFetch.assert_not_called()
    assert "using saved metadata library" in caplog.text


def testProcessFilesRefreshMetadataLibraryRebuildsStorageCache(tmp_path: Path):
    sourceDir = tmp_path / "source"
    sourceDir.mkdir()
    organizer = VideoOrganizer(
        sourceDir=str(sourceDir),
        dryRun=True,
        refreshMetadataLibrary=True,
    )
    libraryPath = tmp_path / "metadataLibrary.json"
    libraryPath.write_text(
        json.dumps({"version": 1, "movies": {}, "tv": {}}), encoding="utf-8"
    )
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(organizer, "_getMetadataLibraryPath", return_value=libraryPath):
        with patch.object(
            organizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(
                organizer, "_buildMetadataLibraryFromStorage"
            ) as mockBuild:
                organizer.processFiles(interactive=False)

    mockBuild.assert_called_once_with([movieStorage], [tvStorage])


def testProcessFilesKeepsSourceNameWhenScraperCannotFillEpisodeTitle(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showDir = confirmedOrganizer.sourceDir / "Virgin River"
    seasonDir = showDir / "Season 6"
    seasonDir.mkdir(parents=True)
    srcFile = seasonDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Virgin River</SeriesName>
    <SeriesID>117581</SeriesID>
</Series>
""",
        encoding="utf-8",
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        with patch.object(
            confirmedOrganizer, "_fetchTvMetadataFromScraper", return_value=None
        ):
            confirmedOrganizer.processFiles(interactive=False)

    destFile = tvStorage / "Virgin River" / "Season 06" / "Virgin.River.S06E01.mkv"
    assert destFile.exists()
    assert not srcFile.exists()


def testProcessFilesDoesNotRefetchTvMetadataAfterClassification(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "The.Pitt.S02E05.1080p.WEB.h264-ETHEL.mkv"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([movieStorage], [tvStorage]),
    ):
        with patch.object(
            confirmedOrganizer, "_fetchTvMetadataFromScraper", return_value=None
        ) as mockFetch:
            confirmedOrganizer.processFiles(interactive=False)

    assert mockFetch.call_count == 1
    destFile = tvStorage / "Pitt, The" / "Season 02" / "The.Pitt.S02E05.mkv"
    assert destFile.exists()
    assert not srcFile.exists()


def testFetchTvMetadataFromProvidersUsesTvdbBeforeImdb(organizer: VideoOrganizer):
    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1, "type": "tv"}
    tvdbRecord = {"type": "tv", "episodeTitle": "Pilot", "metadataSource": "tvdb"}
    imdbRecord = {"type": "tv", "episodeTitle": "Pilot", "metadataSource": "imdb"}

    with patch.object(organizer, "_fetchTvdbMetadata", return_value=tvdbRecord) as tvdb:
        with patch.object(
            organizer, "_fetchImdbMetadata", return_value=imdbRecord
        ) as imdb:
            result = organizer._fetchTvMetadataFromProviders(tvInfo)

    assert result == tvdbRecord
    tvdb.assert_called_once_with(tvInfo)
    imdb.assert_not_called()


def testFetchTvMetadataFromProvidersFallsBackToImdb(organizer: VideoOrganizer):
    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 2, "type": "tv"}
    imdbRecord = {
        "type": "tv",
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 2,
        "episodeTitle": "Cat's in the Bag...",
        "metadataSource": "imdb",
    }

    with patch.object(organizer, "_fetchTvdbMetadata", return_value=None) as tvdb:
        with patch.object(
            organizer, "_fetchImdbMetadata", return_value=imdbRecord
        ) as imdb:
            result = organizer._fetchTvMetadataFromProviders(tvInfo)

    assert result == imdbRecord
    tvdb.assert_called_once_with(tvInfo)
    imdb.assert_called_once_with(tvInfo)


def testFetchTvMetadataFromProvidersReturnsNoneWhenAllProvidersMiss(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "Unknown Show", "season": 1, "episode": 1, "type": "tv"}

    with patch.object(organizer, "_fetchTvdbMetadata", return_value=None) as tvdb:
        with patch.object(organizer, "_fetchImdbMetadata", return_value=None) as imdb:
            result = organizer._fetchTvMetadataFromProviders(tvInfo)

    assert result is None
    tvdb.assert_called_once_with(tvInfo)
    imdb.assert_called_once_with(tvInfo)


def testEnrichTvMetadataCallsScraperInDryRun(organizer: VideoOrganizer):
    """Dry-run TV enrichment still fetches episode metadata for previews."""
    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1, "type": "tv"}
    scraped = {
        "type": "tv",
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "episodeTitle": "Pilot",
        "seriesId": "81189",
        "episodeId": "349232",
        "metadataSource": "tvdb",
    }
    emptyLibrary = organizer._newMetadataLibrary()
    with patch.object(organizer, "_loadMetadataLibrary", return_value=emptyLibrary):
        with patch.object(
            organizer, "_fetchTvMetadataFromScraper", return_value=scraped
        ) as mockScraper:
            with patch.object(organizer, "_saveMetadataLibrary") as mockSave:
                result = organizer._enrichTvMetadata(tvInfo)

    mockScraper.assert_called_once()
    mockSave.assert_called_once()
    assert result is not None
    assert result["episodeTitle"] == "Pilot"
    assert result["seriesId"] == "81189"
    assert emptyLibrary["tv"]["episodes"]


def testEnrichTvMetadataReplacesParsedEpisodeTitleWithScrapedMetadata(
    organizer: VideoOrganizer,
):
    """Scraped TV metadata should replace noisy filename-derived episode titles."""
    tvInfo = {
        "showName": "The Pitt",
        "season": 2,
        "episode": 5,
        "episodeTitle": "1080p WEB h264-ETHEL[EZTVx.to]",
        "type": "tv",
    }
    scraped = {
        "type": "tv",
        "showName": "The Pitt",
        "season": 2,
        "episode": 5,
        "episodeTitle": "A Better Episode Title",
        "seriesId": "12345",
        "episodeId": "67890",
        "metadataSource": "tvdb",
    }
    emptyLibrary = organizer._newMetadataLibrary()
    with patch.object(organizer, "_loadMetadataLibrary", return_value=emptyLibrary):
        with patch.object(
            organizer, "_fetchTvMetadataFromScraper", return_value=scraped
        ) as mockScraper:
            with patch.object(organizer, "_saveMetadataLibrary"):
                result = organizer._enrichTvMetadata(tvInfo)

    mockScraper.assert_called_once()
    assert result is not None
    assert result["episodeTitle"] == "A Better Episode Title"
    assert result["seriesId"] == "12345"
    assert result["metadataSource"] == "tvdb"


def testEnrichTvMetadataPrefersScrapedEpisodeTitleOverCleanParsedTitle(
    organizer: VideoOrganizer,
):
    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "episodeTitle": "Pilot",
        "type": "tv",
    }
    scraped = {
        "type": "tv",
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "episodeTitle": "Cat's in the Bag...",
        "metadataSource": "tvdb",
    }
    emptyLibrary = organizer._newMetadataLibrary()

    with patch.object(organizer, "_loadMetadataLibrary", return_value=emptyLibrary):
        with patch.object(
            organizer, "_fetchTvMetadataFromScraper", return_value=scraped
        ) as mockScraper:
            result = organizer._enrichTvMetadata(tvInfo)

    mockScraper.assert_called_once()
    assert result is not None
    assert result["episodeTitle"] == "Cat's in the Bag..."


def testEnrichTvMetadataKeepsFilenameEpisodeTitleWhenScraperHasNoTitle(
    organizer: VideoOrganizer,
):
    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "episodeTitle": "Pilot",
        "type": "tv",
    }
    emptyLibrary = organizer._newMetadataLibrary()

    with patch.object(organizer, "_loadMetadataLibrary", return_value=emptyLibrary):
        with patch.object(
            organizer, "_fetchTvMetadataFromScraper", return_value=None
        ) as mockScraper:
            result = organizer._enrichTvMetadata(tvInfo)

    mockScraper.assert_called_once()
    assert result is not None
    assert result["episodeTitle"] == "Pilot"


def testGetTvdbTokenPromptsForApiKeyWhenMissing(organizer: VideoOrganizer):
    organizer.tvdbApiKeyPrompt = MagicMock(return_value="prompted-key")

    with patch.dict("os.environ", {}, clear=True):
        with patch.object(
            organizer, "_requestJson", return_value={"data": {"token": "token-123"}}
        ) as mockRequest:
            token = organizer._getTvdbToken()

    assert token == "token-123"
    organizer.tvdbApiKeyPrompt.assert_called_once_with()
    mockRequest.assert_called_once_with(
        "https://api4.thetvdb.com/v4/login",
        method="POST",
        payload={"apikey": "prompted-key"},
        headers={},
    )


def testFetchTvdbMetadataUsesEpisodeListEndpointForSeriesLookup(
    organizer: VideoOrganizer,
):
    tvInfo = {
        "showName": "Virgin River",
        "seriesId": "117581",
        "season": 6,
        "episode": 1,
        "type": "tv",
    }
    payload = {
        "data": {
            "episodes": [
                {
                    "id": "9999",
                    "seriesId": "117581",
                    "seriesName": "Virgin River",
                    "seasonNumber": 6,
                    "number": 1,
                    "name": "The Beginning",
                }
            ]
        }
    }
    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(
            organizer, "_requestJson", return_value=payload
        ) as mockRequest:
            result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is not None
    assert result["episodeTitle"] == "The Beginning"
    assert result["seriesId"] == "117581"
    mockRequest.assert_called_once_with(
        "https://api4.thetvdb.com/v4/series/117581/episodes/default?page=0",
        headers={"Authorization": "Bearer token-123"},
    )


def testFetchTvdbMetadataUsesEpisodeListEndpointForSearchResults(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "The Office", "season": 1, "episode": 6, "type": "tv"}

    def requestJson(url, headers=None, **kwargs):
        if url == "https://api4.thetvdb.com/v4/search?query=The+Office&type=series":
            return {"data": [{"tvdb_id": "78565"}]}
        if url == "https://api4.thetvdb.com/v4/series/78565/episodes/default?page=0":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "456",
                            "seriesId": "78565",
                            "seriesName": "The Office",
                            "seasonNumber": 1,
                            "number": 6,
                            "name": "Hot Girl",
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(
            organizer, "_requestJson", side_effect=requestJson
        ) as mockRequest:
            result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is not None
    assert result["episodeTitle"] == "Hot Girl"
    assert result["seriesId"] == "78565"
    assert mockRequest.call_count == 2


def testFetchTvdbMetadataPrefersExactTvdbSearchMatchBeforeBroaderResults(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "The Pitt", "season": 1, "episode": 9, "type": "tv"}

    def requestJson(url, headers=None, **kwargs):
        if url == "https://api4.thetvdb.com/v4/search?query=The+Pitt&type=series":
            return {
                "data": [
                    {"tvdb_id": "111", "name": "The Pittsburgh Steelers Select"},
                    {"tvdb_id": "54321", "name": "The Pitt"},
                ]
            }
        if url == "https://api4.thetvdb.com/v4/series/54321/episodes/default?page=0":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "999",
                            "seriesId": "54321",
                            "seriesName": "The Pitt",
                            "seasonNumber": 1,
                            "number": 9,
                            "name": "3:00 P.M.",
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(
            organizer, "_requestJson", side_effect=requestJson
        ) as mockRequest:
            result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is not None
    assert result["episodeTitle"] == "3.00pm"
    assert result["seriesId"] == "54321"
    assert mockRequest.call_count == 2


def testFetchTvdbMetadataUsesEpisodeTitleWhenSeriesNameMissingFromEpisodeList(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "The Pitt", "season": 1, "episode": 9, "type": "tv"}

    def requestJson(url, headers=None, **kwargs):
        if url == "https://api4.thetvdb.com/v4/search?query=The+Pitt&type=series":
            return {"data": [{"tvdb_id": "54321"}]}
        if url == "https://api4.thetvdb.com/v4/series/54321/episodes/default?page=0":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "999",
                            "seriesId": "54321",
                            "seasonNumber": 1,
                            "number": 9,
                            "name": "3:00 P.M.",
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(
            organizer, "_requestJson", side_effect=requestJson
        ) as mockRequest:
            result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is not None
    assert result["showName"] is None
    assert result["episodeTitle"] == "3.00pm"
    assert result["seriesId"] == "54321"
    assert mockRequest.call_count == 2


def testFetchTvdbMetadataFindsThePittTitleViaPagedSearchFallback(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "The Pitt", "season": 2, "episode": 5, "type": "tv"}

    def requestJson(url, headers=None, **kwargs):
        if url == "https://api4.thetvdb.com/v4/search?query=The+Pitt&type=series":
            return {"data": [{"tvdb_id": "54321"}]}
        if url == "https://api4.thetvdb.com/v4/series/54321/episodes/default?page=0":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "111",
                            "seriesId": "54321",
                            "seriesName": "The Pitt",
                            "seasonNumber": 2,
                            "number": 4,
                            "name": "1:00 P.M.",
                        }
                    ]
                },
                "links": {"next": "?page=1"},
            }
        if url == "https://api4.thetvdb.com/v4/series/54321/episodes/default?page=1":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "222",
                            "seriesId": "54321",
                            "seriesName": "The Pitt",
                            "seasonNumber": 2,
                            "number": 5,
                            "name": "2:00 P.M.",
                        }
                    ]
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(
            organizer, "_requestJson", side_effect=requestJson
        ) as mockRequest:
            result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is not None
    assert result["episodeTitle"] == "2.00pm"
    assert result["seriesId"] == "54321"
    assert mockRequest.call_count == 3


def testFetchTvdbMetadataFetchesMatchedEpisodeByIdWhenListHasNoTitle(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "The Pitt", "season": 2, "episode": 5, "type": "tv"}

    def requestJson(url, headers=None, **kwargs):
        if url == "https://api4.thetvdb.com/v4/search?query=The+Pitt&type=series":
            return {"data": [{"tvdb_id": "54321"}]}
        if url == "https://api4.thetvdb.com/v4/series/54321/episodes/default?page=0":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "222",
                            "seriesId": "54321",
                            "seriesName": "The Pitt",
                            "seasonNumber": 2,
                            "number": 5,
                        }
                    ]
                }
            }
        if url == "https://api4.thetvdb.com/v4/episodes/222/extended":
            return {
                "data": {
                    "id": "222",
                    "seriesId": "54321",
                    "seriesName": "The Pitt",
                    "seasonNumber": 2,
                    "number": 5,
                    "name": "2:00 P.M.",
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(
            organizer, "_requestJson", side_effect=requestJson
        ) as mockRequest:
            result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is not None
    assert result["episodeTitle"] == "2.00pm"
    assert result["seriesId"] == "54321"
    assert mockRequest.call_count == 3


def testFetchTvdbMetadataLogsTvdbTitlePayloads(
    organizer: VideoOrganizer,
):
    tvInfo = {"showName": "The Pitt", "season": 1, "episode": 9, "type": "tv"}

    def requestJson(url, headers=None, **kwargs):
        if url == "https://api4.thetvdb.com/v4/search?query=The+Pitt&type=series":
            return {"data": [{"tvdb_id": "54321"}]}
        if url == "https://api4.thetvdb.com/v4/series/54321/episodes/default?page=0":
            return {
                "data": {
                    "episodes": [
                        {
                            "id": "999",
                            "seriesId": "54321",
                            "seriesName": "The Pitt",
                            "seasonNumber": 1,
                            "number": 9,
                        }
                    ]
                }
            }
        if url == "https://api4.thetvdb.com/v4/episodes/999/extended":
            return {
                "data": {
                    "id": "999",
                    "seriesId": "54321",
                    "seriesName": "The Pitt",
                    "seasonNumber": 1,
                    "number": 9,
                    "name": None,
                }
            }
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(organizer, "_getTvdbToken", return_value="token-123"):
        with patch.object(organizer, "_requestJson", side_effect=requestJson):
            with patch("organiseMyVideo.metadata.logger.debug") as mockDebug:
                result = organizer._fetchTvdbMetadata(tvInfo)

    assert result is None
    debugCalls = [call.args for call in mockDebug.call_args_list]
    assert (
        "TVDB title payload: show=%r season=%s episode=%s episodeId=%r rawTitle=%r resolvedTitle=%r",
        "The Pitt",
        1,
        9,
        "999",
        None,
        None,
    ) in debugCalls


def testPromptForTvdbApiKeyIfNeededReturnsNoneForBlankPrompt(
    organizer: VideoOrganizer,
):
    organizer.tvdbApiKeyPrompt = MagicMock(return_value="   ")

    with patch.dict("os.environ", {}, clear=True):
        result = organizer._promptForTvdbApiKeyIfNeeded()

    assert result is None
    organizer.tvdbApiKeyPrompt.assert_called_once_with()


def testPromptForTvdbApiKeyIfNeededReturnsNoneForNonStringPrompt(
    organizer: VideoOrganizer,
):
    organizer.tvdbApiKeyPrompt = MagicMock(return_value=123)

    with patch.dict("os.environ", {}, clear=True):
        result = organizer._promptForTvdbApiKeyIfNeeded()

    assert result is None
    organizer.tvdbApiKeyPrompt.assert_called_once_with()


def testPromptForTvdbApiKeyIfNeededUsesEnvValueSavedByPrompt(
    organizer: VideoOrganizer,
):
    def persistKey():
        os.environ["ORGANISEMYVIDEO_TVDB_API_KEY"] = "saved-by-prompt"
        return None

    organizer.tvdbApiKeyPrompt = MagicMock(side_effect=persistKey)

    with patch.dict("os.environ", {}, clear=True):
        result = organizer._promptForTvdbApiKeyIfNeeded()

    assert result == "saved-by-prompt"
    organizer.tvdbApiKeyPrompt.assert_called_once_with()


def testProcessFilesCachesImdbFallbackEpisodeTitleForLaterRuns(tmp_path: Path):
    libraryPath = tmp_path / "metadataLibrary.json"
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    firstSource = tmp_path / "source1"
    firstSource.mkdir()
    firstOrganizer = VideoOrganizer(sourceDir=str(firstSource), dryRun=False)
    firstShowDir = firstOrganizer.sourceDir / "Virgin River"
    firstSeasonDir = firstShowDir / "Season 6"
    firstSeasonDir.mkdir(parents=True)
    firstFile = firstSeasonDir / "Virgin.River.S06E01.mkv"
    firstFile.write_bytes(b"x" * 100)
    (firstShowDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Virgin River</SeriesName>
    <SeriesID>117581</SeriesID>
</Series>
""",
        encoding="utf-8",
    )

    imdbScraped = {
        "type": "tv",
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "episodeTitle": "The Beginning",
        "seriesId": "117581",
        "episodeId": "9999",
        "metadataSource": "imdb",
    }

    with patch.object(
        firstOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            firstOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(firstOrganizer, "_fetchTvdbMetadata", return_value=None):
                with patch.object(
                    firstOrganizer, "_fetchImdbMetadata", return_value=imdbScraped
                ):
                    firstOrganizer.processFiles(interactive=False)

    secondSource = tmp_path / "source2"
    secondSource.mkdir()
    secondOrganizer = VideoOrganizer(sourceDir=str(secondSource), dryRun=False)
    secondFile = secondOrganizer.sourceDir / "Virgin.River.S06E01.mkv"
    secondFile.write_bytes(b"x" * 100)

    with patch.object(
        secondOrganizer, "_getMetadataLibraryPath", return_value=libraryPath
    ):
        with patch.object(
            secondOrganizer,
            "scanStorageLocations",
            return_value=([movieStorage], [tvStorage]),
        ):
            with patch.object(secondOrganizer, "_fetchTvdbMetadata") as mockTvdb:
                with patch.object(secondOrganizer, "_fetchImdbMetadata") as mockImdb:
                    secondOrganizer.processFiles(interactive=False)

    cachedDest = (
        tvStorage
        / "Virgin River"
        / "Season 06"
        / "Virgin.River.S06E01.The.Beginning.mkv"
    )
    assert cachedDest.exists()
    assert not secondFile.exists()
    mockTvdb.assert_not_called()
    mockImdb.assert_not_called()


# ---------------------------------------------------------------------------
# moveMovie — dry-run
# ---------------------------------------------------------------------------


def testMoveMovieDryRunReturnsTrueWithoutMoving(
    tmp_path: Path, organizer: VideoOrganizer
):
    srcFile = organizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "extension": ".mp4",
        "type": "movie",
    }

    with patch.object(organizer, "_moveFileWithProgress") as mockMove:
        result = organizer.moveMovie(
            srcFile, movieInfo, [movieStorage], interactive=False
        )

    assert result is True
    mockMove.assert_not_called()
    assert srcFile.exists()


# ---------------------------------------------------------------------------
# moveMovie — confirm mode
# ---------------------------------------------------------------------------


def testMoveMovieConfirmMovesFile(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    destFile = movieStorage / "Inception (2010)" / "Inception (2010).mp4"
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveMovieReplicatesMcmCompanionFiles(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieSourceDir = confirmedOrganizer.sourceDir / "3 from Hell (2019)"
    movieSourceDir.mkdir()
    srcFile = movieSourceDir / "3 from Hell (2019).mp4"
    srcFile.write_bytes(b"x" * 100)
    (movieSourceDir / "folder.jpg").write_bytes(b"poster")
    (movieSourceDir / "backdrop.jpg").write_bytes(b"backdrop")
    (movieSourceDir / "backdrop2.jpg").write_bytes(b"backdrop2")
    (movieSourceDir / "movie.xml").write_text("<Title />", encoding="utf-8")
    (movieSourceDir / "mcm_id__tt8134742-489064.dvdid.xml").write_text(
        "<Disc />", encoding="utf-8"
    )

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "3 from Hell",
        "year": "2019",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    destDir = movieStorage / "3 from Hell (2019)"
    assert (destDir / "3 from Hell (2019).mp4").exists()
    assert (destDir / "folder.jpg").read_bytes() == b"poster"
    assert (destDir / "backdrop.jpg").read_bytes() == b"backdrop"
    assert (destDir / "backdrop2.jpg").read_bytes() == b"backdrop2"
    assert (destDir / "movie.xml").read_text(encoding="utf-8") == "<Title />"
    assert (destDir / "mcm_id__tt8134742-489064.dvdid.xml").read_text(
        encoding="utf-8"
    ) == "<Disc />"


def testMoveMoviePreservesExistingMcmCompanionFilesInDestination(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieSourceDir = confirmedOrganizer.sourceDir / "3 from Hell (2019)"
    movieSourceDir.mkdir()
    srcFile = movieSourceDir / "3 from Hell (2019).mp4"
    srcFile.write_bytes(b"x" * 100)
    (movieSourceDir / "folder.jpg").write_bytes(b"new-poster")

    movieStorage = tmp_path / "movie1"
    destDir = movieStorage / "3 from Hell (2019)"
    destDir.mkdir(parents=True)
    (destDir / "folder.jpg").write_bytes(b"existing-poster")

    movieInfo = {
        "title": "3 from Hell",
        "year": "2019",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    assert (destDir / "folder.jpg").read_bytes() == b"existing-poster"


def testMoveMovieUsesExistingDir(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    existingDir = movieStorage / "Inception (2010)"
    existingDir.mkdir(parents=True)

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    assert (existingDir / "Inception (2010).mp4").exists()


def testMoveMovieNoStorageReturnsFalse(organizer: VideoOrganizer):
    srcFile = organizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "extension": ".mp4",
        "type": "movie",
    }
    # Pass no storage dirs and disable dry-run so it reaches the "no storage" branch
    org = VideoOrganizer(sourceDir=str(organizer.sourceDir), dryRun=False)
    result = org.moveMovie(srcFile, movieInfo, [], interactive=False)
    assert result is False


# ---------------------------------------------------------------------------
# Movie MCM metadata generation — _ensureMovieMetadata / _ensureMovieDvdIdMetadata
# ---------------------------------------------------------------------------


def testMoveMovieCreatesMovieXmlWhenMissingAndMetadataConfident(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    destDir = movieStorage / "Inception (2010)"
    movieXml = destDir / "movie.xml"
    assert movieXml.exists()
    movieXmlText = movieXml.read_text(encoding="utf-8")
    assert "<LocalTitle>Inception</LocalTitle>" in movieXmlText
    assert "<ProductionYear>2010</ProductionYear>" in movieXmlText
    assert "<IMDbId>tt1375666</IMDbId>" in movieXmlText
    assert "<TMDbId>27205</TMDbId>" in movieXmlText


def testMoveMovieCreatesDvdIdXmlWhenMissingWithBothIds(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    destDir = movieStorage / "Inception (2010)"
    dvdIdXml = destDir / "mcm_id__tt1375666-27205.dvdid.xml"
    assert dvdIdXml.exists()
    dvdIdText = dvdIdXml.read_text(encoding="utf-8")
    assert "<IMDbId>tt1375666</IMDbId>" in dvdIdText
    assert "<TMDbId>27205</TMDbId>" in dvdIdText
    assert "<Type>movie</Type>" in dvdIdText


def testMoveMovieCreatesDvdIdXmlWithImdbOnlyWhenTmdbMissing(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    destDir = tmp_path / "Inception (2010)"
    destDir.mkdir()
    movieInfo = {"imdbId": "tt1375666", "tmdbId": None}
    confirmedOrganizer._ensureMovieDvdIdMetadata(destDir, movieInfo)
    dvdIdXml = destDir / "mcm_id__tt1375666.dvdid.xml"
    assert dvdIdXml.exists()


def testMoveMovieCreatesDvdIdXmlWithTmdbOnlyWhenImdbMissing(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    destDir = tmp_path / "Inception (2010)"
    destDir.mkdir()
    movieInfo = {"imdbId": None, "tmdbId": "27205"}
    confirmedOrganizer._ensureMovieDvdIdMetadata(destDir, movieInfo)
    dvdIdXml = destDir / "mcm_id__27205.dvdid.xml"
    assert dvdIdXml.exists()


def testMoveMovieSkipsDvdIdXmlWhenNoIds(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    destDir = tmp_path / "Inception (2010)"
    destDir.mkdir()
    movieInfo = {}
    confirmedOrganizer._ensureMovieDvdIdMetadata(destDir, movieInfo)
    dvdIdFiles = list(destDir.glob("mcm_id__*.dvdid.xml"))
    assert dvdIdFiles == []


def testMoveMoviePreservesExistingMovieXmlWithoutOverwriting(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieSourceDir = confirmedOrganizer.sourceDir / "Inception (2010)"
    movieSourceDir.mkdir()
    srcFile = movieSourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    destDir = movieStorage / "Inception (2010)"
    destDir.mkdir(parents=True)
    existingXml = "<Title><LocalTitle>Existing</LocalTitle></Title>"
    (destDir / "movie.xml").write_text(existingXml, encoding="utf-8")

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    assert (destDir / "movie.xml").read_text(encoding="utf-8") == existingXml


def testMoveMoviePreservesExistingDvdIdXmlWithoutCreatingDuplicate(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    destDir = movieStorage / "Inception (2010)"
    destDir.mkdir(parents=True)
    (destDir / "mcm_id__existing.dvdid.xml").write_text("<Item />", encoding="utf-8")

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "extension": ".mp4",
        "type": "movie",
    }
    result = confirmedOrganizer.moveMovie(
        srcFile, movieInfo, [movieStorage], interactive=False
    )

    assert result is True
    dvdIdFiles = list(destDir.glob("mcm_id__*.dvdid.xml"))
    assert len(dvdIdFiles) == 1
    assert dvdIdFiles[0].name == "mcm_id__existing.dvdid.xml"


def testMoveMovieDryRunDoesNotCreateMetadataFiles(
    tmp_path: Path, organizer: VideoOrganizer
):
    srcFile = organizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "extension": ".mp4",
        "type": "movie",
    }
    result = organizer.moveMovie(srcFile, movieInfo, [movieStorage], interactive=False)

    assert result is True
    destDir = movieStorage / "Inception (2010)"
    assert not (destDir / "movie.xml").exists()
    assert not list(destDir.glob("mcm_id__*.dvdid.xml"))


def testBuildMovieDvdIdFilenameWithBothIds(organizer: VideoOrganizer):
    movieInfo = {"imdbId": "tt1375666", "tmdbId": "27205"}
    assert (
        organizer._buildMovieDvdIdFilename(movieInfo)
        == "mcm_id__tt1375666-27205.dvdid.xml"
    )


def testBuildMovieDvdIdFilenameImdbOnly(organizer: VideoOrganizer):
    movieInfo = {"imdbId": "tt1375666"}
    assert (
        organizer._buildMovieDvdIdFilename(movieInfo) == "mcm_id__tt1375666.dvdid.xml"
    )


def testBuildMovieDvdIdFilenameTmdbOnly(organizer: VideoOrganizer):
    movieInfo = {"tmdbId": "27205"}
    assert organizer._buildMovieDvdIdFilename(movieInfo) == "mcm_id__27205.dvdid.xml"


def testBuildMovieDvdIdFilenameNoIds(organizer: VideoOrganizer):
    assert organizer._buildMovieDvdIdFilename({}) is None


# ---------------------------------------------------------------------------
# Movie metadata enrichment — _normaliseMovieMetadata / _enrichMovieMetadata
# ---------------------------------------------------------------------------


def testNormaliseMovieMetadataReturnsNoneForNone(organizer: VideoOrganizer):
    assert organizer._normaliseMovieMetadata(None) is None


def testNormaliseMovieMetadataSetsType(organizer: VideoOrganizer):
    result = organizer._normaliseMovieMetadata({"title": "Inception", "year": "2010"})
    assert result is not None
    assert result["type"] == "movie"


def testNormaliseMovieMetadataNormalisesEmptyStringsToNone(organizer: VideoOrganizer):
    result = organizer._normaliseMovieMetadata(
        {"title": "", "year": "", "imdbId": "", "tmdbId": ""}
    )
    assert result is not None
    assert result["title"] is None
    assert result["year"] is None
    assert result["imdbId"] is None
    assert result["tmdbId"] is None


def testEnrichMovieMetadataReturnsNoneForNone(organizer: VideoOrganizer):
    assert organizer._enrichMovieMetadata(None) is None


def testEnrichMovieMetadataSkipsScraperWhenBothIdsPresent(organizer: VideoOrganizer):
    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "type": "movie",
    }
    with patch.object(organizer, "_fetchMovieMetadataFromScraper") as mockScraper:
        result = organizer._enrichMovieMetadata(movieInfo)

    mockScraper.assert_not_called()
    assert result is not None
    assert result["imdbId"] == "tt1375666"
    assert result["tmdbId"] == "27205"


def testEnrichMovieMetadataCallsScraperInDryRun(organizer: VideoOrganizer):
    """Dry-run enrichment still fetches metadata so previews use enriched values."""
    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": None,
        "tmdbId": None,
        "type": "movie",
    }
    scraped = {
        "type": "movie",
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "metadataSource": "tmdb",
    }
    emptyLibrary = organizer._newMetadataLibrary()
    with patch.object(organizer, "_loadMetadataLibrary", return_value=emptyLibrary):
        with patch.object(
            organizer, "_fetchMovieMetadataFromScraper", return_value=scraped
        ) as mockScraper:
            with patch.object(organizer, "_saveMetadataLibrary") as mockSave:
                result = organizer._enrichMovieMetadata(movieInfo)

    mockScraper.assert_called_once()
    mockSave.assert_called_once()
    assert result is not None
    assert result["imdbId"] == "tt1375666"
    assert result["tmdbId"] == "27205"
    assert emptyLibrary["movies"]


def testEnrichMovieMetadataCallsScraperWhenIdsMissing(organizer: VideoOrganizer):
    """In confirm mode, enrichment fetches from scraper when IDs are missing."""
    organizer.dryRun = False
    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "type": "movie",
    }
    scraped = {
        "type": "movie",
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "metadataSource": "tmdb",
    }
    emptyLibrary = organizer._newMetadataLibrary()
    with patch.object(organizer, "_loadMetadataLibrary", return_value=emptyLibrary):
        with patch.object(
            organizer, "_fetchMovieMetadataFromScraper", return_value=scraped
        ) as mockScraper:
            with patch.object(organizer, "_saveMetadataLibrary"):
                result = organizer._enrichMovieMetadata(movieInfo)

    mockScraper.assert_called_once()
    assert result is not None
    assert result["imdbId"] == "tt1375666"
    assert result["tmdbId"] == "27205"


# ---------------------------------------------------------------------------
# TMDB movie metadata — _fetchTmdbMovieMetadata / _tmdbMovieRecord
# ---------------------------------------------------------------------------


def testFetchTmdbMovieMetadataReturnsNoneWhenNoApiKey(organizer: VideoOrganizer):
    with patch.dict("os.environ", {}, clear=True):
        result = organizer._fetchTmdbMovieMetadata(
            {"title": "Inception", "year": "2010"}
        )
    assert result is None


def testFetchTmdbMovieMetadataSearchesByTitle(organizer: VideoOrganizer):
    tmdbResponse = {
        "results": [
            {
                "id": 27205,
                "title": "Inception",
                "release_date": "2010-07-16",
                "poster_path": "/poster.jpg",
                "backdrop_path": "/backdrop.jpg",
            }
        ]
    }
    with patch.dict("os.environ", {"ORGANISEMYVIDEO_TMDB_API_KEY": "testkey"}):
        with patch.object(organizer, "_requestJson", return_value=tmdbResponse):
            result = organizer._fetchTmdbMovieMetadata(
                {"title": "Inception", "year": "2010"}
            )

    assert result is not None
    assert result["tmdbId"] == "27205"
    assert result["title"] == "Inception"
    assert result["year"] == "2010"
    assert result["posterPath"] == "/poster.jpg"
    assert result["backdropPath"] == "/backdrop.jpg"
    assert result["metadataSource"] == "tmdb"


def testFetchTmdbMovieMetadataFetchesById(organizer: VideoOrganizer):
    tmdbDetail = {
        "id": 27205,
        "title": "Inception",
        "release_date": "2010-07-16",
        "imdb_id": "tt1375666",
        "poster_path": "/poster.jpg",
        "backdrop_path": None,
    }
    with patch.dict("os.environ", {"ORGANISEMYVIDEO_TMDB_API_KEY": "testkey"}):
        with patch.object(organizer, "_requestJson", return_value=tmdbDetail):
            result = organizer._fetchTmdbMovieMetadata(
                {"title": "Inception", "tmdbId": "27205"}
            )

    assert result is not None
    assert result["tmdbId"] == "27205"
    assert result["imdbId"] == "tt1375666"
    assert result["posterPath"] == "/poster.jpg"
    assert result["backdropPath"] is None


def testTmdbMovieRecordReturnsNoneForNonDict(organizer: VideoOrganizer):
    assert organizer._tmdbMovieRecord(None) is None  # type: ignore[arg-type]
    assert organizer._tmdbMovieRecord("bad") is None  # type: ignore[arg-type]


def testTmdbMovieRecordReturnsNoneWhenNoTitle(organizer: VideoOrganizer):
    assert organizer._tmdbMovieRecord({"id": 123}) is None


def testTmdbMovieRecordParsesReleaseDate(organizer: VideoOrganizer):
    result = organizer._tmdbMovieRecord(
        {"id": 27205, "title": "Inception", "release_date": "2010-07-16"}
    )
    assert result is not None
    assert result["year"] == "2010"


# ---------------------------------------------------------------------------
# OMDb movie metadata — _fetchOmdbMovieMetadata
# ---------------------------------------------------------------------------


def testFetchOmdbMovieMetadataReturnsNoneWhenNoApiKey(organizer: VideoOrganizer):
    with patch.dict("os.environ", {}, clear=True):
        result = organizer._fetchOmdbMovieMetadata(
            {"title": "Inception", "year": "2010"}
        )
    assert result is None


def testFetchOmdbMovieMetadataSearchesByTitle(organizer: VideoOrganizer):
    omdbResponse = {
        "Response": "True",
        "Title": "Inception",
        "Year": "2010",
        "imdbID": "tt1375666",
        "Poster": "https://example.com/poster.jpg",
    }
    with patch.dict("os.environ", {"ORGANISEMYVIDEO_OMDB_API_KEY": "testkey"}):
        with patch.object(organizer, "_requestJson", return_value=omdbResponse):
            result = organizer._fetchOmdbMovieMetadata(
                {"title": "Inception", "year": "2010"}
            )

    assert result is not None
    assert result["imdbId"] == "tt1375666"
    assert result["title"] == "Inception"
    assert result["year"] == "2010"
    assert result["posterUrl"] == "https://example.com/poster.jpg"
    assert result["metadataSource"] == "omdb"


def testFetchOmdbMovieMetadataReturnsFalseResponse(organizer: VideoOrganizer):
    with patch.dict("os.environ", {"ORGANISEMYVIDEO_OMDB_API_KEY": "testkey"}):
        with patch.object(
            organizer, "_requestJson", return_value={"Response": "False"}
        ):
            result = organizer._fetchOmdbMovieMetadata({"title": "Unknown"})
    assert result is None


def testFetchOmdbMovieMetadataRequiresTitleOrImdb(organizer: VideoOrganizer):
    with patch.dict("os.environ", {"ORGANISEMYVIDEO_OMDB_API_KEY": "testkey"}):
        result = organizer._fetchOmdbMovieMetadata({})
    assert result is None


# ---------------------------------------------------------------------------
# Artwork download — _downloadArtworkFile / _fetchMovieArtwork
# ---------------------------------------------------------------------------


def testDownloadArtworkFilePreservesExistingFile(
    tmp_path: Path, organizer: VideoOrganizer
):
    dest = tmp_path / "folder.jpg"
    dest.write_bytes(b"existing")
    result = organizer._downloadArtworkFile("https://example.com/img.jpg", dest)
    assert result is True
    assert dest.read_bytes() == b"existing"


def testDownloadArtworkFileRejectsNonHttps(tmp_path: Path, organizer: VideoOrganizer):
    dest = tmp_path / "folder.jpg"
    result = organizer._downloadArtworkFile("http://example.com/img.jpg", dest)
    assert result is False
    assert not dest.exists()


def testDownloadArtworkFileDryRunReturnsTrueWithoutWriting(
    tmp_path: Path, organizer: VideoOrganizer
):
    dest = tmp_path / "folder.jpg"
    result = organizer._downloadArtworkFile("https://example.com/img.jpg", dest)
    assert result is True
    assert not dest.exists()


def testDownloadArtworkFileWritesBytes(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    dest = tmp_path / "folder.jpg"
    import urllib.request
    from unittest.mock import MagicMock

    fakeResponse = MagicMock()
    fakeResponse.__enter__ = lambda s: s
    fakeResponse.__exit__ = MagicMock(return_value=False)
    fakeResponse.headers = {"Content-Length": "5"}
    fakeResponse.read = MagicMock(return_value=b"imgdt")

    with patch("urllib.request.urlopen", return_value=fakeResponse):
        result = confirmedOrganizer._downloadArtworkFile(
            "https://example.com/poster.jpg", dest
        )
    assert result is True
    assert dest.read_bytes() == b"imgdt"


def testFetchMovieArtworkDownloadsPosterAndBackdrop(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieInfo = {
        "posterPath": "/poster.jpg",
        "backdropPath": "/backdrop.jpg",
    }
    with patch.object(
        confirmedOrganizer, "_downloadArtworkFile", return_value=True
    ) as mockDownload:
        confirmedOrganizer._fetchMovieArtwork(movieInfo, tmp_path)

    calls = {str(c.args[1].name): c.args[0] for c in mockDownload.call_args_list}
    assert "folder.jpg" in calls
    assert calls["folder.jpg"].endswith("/poster.jpg")
    assert "backdrop.jpg" in calls
    assert calls["backdrop.jpg"].endswith("/backdrop.jpg")


def testFetchMovieArtworkFallsBackToOmdbPosterUrl(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieInfo = {
        "posterUrl": "https://example.com/omdb-poster.jpg",
    }
    with patch.object(
        confirmedOrganizer, "_downloadArtworkFile", return_value=True
    ) as mockDownload:
        confirmedOrganizer._fetchMovieArtwork(movieInfo, tmp_path)

    posterCall = [
        c for c in mockDownload.call_args_list if "folder.jpg" in str(c.args[1])
    ]
    assert posterCall
    assert posterCall[0].args[0] == "https://example.com/omdb-poster.jpg"


def testFetchMovieArtworkSkipsNAOmdbPoster(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    movieInfo = {"posterUrl": "N/A"}
    with patch.object(
        confirmedOrganizer, "_downloadArtworkFile", return_value=True
    ) as mockDownload:
        confirmedOrganizer._fetchMovieArtwork(movieInfo, tmp_path)

    assert not mockDownload.called


def testMoveMovieFetchesArtworkViaEnrichedMetadata(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    """_replicateMovieMetadata calls _fetchMovieArtwork with enriched metadata."""
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "imdbId": "tt1375666",
        "tmdbId": "27205",
        "extension": ".mp4",
        "type": "movie",
    }

    with patch.object(confirmedOrganizer, "_fetchMovieArtwork") as mockArtwork:
        result = confirmedOrganizer.moveMovie(
            srcFile, movieInfo, [movieStorage], interactive=False
        )

    assert result is True
    mockArtwork.assert_called_once()


# ---------------------------------------------------------------------------
# moveTvShow — dry-run
# ---------------------------------------------------------------------------


def testMoveTvShowDryRunReturnsTrueWithoutMoving(
    tmp_path: Path, organizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    srcFile = organizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "extension": ".mkv",
        "type": "tv",
    }

    with patch.object(organizer, "_moveFileWithProgress") as mockMove:
        with caplog.at_level("INFO"):
            result = organizer.moveTvShow(
                srcFile, tvInfo, [tvStorage], interactive=False
            )

    assert result is True
    mockMove.assert_not_called()
    assert srcFile.exists()
    expectedDest = (
        tvStorage / "Breaking Bad" / "Season 01" / "Breaking.Bad.S01E01.Pilot.mkv"
    )
    assert (
        f"...moving TV show:\n"
        f"     Breaking.Bad.S01E01.Pilot.mkv\n"
        f"     -> {expectedDest}"
    ) in caplog.text


class _FakeTtyStream(io.StringIO):
    def __init__(self, interactive: bool):
        super().__init__()
        self._interactive = interactive

    def isatty(self) -> bool:
        return self._interactive


def testMoveFileWithProgressPrefersRename(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = tmp_path / "movie.mkv"
    destFile = tmp_path / "dest" / "movie.mkv"
    srcFile.write_bytes(b"content")
    destFile.parent.mkdir()

    with (
        patch("organiseMyVideo.video.os.rename") as mockRename,
        patch.object(confirmedOrganizer, "_copyFileWithProgress") as mockCopy,
    ):
        confirmedOrganizer._moveFileWithProgress(srcFile, destFile)

    mockRename.assert_called_once_with(srcFile, destFile)
    mockCopy.assert_not_called()


def testMoveFileWithProgressFallsBackToCopyOnCrossDeviceError(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = tmp_path / "movie.mkv"
    destFile = tmp_path / "dest" / "movie.mkv"
    srcFile.write_bytes(b"content")
    destFile.parent.mkdir()

    with (
        patch(
            "organiseMyVideo.video.os.rename",
            side_effect=OSError(errno.EXDEV, "Cross-device link"),
        ) as mockRename,
        patch.object(confirmedOrganizer, "_copyFileWithProgress") as mockCopy,
    ):
        confirmedOrganizer._moveFileWithProgress(srcFile, destFile)

    mockRename.assert_called_once_with(srcFile, destFile)
    mockCopy.assert_called_once_with(srcFile, destFile)


def testCopyFileWithProgressWritesBarOnTty(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = tmp_path / "movie.mkv"
    destFile = tmp_path / "dest" / "movie.mkv"
    srcFile.write_bytes(b"progress-data")
    destFile.parent.mkdir()
    fakeStderr = _FakeTtyStream(interactive=True)

    with patch("sys.stderr", fakeStderr):
        confirmedOrganizer._copyFileWithProgress(srcFile, destFile)

    output = fakeStderr.getvalue()
    assert "Moving movie.mkv:" in output
    assert "100%" in output
    assert output.endswith("\n")
    assert destFile.read_bytes() == b"progress-data"
    assert not srcFile.exists()


def testRenderMoveProgressFitsWithinTerminalWidth(confirmedOrganizer: VideoOrganizer):
    fakeStderr = _FakeTtyStream(interactive=True)
    longFilename = "Very.Long.Show.Name.With.Lots.Of.Words.And.Metadata.Tags.mkv"
    terminalWidth = 50

    with patch(
        "organiseMyVideo.video.shutil.get_terminal_size",
        return_value=MagicMock(columns=terminalWidth),
    ):
        confirmedOrganizer._renderMoveProgress(fakeStderr, longFilename, 512, 1024)

    renderedLine = fakeStderr.getvalue().split("\r")[-1]
    assert len(renderedLine) <= terminalWidth
    assert "Moving " in renderedLine
    assert " 50%" in renderedLine
    assert "..." in renderedLine


def testCopyFileWithProgressSkipsBarWithoutTty(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = tmp_path / "movie.mkv"
    destFile = tmp_path / "dest" / "movie.mkv"
    srcFile.write_bytes(b"progress-data")
    destFile.parent.mkdir()
    fakeStderr = _FakeTtyStream(interactive=False)

    with patch("sys.stderr", fakeStderr):
        confirmedOrganizer._copyFileWithProgress(srcFile, destFile)

    assert fakeStderr.getvalue() == ""
    assert destFile.read_bytes() == b"progress-data"
    assert not srcFile.exists()


# ---------------------------------------------------------------------------
# moveTvShow — confirm mode
# ---------------------------------------------------------------------------


def testMoveTvShowConfirmMovesFile(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    destFile = (
        tvStorage / "Breaking Bad" / "Season 01" / "Breaking.Bad.S01E01.Pilot.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowReplicatesMcmCompanionFiles(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showSourceDir = confirmedOrganizer.sourceDir / "Daredevil, Born Again"
    seasonSourceDir = showSourceDir / "Season 1"
    metadataSourceDir = seasonSourceDir / "metadata"
    metadataSourceDir.mkdir(parents=True)

    srcFile = seasonSourceDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showSourceDir / "banner.jpg").write_bytes(b"banner")
    (showSourceDir / "folder.jpg").write_bytes(b"show-cover")
    (showSourceDir / "backdrop.jpg").write_bytes(b"backdrop")
    (showSourceDir / "backdrop2.jpg").write_bytes(b"backdrop2")
    (showSourceDir / "series.xml").write_text("<Series />", encoding="utf-8")
    (showSourceDir / "mcm_id__show.dvdid.xml").write_text("<Disc />", encoding="utf-8")
    (seasonSourceDir / "folder.jpg").write_bytes(b"season-cover")

    episodeXml = (
        metadataSourceDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.xml"
    )
    episodeXml.write_text(
        "<?xml version='1.0' encoding='utf-8'?><Item><filename>/67da18725f220.jpg</filename></Item>",
        encoding="utf-8",
    )
    (metadataSourceDir / "67da18725f220.jpg").write_bytes(b"episode-thumb")

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "Daredevil, Born Again",
        "season": 1,
        "episode": 4,
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    showDestDir = tvStorage / "Daredevil, Born Again"
    seasonDestDir = showDestDir / "Season 01"
    assert (
        seasonDestDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.mkv"
    ).exists()
    assert (showDestDir / "banner.jpg").read_bytes() == b"banner"
    assert (showDestDir / "folder.jpg").read_bytes() == b"show-cover"
    assert (showDestDir / "backdrop.jpg").read_bytes() == b"backdrop"
    assert (showDestDir / "backdrop2.jpg").read_bytes() == b"backdrop2"
    assert (showDestDir / "series.xml").read_text(encoding="utf-8") == "<Series />"
    assert (showDestDir / "mcm_id__show.dvdid.xml").read_text(
        encoding="utf-8"
    ) == "<Disc />"
    assert (seasonDestDir / "folder.jpg").read_bytes() == b"season-cover"
    destMetadata = (
        seasonDestDir
        / "metadata"
        / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.xml"
    ).read_text(encoding="utf-8")
    assert destMetadata.startswith("<?xml")
    assert "<filename>/67da18725f220.jpg</filename>" in destMetadata
    assert "<EpisodeNumber>4</EpisodeNumber>" not in destMetadata
    assert "<SeasonNumber>1</SeasonNumber>" not in destMetadata
    assert "<EpisodeName>Sic Semper Systema</EpisodeName>" not in destMetadata
    assert (
        seasonDestDir / "metadata" / "67da18725f220.jpg"
    ).read_bytes() == b"episode-thumb"


def testMoveTvShowPreservesExistingEpisodeMetadataInDestination(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showSourceDir = confirmedOrganizer.sourceDir / "Daredevil Born Again"
    seasonSourceDir = showSourceDir / "Season 1"
    metadataSourceDir = seasonSourceDir / "metadata"
    metadataSourceDir.mkdir(parents=True)
    srcFile = seasonSourceDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.mkv"
    srcFile.write_bytes(b"x" * 100)
    (
        metadataSourceDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.xml"
    ).write_text("<Item><EpisodeName>new</EpisodeName></Item>", encoding="utf-8")

    tvStorage = tmp_path / "video1" / "TV"
    metadataDestDir = tvStorage / "Daredevil Born Again" / "Season 01" / "metadata"
    metadataDestDir.mkdir(parents=True)
    (metadataDestDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.xml").write_text(
        "<Item><EpisodeName>existing</EpisodeName></Item>", encoding="utf-8"
    )

    tvInfo = {
        "showName": "Daredevil Born Again",
        "season": 1,
        "episode": 4,
        "episodeTitle": "Sic Semper Systema",
        "seriesId": "12345",
        "imdbId": "tt12345",
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    assert (
        metadataDestDir / "Daredevil.Born.Again.S01E04.Sic.Semper.Systema.xml"
    ).read_text(encoding="utf-8") == "<Item><EpisodeName>existing</EpisodeName></Item>"


def testMoveTvShowCreatesSeriesXmlWhenMissingAndMetadataConfident(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "episodeTitle": "The Beginning",
        "seriesId": "117581",
        "imdbId": "tt9077530",
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    showDestDir = tvStorage / "Virgin River"
    seriesXml = showDestDir / "series.xml"
    assert seriesXml.exists()
    seriesText = seriesXml.read_text(encoding="utf-8")
    assert "<SeriesName>Virgin River</SeriesName>" in seriesText
    assert "<SeriesID>117581</SeriesID>" in seriesText
    assert "<IMDB_ID>tt9077530</IMDB_ID>" in seriesText
    assert (showDestDir / "mcm_id__tt9077530-117581.dvdid.xml").exists()
    assert (
        showDestDir / "Season 06" / "metadata" / "Virgin.River.S06E01.The.Beginning.xml"
    ).exists()


def testMoveTvShowPreservesExistingDvdIdXmlWithoutCreatingDuplicate(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "video1" / "TV"
    showDestDir = tvStorage / "Virgin River"
    showDestDir.mkdir(parents=True)
    (showDestDir / "mcm_id__existing.dvdid.xml").write_text(
        "<Item><SeriesID>existing</SeriesID></Item>", encoding="utf-8"
    )

    tvInfo = {
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "seriesId": "117581",
        "imdbId": "tt9077530",
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    assert (showDestDir / "mcm_id__existing.dvdid.xml").exists()
    assert len(list(showDestDir.glob("mcm_id__*.dvdid.xml"))) == 1


def testMoveTvShowLeavesMultipleExistingDvdIdXmlFilesUnchanged(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "video1" / "TV"
    showDestDir = tvStorage / "Virgin River"
    showDestDir.mkdir(parents=True)
    (showDestDir / "mcm_id__first.dvdid.xml").write_text(
        "<Item><SeriesID>first</SeriesID></Item>", encoding="utf-8"
    )
    (showDestDir / "mcm_id__second.dvdid.xml").write_text(
        "<Item><SeriesID>second</SeriesID></Item>", encoding="utf-8"
    )

    tvInfo = {
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "seriesId": "117581",
        "imdbId": "tt9077530",
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    assert (showDestDir / "mcm_id__first.dvdid.xml").exists()
    assert (showDestDir / "mcm_id__second.dvdid.xml").exists()
    assert len(list(showDestDir.glob("mcm_id__*.dvdid.xml"))) == 2


def testMoveTvShowCreatesSeriesIdOnlyDvdIdXmlWhenImdbMissing(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "seriesId": "117581",
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    dvdIdXml = tvStorage / "Virgin River" / "mcm_id__117581.dvdid.xml"
    assert dvdIdXml.exists()
    dvdIdContent = dvdIdXml.read_text(encoding="utf-8")
    assert "<SeriesID>117581</SeriesID>" in dvdIdContent
    assert "<IMDB_ID>" not in dvdIdContent


def testMoveTvShowPreservesExistingSeriesXmlWithoutOverwriting(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    showSourceDir = confirmedOrganizer.sourceDir / "Alias Name"
    seasonSourceDir = showSourceDir / "Season 1"
    seasonSourceDir.mkdir(parents=True)
    srcFile = seasonSourceDir / "Alias.Name.S01E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    (showSourceDir / "series.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Series>
    <SeriesName>Existing Canonical Name</SeriesName>
    <SeriesID>990001</SeriesID>
</Series>
""",
        encoding="utf-8",
    )

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)
    tvInfo = {
        "showName": "New Alias Name",
        "season": 1,
        "episode": 1,
        "seriesId": "990001",
        "imdbId": "tt8398600",
        "extension": ".mkv",
        "type": "tv",
    }

    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )
    assert result is True

    seriesText = (tvStorage / "New Alias Name" / "series.xml").read_text(
        encoding="utf-8"
    )
    assert "<SeriesName>Existing Canonical Name</SeriesName>" in seriesText
    assert "<SeriesID>990001</SeriesID>" in seriesText
    assert "<IMDB_ID>" not in seriesText


def testMoveTvShowBackfillsExistingIncompleteShowMetadata(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Virgin.River.S06E01.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "video1" / "TV"
    showDestDir = tvStorage / "Virgin River"
    showDestDir.mkdir(parents=True)
    (showDestDir / "series.xml").write_text(
        "<Series><SeriesName>Virgin River</SeriesName></Series>", encoding="utf-8"
    )
    (showDestDir / "mcm_id__existing.dvdid.xml").write_text(
        "<Item><IMDB_ID>tt9077530</IMDB_ID></Item>", encoding="utf-8"
    )

    tvInfo = {
        "showName": "Virgin River",
        "season": 6,
        "episode": 1,
        "seriesId": "117581",
        "imdbId": "tt9077530",
        "extension": ".mkv",
        "type": "tv",
    }

    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    assert "<SeriesID>117581</SeriesID>" in (showDestDir / "series.xml").read_text(
        encoding="utf-8"
    )
    assert "<SeriesID>117581</SeriesID>" in (
        showDestDir / "mcm_id__existing.dvdid.xml"
    ).read_text(encoding="utf-8")


def testMoveTvShowUsesCanonicalEpisodeTitleFilename(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "episode.mkv"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "Law & Order: SVU",
        "season": 3,
        "episode": 2,
        "episodeTitle": "What's Next?: Finale!",
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    destFile = (
        tvStorage
        / "Law & Order: SVU"
        / "Season 03"
        / "Law.Order.SVU.S03E02.Whats.Next.Finale.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowUsesNormalisedTimeRangeEpisodeTitleFilename(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "episode.avi"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {
        "showName": "24",
        "season": 8,
        "episode": 13,
        "episodeTitle": "Day 8: 4:00 A.M.-5:00 A.M.",
        "extension": ".avi",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(
        srcFile, tvInfo, [tvStorage], interactive=False
    )

    assert result is True
    destFile = tvStorage / "24" / "Season 08" / "24.S08E13.Day 8 4.00am-5.00am.avi"
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowUsesNormalisedScrapedTimeRangeEpisodeTitleFilename(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "episode.mkv"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    scraped = {
        "showName": "24",
        "season": 8,
        "episode": 13,
        "episodeTitle": "Day 8 4AM-5AM",
        "seriesId": "12345",
        "episodeId": "67890",
        "extension": ".mkv",
        "type": "tv",
        "metadataSource": "tvdb",
    }
    emptyLibrary = confirmedOrganizer._newMetadataLibrary()
    with patch.object(
        confirmedOrganizer, "_loadMetadataLibrary", return_value=emptyLibrary
    ):
        with patch.object(confirmedOrganizer, "_saveMetadataLibrary"):
            with patch.object(
                confirmedOrganizer, "_fetchTvMetadataFromScraper", return_value=scraped
            ):
                result = confirmedOrganizer.moveTvShow(
                    srcFile,
                    {"showName": "24", "season": 8, "episode": 13, "type": "tv"},
                    [tvStorage],
                    interactive=False,
                )

    assert result is True
    destFile = tvStorage / "24" / "Season 08" / "24.S08E13.Day 8 4.00am-5.00am.mkv"
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowUsesScrapedEpisodeTitleToRenameNoisyFilename(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = (
        confirmedOrganizer.sourceDir
        / "The.Pitt.S02E05.1080p.WEB.h264-ETHEL[EZTVx.to].mkv"
    )
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    scraped = {
        "showName": "The Pitt",
        "season": 2,
        "episode": 5,
        "episodeTitle": "A Better Episode Title",
        "seriesId": "12345",
        "episodeId": "67890",
        "extension": ".mkv",
        "type": "tv",
        "metadataSource": "tvdb",
    }
    emptyLibrary = confirmedOrganizer._newMetadataLibrary()
    with patch.object(
        confirmedOrganizer, "_loadMetadataLibrary", return_value=emptyLibrary
    ):
        with patch.object(confirmedOrganizer, "_saveMetadataLibrary"):
            with patch.object(
                confirmedOrganizer, "_fetchTvMetadataFromScraper", return_value=scraped
            ):
                result = confirmedOrganizer.moveTvShow(
                    srcFile,
                    {"showName": "The Pitt", "season": 2, "episode": 5, "type": "tv"},
                    [tvStorage],
                    interactive=False,
                )

    assert result is True
    destFile = (
        tvStorage
        / "Pitt, The"
        / "Season 02"
        / "The.Pitt.S02E05.A.Better.Episode.Title.mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowNoStorageReturnsFalse(confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "extension": ".mkv",
        "type": "tv",
    }
    result = confirmedOrganizer.moveTvShow(srcFile, tvInfo, [], interactive=False)
    assert result is False


# ---------------------------------------------------------------------------
# promptUserConfirmation — new behaviour (blank=skip, t/m=type switch)
# ---------------------------------------------------------------------------


def testPromptUserConfirmationYesReturnsName(organizer: VideoOrganizer):
    with patch("builtins.input", return_value="y"):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "My Show", "type": "tv"}


def testPromptUserConfirmationEnterReturnsDefault(organizer: VideoOrganizer):
    with patch("builtins.input", return_value=""):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "My Show", "type": "tv"}


def testPromptUserConfirmationCustomNameReturnsName(organizer: VideoOrganizer):
    with patch("builtins.input", return_value="Better Show"):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "Better Show", "type": "tv"}


def testPromptUserConfirmationNThenBlankUsesDefault(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["n", ""]):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "My Show", "type": "tv"}


def testPromptUserConfirmationNThenSpaceUsesDefault(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["n", "   "]):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "My Show", "type": "tv"}


def testPromptUserConfirmationNThenQuitReturnsNone(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["n", "quit"]):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result is None


def testPromptUserConfirmationNThenNewNameReturnsName(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["n", "Corrected Show"]):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "Corrected Show", "type": "tv"}


def testPromptUserConfirmationTSwitchesToTv(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["t", "Breaking Bad"]):
        result = organizer.promptUserConfirmation(
            "file.mkv", "Inception (2010)", "movie"
        )
    assert result == {"name": "Breaking Bad", "type": "tv"}


def testPromptUserConfirmationTDefaultsToCurrentName(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["t", ""]):
        result = organizer.promptUserConfirmation(
            "file.mkv", "Inception (2010)", "movie"
        )
    assert result == {"name": "Inception (2010)", "type": "tv"}


def testPromptUserConfirmationTUsesMatchingTvFolderAsDefault(
    tmp_path: Path, organizer: VideoOrganizer
):
    """When videoDirs is provided and a folder matches the parsed show name, use it as default."""
    tvDir = tmp_path / "TV"
    tvDir.mkdir()
    (tvDir / "Law and Order Special Victims Unit").mkdir()
    filename = "Law.and.Order.Special.Victims.Unit.S27E13.Corrosive.1080p.mkv"
    with patch("builtins.input", side_effect=["t", ""]):
        result = organizer.promptUserConfirmation(
            filename,
            "Law and Order Special Victims Unit S27E13 Corrosive (1080)",
            "movie",
            videoDirs=[tvDir],
        )
    assert result == {"name": "Law and Order Special Victims Unit", "type": "tv"}


def testPromptUserConfirmationTFallsBackToDefaultWhenNoTvFolderMatch(
    tmp_path: Path, organizer: VideoOrganizer
):
    """When videoDirs has no matching folder, fall back to the original defaultName."""
    tvDir = tmp_path / "TV"
    tvDir.mkdir()
    (tvDir / "Breaking Bad").mkdir()
    filename = "Law.and.Order.Special.Victims.Unit.S27E13.Corrosive.1080p.mkv"
    with patch("builtins.input", side_effect=["t", ""]):
        result = organizer.promptUserConfirmation(
            filename,
            "Law and Order Special Victims Unit S27E13 Corrosive (1080)",
            "movie",
            videoDirs=[tvDir],
        )
    assert result == {
        "name": "Law and Order Special Victims Unit S27E13 Corrosive (1080)",
        "type": "tv",
    }


def testPromptUserConfirmationTUserCanOverrideSuggestedTvFolder(
    tmp_path: Path, organizer: VideoOrganizer
):
    """User can override the suggested TV folder name by typing a custom name."""
    tvDir = tmp_path / "TV"
    tvDir.mkdir()
    (tvDir / "Law and Order Special Victims Unit").mkdir()
    filename = "Law.and.Order.Special.Victims.Unit.S27E13.Corrosive.1080p.mkv"
    with patch("builtins.input", side_effect=["t", "My Custom Show"]):
        result = organizer.promptUserConfirmation(
            filename, "Some Movie (2024)", "movie", videoDirs=[tvDir]
        )
    assert result == {"name": "My Custom Show", "type": "tv"}


def testPromptUserConfirmationMSwitchesToMovie(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["m", "Inception"]):
        result = organizer.promptUserConfirmation("file.mkv", "Breaking Bad", "tv")
    assert result == {"name": "Inception", "type": "movie"}


def testPromptUserConfirmationMDefaultsToCurrentName(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["m", ""]):
        result = organizer.promptUserConfirmation("file.mkv", "Breaking Bad", "tv")
    assert result == {"name": "Breaking Bad", "type": "movie"}


def testPromptUserConfirmationPrintsLegendOnFirstCall(organizer: VideoOrganizer):
    """Key legend is printed exactly once, on the first call."""
    with (
        patch("builtins.input", return_value="y"),
        patch("builtins.print") as mockPrint,
    ):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "My Show", "type": "tv"}
    assert mockPrint.call_count == 1
    printed = mockPrint.call_args[0][0]
    assert "y" in printed
    assert "n" in printed
    assert "t" in printed
    assert "m" in printed
    assert "q" in printed


def testPromptUserConfirmationLegendNotPrintedOnSecondCall(organizer: VideoOrganizer):
    """Key legend is suppressed after the first prompt has been shown."""
    with (
        patch("builtins.input", return_value="y"),
        patch("builtins.print") as mockPrint,
    ):
        organizer.promptUserConfirmation("file.mkv", "Show One", "tv")
        mockPrint.reset_mock()
        result = organizer.promptUserConfirmation("file.mkv", "Show Two", "tv")
    assert result == {"name": "Show Two", "type": "tv"}
    mockPrint.assert_not_called()


def testPromptUserConfirmationWritesTextPromptToStderrWhenInteractive(
    organizer: VideoOrganizer,
):
    organizer._promptHelpDisplayed = True
    fakeStderr = _FakeTtyStream(interactive=True)
    fakeStdout = io.StringIO()

    with (
        patch("sys.stderr", fakeStderr),
        patch("sys.stdout", fakeStdout),
        patch("builtins.input", return_value="y") as mockInput,
    ):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")

    assert result == {"name": "My Show", "type": "tv"}
    mockInput.assert_called_once_with()
    assert "TV Show detected: 'My Show'\n" in fakeStderr.getvalue()
    assert "Is this correct?  (y/n/q/t/m or enter new name): " in fakeStderr.getvalue()
    assert fakeStdout.getvalue() == ""


def testPromptUserConfirmationShowsEpisodeTitleWhenAvailable(
    organizer: VideoOrganizer,
):
    organizer._promptHelpDisplayed = True
    fakeStderr = _FakeTtyStream(interactive=True)
    fakeStdout = io.StringIO()

    with (
        patch("sys.stderr", fakeStderr),
        patch("sys.stdout", fakeStdout),
        patch("builtins.input", return_value="y"),
    ):
        result = organizer.promptUserConfirmation(
            "file.mkv",
            "The Pitt",
            "tv",
            episodeTitle="Pilot",
        )

    assert result == {"name": "The Pitt", "type": "tv"}
    assert "TV Show detected: 'The Pitt'\n" in fakeStderr.getvalue()
    assert "Episode Title: Pilot\n" in fakeStderr.getvalue()
    assert "Is this correct?  (y/n/q/t/m or enter new name): " in fakeStderr.getvalue()
    assert fakeStdout.getvalue() == ""


def testPromptUserConfirmationReusesConfirmedTvShow(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["y"]) as mockInput:
        first = organizer.promptUserConfirmation("file1.mkv", "The Pitt", "tv")
        second = organizer.promptUserConfirmation("file2.mkv", "The Pitt", "tv")
    assert first == {"name": "The Pitt", "type": "tv"}
    assert second == {"name": "The Pitt", "type": "tv"}
    assert mockInput.call_count == 1


def testPromptUserConfirmationDoesNotReuseMovieChoices(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["y", "y"]) as mockInput:
        first = organizer.promptUserConfirmation(
            "file1.mkv", "Inception (2010)", "movie"
        )
        second = organizer.promptUserConfirmation(
            "file2.mkv", "Inception (2010)", "movie"
        )
    assert first == {"name": "Inception (2010)", "type": "movie"}
    assert second == {"name": "Inception (2010)", "type": "movie"}
    assert mockInput.call_count == 2


def testPromptUserConfirmationUsesCursesMenuWhenEnabled(organizer: VideoOrganizer):
    organizer.useCurses = True
    with (
        patch.object(organizer, "_shouldUseCursesPrompts", return_value=True),
        patch.object(organizer, "_readCursesMenuChoice", return_value="y") as mockMenu,
        patch.object(organizer, "_readTextResponse") as mockText,
    ):
        result = organizer.promptUserConfirmation("file.mkv", "My Show", "tv")
    assert result == {"name": "My Show", "type": "tv"}
    mockMenu.assert_called_once_with(
        "TV Show detected: 'My Show'\nIs this correct?  (y/n/q/t/m or enter new name): ",
        validChoices={"y", "n", "q", "t", "m"},
        defaultChoice="y",
    )
    mockText.assert_not_called()


def testReadCursesMenuChoiceKeepsPromptInScrollFlow(organizer: VideoOrganizer):
    class FakeSingleKeyInput:
        def __init__(self, values: list[str]):
            self._values = iter(values)

        def fileno(self) -> int:
            return 0

        def read(self, _: int) -> str:
            return next(self._values)

    fakeInput = FakeSingleKeyInput(["x", "y"])
    fakeOutput = io.StringIO()
    iflag = 1280
    oflag = 5
    cflag = 191
    lflag = 35387
    ispeed = 15
    ospeed = 15
    # Match the shape returned by termios.tcgetattr():
    # [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
    control_characters = [b"\x03", b"\x1c", b"\x7f", b"\x15", b"\x04", 0, 1]
    savedTerminalState = [
        iflag,
        oflag,
        cflag,
        lflag,
        ispeed,
        ospeed,
        control_characters,
    ]

    with (
        patch("sys.stdin", fakeInput),
        patch("sys.stdout", fakeOutput),
        patch("termios.tcgetattr", return_value=savedTerminalState),
        patch("tty.setraw"),
        patch("termios.tcsetattr") as mockRestore,
    ):
        result = organizer._readCursesMenuChoice(
            "TV Show detected: 'My Show'",
            validChoices={"y", "n", "q", "t", "m"},
            defaultChoice="y",
        )

    assert result == "y"
    output = fakeOutput.getvalue()
    assert output.count("TV Show detected: 'My Show'") == 2
    assert "Use one of: m, n, q, t, y" in output
    firstPrompt = output.index("TV Show detected: 'My Show'")
    status = output.index("Use one of: m, n, q, t, y")
    secondPrompt = output.rindex("TV Show detected: 'My Show'")
    assert firstPrompt < status < secondPrompt
    mockRestore.assert_called_once_with(0, 1, savedTerminalState)


# ---------------------------------------------------------------------------
# moveMovie — skip and type-switch via promptUserConfirmation
# ---------------------------------------------------------------------------


def testMoveMovieUsesDefaultWhenUserEntersBlank(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "extension": ".mp4",
        "type": "movie",
    }
    with patch("builtins.input", side_effect=["n", ""]):
        result = confirmedOrganizer.moveMovie(srcFile, movieInfo, [movieStorage])
    assert result is True
    assert not srcFile.exists()
    destFile = movieStorage / "Inception (2010)" / "Inception (2010).mp4"
    assert destFile.exists()


def testMoveMovieSwitchesToTv(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvStorage = tmp_path / "tv1"
    tvStorage.mkdir()
    movieInfo = {
        "title": "Inception",
        "year": "2010",
        "extension": ".mp4",
        "type": "movie",
    }
    # user says 't', enters show name "Inception Show", season 2
    with patch("builtins.input", side_effect=["t", "Inception Show", "2"]):
        result = confirmedOrganizer.moveMovie(
            srcFile, movieInfo, [movieStorage], videoDirs=[tvStorage]
        )
    assert result is True
    destFile = tvStorage / "Inception Show" / "Season 02" / "Inception (2010).mp4"
    assert destFile.exists()
    assert not srcFile.exists()


# ---------------------------------------------------------------------------
# moveTvShow — skip and type-switch via promptUserConfirmation
# ---------------------------------------------------------------------------


def testMoveTvShowUsesDefaultWhenUserEntersBlank(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "tv1"
    tvStorage.mkdir()
    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "extension": ".mkv",
        "type": "tv",
    }
    with patch("builtins.input", side_effect=["n", ""]):
        result = confirmedOrganizer.moveTvShow(srcFile, tvInfo, [tvStorage])
    assert result is True
    assert not srcFile.exists()
    destFile = (
        tvStorage / "Breaking Bad" / "Season 01" / "Breaking.Bad.S01E01.Pilot.mkv"
    )
    assert destFile.exists()


def testMoveTvShowSwitchesToMovie(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "tv1"
    tvStorage.mkdir()
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvInfo = {
        "showName": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "extension": ".mkv",
        "type": "tv",
    }
    # user says 'm', enters movie title "Breaking Bad Movie", year 2013
    with patch("builtins.input", side_effect=["m", "Breaking Bad Movie", "2013"]):
        result = confirmedOrganizer.moveTvShow(
            srcFile, tvInfo, [tvStorage], movieDirs=[movieStorage]
        )
    assert result is True
    destFile = (
        movieStorage / "Breaking Bad Movie (2013)" / "Breaking Bad Movie (2013).mkv"
    )
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowReusesConfirmedChoiceWithoutSecondPrompt(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    firstFile = confirmedOrganizer.sourceDir / "The.Pitt.S01E13.Pilot.mkv"
    secondFile = confirmedOrganizer.sourceDir / "The.Pitt.S02E07.Hour.mkv"
    firstFile.write_bytes(b"x" * 100)
    secondFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "tv1"
    tvStorage.mkdir()
    firstTvInfo = {
        "showName": "The Pitt",
        "season": 1,
        "episode": 13,
        "episodeTitle": "Pilot",
        "extension": ".mkv",
        "type": "tv",
    }
    secondTvInfo = {
        "showName": "The Pitt",
        "season": 2,
        "episode": 7,
        "episodeTitle": "Hour",
        "extension": ".mkv",
        "type": "tv",
    }

    with patch("builtins.input", side_effect=["y"]) as mockInput:
        firstResult = confirmedOrganizer.moveTvShow(firstFile, firstTvInfo, [tvStorage])
        secondResult = confirmedOrganizer.moveTvShow(
            secondFile, secondTvInfo, [tvStorage]
        )

    assert firstResult is True
    assert secondResult is True
    assert mockInput.call_count == 1
    assert (
        tvStorage / "Pitt, The" / "Season 01" / "The.Pitt.S01E13.Pilot.mkv"
    ).exists()
    assert (tvStorage / "Pitt, The" / "Season 02" / "The.Pitt.S02E07.Hour.mkv").exists()


# ---------------------------------------------------------------------------
# cleanNames — dry-run
# ---------------------------------------------------------------------------


def testCleanNamesDryRunDoesNotRename(sourceDir: Path, organizer: VideoOrganizer):
    original = sourceDir / "www.UIndex.org - Some Movie (2020)"
    original.mkdir()
    stats = organizer.cleanNames()
    assert original.exists(), "dry-run must not rename the folder"
    assert stats["renamed"] == 1
    assert stats["errors"] == 0


def testCleanNamesDryRunSkipsNonMatching(sourceDir: Path, organizer: VideoOrganizer):
    normal = sourceDir / "Normal Movie (2020)"
    normal.mkdir()
    stats = organizer.cleanNames()
    assert normal.exists()
    assert stats["renamed"] == 0
    assert stats["skipped"] == 0


def testCleanNamesDryRunTorrentingPrefix(sourceDir: Path, organizer: VideoOrganizer):
    original = sourceDir / "www.Torrenting.com - Great Show S01E01.mkv"
    original.write_bytes(b"x" * 50)
    stats = organizer.cleanNames()
    assert original.exists(), "dry-run must not rename the file"
    assert stats["renamed"] == 1


# ---------------------------------------------------------------------------
# cleanNames — confirm mode (actual rename)
# ---------------------------------------------------------------------------


def testCleanNamesConfirmRenamesFolder(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    original = sourceDir / "www.UIndex.org - Some Movie (2020)"
    original.mkdir()
    stats = confirmedOrganizer.cleanNames()
    expected = sourceDir / "Some Movie (2020)"
    assert not original.exists()
    assert expected.exists()
    assert stats["renamed"] == 1
    assert stats["errors"] == 0


def testCleanNamesConfirmRenamesFile(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    original = sourceDir / "www.Torrenting.com - Great Show S01E01.mkv"
    original.write_bytes(b"x" * 50)
    stats = confirmedOrganizer.cleanNames()
    expected = sourceDir / "Great Show S01E01.mkv"
    assert not original.exists()
    assert expected.exists()
    assert stats["renamed"] == 1


def testCleanNamesConfirmCaseInsensitive(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    original = sourceDir / "WWW.UINDEX.ORG - Movie Title (2021)"
    original.mkdir()
    stats = confirmedOrganizer.cleanNames()
    expected = sourceDir / "Movie Title (2021)"
    assert expected.exists()
    assert stats["renamed"] == 1


def testCleanNamesMissingSrcReturnsZeroStats(tmp_path: Path):
    org = VideoOrganizer(sourceDir=str(tmp_path / "nonexistent"), dryRun=False)
    stats = org.cleanNames()
    assert stats == {"renamed": 0, "skipped": 0, "errors": 0}


def testCleanNamesLeavesNonMatchingUntouched(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    keep = sourceDir / "Normal Movie (2019)"
    keep.mkdir()
    original = sourceDir / "www.UIndex.org - Prefixed Movie (2020)"
    original.mkdir()
    stats = confirmedOrganizer.cleanNames()
    assert keep.exists()
    assert stats["renamed"] == 1


def testCleanNamesSkippedCounterWhenResultIsEmpty(
    sourceDir: Path, confirmedOrganizer: VideoOrganizer
):
    """A name that is only the prefix should be skipped (stripped result is empty)."""
    prefixOnly = sourceDir / "www.UIndex.org - "
    prefixOnly.mkdir()
    stats = confirmedOrganizer.cleanNames()
    assert prefixOnly.exists(), "prefix-only folder must not be removed"
    assert stats["skipped"] == 1
    assert stats["renamed"] == 0


# ---------------------------------------------------------------------------
# removeTorrentsInLibrary — dry-run mode
# ---------------------------------------------------------------------------


def testRemoveTorrentsInLibraryMissingDirReturnsZeroStats(
    organizer: VideoOrganizer, tmp_path: Path
):
    """Non-existent torrent directory returns zero counts."""
    stats = organizer.removeTorrentsInLibrary(torrentDir=str(tmp_path / "nonexistent"))
    assert stats == {"deleted": 0, "skipped": 0, "errors": 0}


def testRemoveTorrentsInLibraryDryRunDeletesMovieTorrent(tmp_path: Path):
    """Dry-run: torrent matching a library movie is counted but file is not removed."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "Inception.2010.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    # Fake library: movie storage with matching directory
    movieRoot = tmp_path / "movie1"
    (movieRoot / "Inception (2010)").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=True)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert torrentFile.exists(), "dry-run must not delete the file"
    assert stats["deleted"] == 1
    assert stats["skipped"] == 0
    assert stats["errors"] == 0


def testRemoveTorrentsInLibraryDryRunDeletesTvTorrent(tmp_path: Path):
    """Dry-run: torrent matching a library TV show is counted but file is not removed."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "Breaking.Bad.S01E01.Pilot.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    tvRoot = tmp_path / "TV"
    (tvRoot / "Breaking Bad").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=True)
    with patch.object(org, "scanStorageLocations", return_value=([], [tvRoot])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert torrentFile.exists(), "dry-run must not delete the file"
    assert stats["deleted"] == 1
    assert stats["skipped"] == 0


def testRemoveTorrentsInLibraryDryRunKeepsUnknownTorrent(tmp_path: Path):
    """Dry-run: torrent with no library match is kept and counted as skipped."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "Unknown.Movie.2099.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    movieRoot = tmp_path / "movie1"
    movieRoot.mkdir()

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=True)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert torrentFile.exists()
    assert stats["skipped"] == 1
    assert stats["deleted"] == 0


# ---------------------------------------------------------------------------
# removeTorrentsInLibrary — confirm mode (actual deletion)
# ---------------------------------------------------------------------------


def testRemoveTorrentsInLibraryConfirmDeletesMovieTorrent(tmp_path: Path):
    """Confirm mode: torrent matching a library movie is deleted."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "The.Matrix.1999.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    movieRoot = tmp_path / "movie1"
    (movieRoot / "The Matrix (1999)").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert not torrentFile.exists(), "torrent file should be deleted in confirm mode"
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


def testRemoveTorrentsInLibraryConfirmDeletesTvTorrent(tmp_path: Path):
    """Confirm mode: torrent matching a library TV show is deleted."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "The.Office.S03E07.Branch.Closing.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    tvRoot = tmp_path / "TV"
    (tvRoot / "Office, The").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([], [tvRoot])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert not torrentFile.exists()
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


def testRemoveTorrentsInLibraryConfirmKeepsUnknownTorrent(tmp_path: Path):
    """Confirm mode: torrent with no library match is not deleted."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "Unreleased.Movie.2030.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    movieRoot = tmp_path / "movie1"
    movieRoot.mkdir()

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert torrentFile.exists()
    assert stats["skipped"] == 1
    assert stats["deleted"] == 0


def testRemoveTorrentsInLibraryHandlesTorrentWithoutInnerExtension(tmp_path: Path):
    """Torrent named without inner video extension (e.g. Movie.2010.torrent) is still matched."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "Inception.2010.torrent"
    torrentFile.write_bytes(b"torrent data")

    movieRoot = tmp_path / "movie1"
    (movieRoot / "Inception (2010)").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert not torrentFile.exists()
    assert stats["deleted"] == 1


def testRemoveTorrentsInLibraryScansSubdirectories(tmp_path: Path):
    """Torrents nested in sub-directories cause the containing folder to be removed."""
    downloadDir = tmp_path / "Download"
    subDir = downloadDir / "movies"
    subDir.mkdir(parents=True)
    torrentFile = subDir / "Interstellar.2014.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    movieRoot = tmp_path / "movie1"
    (movieRoot / "Interstellar (2014)").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert not subDir.exists()
    assert stats["deleted"] == 1


def testRemoveTorrentsInLibraryStripsKnownPrefixBeforeMatching(tmp_path: Path):
    """Torrents with a known site prefix are matched after the prefix is stripped."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "www.Torrenting.com - Inception.2010.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    movieRoot = tmp_path / "movie1"
    (movieRoot / "Inception (2010)").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([movieRoot], [])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert (
        not torrentFile.exists()
    ), "prefixed torrent should be deleted when matched after prefix strip"
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# cleanTorrentNames — rename .torrent files by stripping site prefixes
# ---------------------------------------------------------------------------


def testCleanTorrentNamesMissingDirReturnsZeroStats(
    organizer: VideoOrganizer, tmp_path: Path
):
    """Non-existent torrent directory returns zero counts."""
    stats = organizer.cleanTorrentNames(torrentDir=str(tmp_path / "nonexistent"))
    assert stats == {"renamed": 0, "skipped": 0, "errors": 0}


def testCleanTorrentNamesDryRunRenamesPrefixedTorrent(tmp_path: Path):
    """Dry-run: prefixed torrent is counted as renamed but file is not actually renamed."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "www.Torrenting.com - Inception.2010.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=True)
    stats = org.cleanTorrentNames(torrentDir=str(downloadDir))

    assert torrentFile.exists(), "dry-run must not rename the file"
    assert stats["renamed"] == 1
    assert stats["skipped"] == 0
    assert stats["errors"] == 0


def testCleanTorrentNamesConfirmRenamesPrefixedTorrent(tmp_path: Path):
    """Confirm mode: prefixed torrent is renamed to its clean name."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "www.Torrenting.com - Inception.2010.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")
    expectedFile = downloadDir / "Inception.2010.mkv.torrent"

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    stats = org.cleanTorrentNames(torrentDir=str(downloadDir))

    assert not torrentFile.exists(), "original prefixed file should be gone"
    assert expectedFile.exists(), "renamed file should exist"
    assert stats["renamed"] == 1
    assert stats["errors"] == 0


def testCleanTorrentNamesSkipsUnprefixedTorrent(tmp_path: Path):
    """Torrent without a known prefix is not counted."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "Inception.2010.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    stats = org.cleanTorrentNames(torrentDir=str(downloadDir))

    assert torrentFile.exists()
    assert stats["renamed"] == 0
    assert stats["skipped"] == 0
    assert stats["errors"] == 0


def testCleanTorrentNamesHandlesUIndexPrefix(tmp_path: Path):
    """Confirm mode: UIndex-prefixed torrent is renamed correctly."""
    downloadDir = tmp_path / "Download"
    downloadDir.mkdir()
    torrentFile = downloadDir / "www.UIndex.org - Breaking.Bad.S01E01.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")
    expectedFile = downloadDir / "Breaking.Bad.S01E01.mkv.torrent"

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    stats = org.cleanTorrentNames(torrentDir=str(downloadDir))

    assert not torrentFile.exists()
    assert expectedFile.exists()
    assert stats["renamed"] == 1
    assert stats["errors"] == 0


def testRemoveTorrentsInLibraryDryRunCountsMatchingDownloadFolder(tmp_path: Path):
    """Dry-run: a matching download folder is counted but not actually removed."""
    downloadDir = tmp_path / "Download"
    prefixedDir = (
        downloadDir / "www.Torrenting.com - Silent.Witness.S28E09.720p.x265-TiPEX"
    )
    prefixedDir.mkdir(parents=True)
    torrentFile = (
        prefixedDir
        / "www.Torrenting.com - Silent.Witness.S28E09.720p.x265-TiPEX.torrent"
    )
    torrentFile.write_bytes(b"torrent data")

    tvRoot = tmp_path / "TV"
    (tvRoot / "Silent Witness").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=True)
    with patch.object(org, "scanStorageLocations", return_value=([], [tvRoot])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert prefixedDir.exists(), "dry-run must not delete the folder"
    assert torrentFile.exists(), "dry-run must not delete files inside the folder"
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


def testRemoveTorrentsInLibraryDeletesMatchingDownloadFolderWithPrefixedTorrent(
    tmp_path: Path,
):
    """Confirm mode: a matching download folder is removed when it contains a prefixed torrent."""
    downloadDir = tmp_path / "Download"
    prefixedDir = (
        downloadDir
        / "www.UIndex.org    -    FBI Most Wanted S06E13 Greek Tragedy 1080p"
    )
    prefixedDir.mkdir(parents=True)
    torrentFile = (
        prefixedDir
        / "www.UIndex.org    -    FBI.Most.Wanted.S06E04.MULTi.1080p.WEB.x264-AMB3R.torrent"
    )
    torrentFile.write_bytes(b"torrent data")

    tvRoot = tmp_path / "TV"
    (tvRoot / "FBI Most Wanted").mkdir(parents=True)

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    with patch.object(org, "scanStorageLocations", return_value=([], [tvRoot])):
        stats = org.removeTorrentsInLibrary(torrentDir=str(downloadDir))

    assert not prefixedDir.exists(), "matching download folder should be removed"
    assert not torrentFile.exists()
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


def testCleanTorrentNamesScansSubdirectories(tmp_path: Path):
    """Torrents nested in sub-directories are also renamed."""
    downloadDir = tmp_path / "Download"
    subDir = downloadDir / "tv"
    subDir.mkdir(parents=True)
    torrentFile = subDir / "www.Torrenting.com - The.Office.S03E07.mkv.torrent"
    torrentFile.write_bytes(b"torrent data")
    expectedFile = subDir / "The.Office.S03E07.mkv.torrent"

    org = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    stats = org.cleanTorrentNames(torrentDir=str(downloadDir))

    assert not torrentFile.exists()
    assert expectedFile.exists()
    assert stats["renamed"] == 1


def testResetTvEpisodeTitlesRenamesNoisyStoredEpisodes(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "After Life" / "Season 01"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    episodeFile = seasonDir / "After.Life.S01E04.1080p.WEB.h264.mkv"
    episodeFile.write_bytes(b"x" * 20)
    episodeSidecarXml = seasonDir / "After.Life.S01E04.1080p.WEB.h264.xml"
    episodeSidecarXml.write_text("<Item />", encoding="utf-8")
    episodeSidecarJpg = seasonDir / "After.Life.S01E04.1080p.WEB.h264.jpg"
    episodeSidecarJpg.write_bytes(b"cover")
    episodeMetadataFile = metadataDir / "After.Life.S01E04.1080p.WEB.h264.xml"
    episodeMetadataFile.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeName>1080p WEB h264</EpisodeName>
    <EpisodeNumber>4</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
</Item>
""",
        encoding="utf-8",
    )
    episodeMetadataJpg = metadataDir / "After.Life.S01E04.1080p.WEB.h264.jpg"
    episodeMetadataJpg.write_bytes(b"thumb")

    libraryPath = tmp_path / "metadataLibrary.json"
    libraryPath.write_text(
        json.dumps(_savedAfterLifeMetadataLibrary()), encoding="utf-8"
    )

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([], [tvStorage]),
    ):
        with patch.object(
            confirmedOrganizer,
            "_getMetadataLibraryPath",
            return_value=libraryPath,
        ):
            stats = confirmedOrganizer.resetTvEpisodeTitles()

    renamedEpisode = metadataDir.parent / "After Life.S01E04.Sic Semper Systema.mkv"
    renamedEpisodeSidecarXml = seasonDir / "After Life.S01E04.Sic Semper Systema.xml"
    renamedEpisodeSidecarJpg = seasonDir / "After Life.S01E04.Sic Semper Systema.jpg"
    renamedMetadata = metadataDir / "After Life.S01E04.Sic Semper Systema.xml"
    renamedMetadataJpg = metadataDir / "After Life.S01E04.Sic Semper Systema.jpg"
    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert renamedEpisode.exists()
    assert not episodeFile.exists()
    assert renamedEpisodeSidecarXml.exists()
    assert not episodeSidecarXml.exists()
    assert renamedEpisodeSidecarJpg.exists()
    assert not episodeSidecarJpg.exists()
    assert renamedMetadata.exists()
    assert not episodeMetadataFile.exists()
    assert renamedMetadataJpg.exists()
    assert not episodeMetadataJpg.exists()
    assert "<EpisodeName>Sic Semper Systema</EpisodeName>" in renamedMetadata.read_text(
        encoding="utf-8"
    )


def testResetTvEpisodeTitlesSkipsCleanStoredEpisodesWithoutScraperLookup(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "After Life" / "Season 01"
    seasonDir.mkdir(parents=True)
    episodeFile = seasonDir / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    episodeFile.write_bytes(b"x" * 20)

    confirmedOrganizer._tvMetadataFetcher = MagicMock(
        side_effect=AssertionError("scraper lookup should not run")
    )

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([], [tvStorage]),
    ):
        stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert episodeFile.exists()


def testResetTvEpisodeTitlesCapitalisesLowercaseShowNames(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "after life" / "Season 01"
    seasonDir.mkdir(parents=True)
    episodeFile = seasonDir / "after.life.S01E04.Sic.Semper.Systema.mkv"
    episodeFile.write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            with caplog.at_level("INFO"):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert not episodeFile.exists()
    renamedSeasonDir = tvStorage / "After Life" / "Season 01"
    assert renamedSeasonDir.exists()
    assert (renamedSeasonDir / "After.Life.S01E04.Sic.Semper.Systema.mkv").exists()
    assert "renaming TV Show: After Life (from after life)" in caplog.text


def testResetTvEpisodeTitlesRegeneratesCorruptEpisodeMetadataXml(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer, caplog: pytest.LogCaptureFixture
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "After Life" / "Season 01"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    episodeFile = seasonDir / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    episodeFile.write_bytes(b"x" * 20)
    metadataFile = metadataDir / "After.Life.S01E04.Sic.Semper.Systema.xml"
    metadataFile.write_text(
        "<Item><EpisodeName>Sic & Semper Systema</EpisodeName></Item>"
    )

    libraryPath = tmp_path / "metadataLibrary.json"
    libraryPath.write_text(
        json.dumps(_savedAfterLifeMetadataLibrary()), encoding="utf-8"
    )

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([], [tvStorage]),
    ):
        with patch.object(
            confirmedOrganizer,
            "_getMetadataLibraryPath",
            return_value=libraryPath,
        ):
            with caplog.at_level("WARNING"):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert "could not parse metadata XML" in caplog.text
    regenerated = metadataFile.read_text(encoding="utf-8")
    assert "<EpisodeName>Sic Semper Systema</EpisodeName>" in regenerated
    assert "<seriesid>" in regenerated


def testResetTvEpisodeTitlesSkipsCleanStoredEpisodesWithSpacesAndApostrophes(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "Code Black" / "Season 03"
    seasonDir.mkdir(parents=True)
    episodeFile = seasonDir / "Code Black.S03E12.As Night Comes and I’m Breathing.mkv"
    episodeFile.write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert episodeFile.exists()


def testResetTvEpisodeTitlesNormalisesHourOnlyTimedEpisodeTitles(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "24" / "Season 08"
    seasonDir.mkdir(parents=True)
    episodeFile = seasonDir / "24.S08E13.Day 8 4AM-5AM[Action-Drama-Mystery][2010].avi"
    episodeFile.write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            stats = confirmedOrganizer.resetTvEpisodeTitles()

    renamedEpisode = seasonDir / "24.S08E13.Day 8 4.00am-5.00am.avi"
    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert renamedEpisode.exists()
    assert not episodeFile.exists()


def testResetTvEpisodeTitlesNormalisesTimedEpisodeTitles(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "24" / "Season 08"
    seasonDir.mkdir(parents=True)
    episodeFile = seasonDir / "24.S08E13.Day.8.4.00.A.M.5.00.A.M.avi"
    episodeFile.write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            stats = confirmedOrganizer.resetTvEpisodeTitles()

    renamedEpisode = seasonDir / "24.S08E13.Day 8 4.00am 5.00am.avi"
    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert renamedEpisode.exists()
    assert not episodeFile.exists()


def testResetTvEpisodeTitlesPreservesSpacesWhenRetitlingSpacedEpisodeNames(
    tmp_path: Path, confirmedOrganizer: VideoOrganizer
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "Percy Jackson and the Olympians" / "Season 01"
    seasonDir.mkdir(parents=True)
    episodeFile = (
        seasonDir
        / "Percy Jackson and the Olympians.S01E01.I Accidentally Vaporize My Teacher.mkv"
    )
    episodeFile.write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_tvEpisodeTitleNeedsCanonicalLookup",
        return_value=True,
    ):
        with patch.object(
            confirmedOrganizer,
            "_enrichTvMetadata",
            return_value={
                "showName": "Percy Jackson and the Olympians",
                "season": 1,
                "episode": 1,
                "episodeTitle": "I Accidentally Vaporize My Pre-Algebra Teacher",
                "seriesId": "415151",
                "extension": "mkv",
                "type": "tv",
            },
        ):
            with patch.object(
                confirmedOrganizer,
                "scanStorageLocations",
                return_value=([], [tvStorage]),
            ):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    renamedEpisode = (
        seasonDir
        / "Percy Jackson and the Olympians.S01E01.I Accidentally Vaporize My Pre-Algebra Teacher.mkv"
    )
    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert renamedEpisode.exists()
    assert not episodeFile.exists()


def testResetTvEpisodeTitlesLogsShowNamesAndOnlyRenameChanges(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    tvStorage = tmp_path / "video1" / "TV"

    afterLifeSeasonDir = tvStorage / "After Life" / "Season 01"
    afterLifeSeasonDir.mkdir(parents=True)
    (afterLifeSeasonDir.parent / "series.xml").write_text(
        "<Series><SeriesID>361563</SeriesID></Series>", encoding="utf-8"
    )
    (afterLifeSeasonDir.parent / "mcm_id__361563.dvdid.xml").write_text(
        "<Item><SeriesID>361563</SeriesID></Item>", encoding="utf-8"
    )
    noisyEpisode = afterLifeSeasonDir / "After.Life.S01E04.1080p.WEB.h264.mkv"
    noisyEpisode.write_bytes(b"x" * 20)

    anotherShowSeasonDir = tvStorage / "Another Show" / "Season 01"
    anotherShowSeasonDir.mkdir(parents=True)
    (anotherShowSeasonDir.parent / "series.xml").write_text(
        "<Series><SeriesID>999999</SeriesID></Series>", encoding="utf-8"
    )
    (anotherShowSeasonDir.parent / "mcm_id__999999.dvdid.xml").write_text(
        "<Item><SeriesID>999999</SeriesID></Item>", encoding="utf-8"
    )
    cleanEpisode = anotherShowSeasonDir / "Another.Show.S01E01.Opening.Night.mkv"
    cleanEpisode.write_bytes(b"x" * 20)

    libraryPath = tmp_path / "metadataLibrary.json"
    libraryPath.write_text(
        json.dumps(_savedAfterLifeMetadataLibrary()), encoding="utf-8"
    )

    with patch.object(
        confirmedOrganizer,
        "scanStorageLocations",
        return_value=([], [tvStorage]),
    ):
        with patch.object(
            confirmedOrganizer,
            "_getMetadataLibraryPath",
            return_value=libraryPath,
        ):
            with caplog.at_level("INFO"):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 1, "skipped": 1, "errors": 0}
    assert "scanning: After Life [361563]" in caplog.text
    assert "scanning: Another Show [999999]" in caplog.text
    assert (
        "...tv show:\n"
        "     After.Life.S01E04.1080p.WEB.h264.mkv\n"
        "     After Life.S01E04.Sic Semper Systema.mkv"
    ) in caplog.text
    assert "...tv show:\n     Another.Show.S01E01.Opening.Night.mkv" not in caplog.text
    assert (afterLifeSeasonDir / "After Life.S01E04.Sic Semper Systema.mkv").exists()
    assert cleanEpisode.exists()
    assert not noisyEpisode.exists()
    assert "starting TV episode title reset" not in caplog.text
    assert "scanning for storage locations" not in caplog.text
    assert "using saved metadata library" not in caplog.text
    assert "fetch TV metadata" not in caplog.text
    assert "TV episode title reset complete" not in caplog.text
    assert "preserving existing metadata files" not in caplog.text
    assert "preserving existing metadata" not in caplog.text


def testResetTvEpisodeTitlesWarnsWhenSeriesIdMatchesAcrossShowFolders(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    tvStorage = tmp_path / "video1" / "TV"

    grimmDir = tvStorage / "Grimm" / "Season 01"
    grimmDir.mkdir(parents=True)
    (grimmDir.parent / "series.xml").write_text(
        "<Series><SeriesID>777</SeriesID></Series>", encoding="utf-8"
    )
    (grimmDir / "Grimm.S01E01.Pilot.mkv").write_bytes(b"x" * 20)

    grimmYearDir = tvStorage / "Grimm (2011)" / "Season 01"
    grimmYearDir.mkdir(parents=True)
    (grimmYearDir.parent / "series.xml").write_text(
        "<Series><SeriesID>777</SeriesID></Series>", encoding="utf-8"
    )
    (grimmYearDir / "Grimm.S01E02.Bears.Will.Be.Bears.mkv").write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            with caplog.at_level("INFO"):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 2, "errors": 0}
    assert (
        "rescan found possible duplicate TV show folders for SeriesID 777: "
        "Grimm, Grimm (2011)"
    ) in caplog.text


def testResetTvEpisodeTitlesWarnsWhenTrailingTheFoldersDuplicate(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    tvStorage = tmp_path / "video1" / "TV"

    canonicalDir = tvStorage / "Crown, The" / "Season 01"
    canonicalDir.mkdir(parents=True)
    (canonicalDir / "The.Crown.S01E01.Wolferton.Splash.mkv").write_bytes(b"x" * 20)

    leadingArticleDir = tvStorage / "The Crown" / "Season 01"
    leadingArticleDir.mkdir(parents=True)
    (leadingArticleDir / "The.Crown.S01E02.Hyde.Park.Corner.mkv").write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            with caplog.at_level("INFO"):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 2, "errors": 0}
    assert (
        "rescan found possible duplicate TV show folders for canonical name "
        "Crown, The: Crown, The, The Crown"
    ) in caplog.text
    assert "scanning: The Crown" not in caplog.text
    assert caplog.text.count("scanning: Crown, The") == 2


def testResetTvEpisodeTitlesWarnsWhenNormalizedNamesDuplicate(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    tvStorage = tmp_path / "video1" / "TV"

    for showName, filename in (
        ("Grimm", "Grimm.S01E01.Pilot.mkv"),
        ("Grimm (2011)", "Grimm.S01E02.Bears.Will.Be.Bears.mkv"),
        ("Hijack [419254]", "Hijack.S01E01.Final.Call.mkv"),
        ("Hijack 2023", "Hijack.S01E02.3.Joules.mkv"),
        ("Hijak", "Hijack.S01E03.Draw.a.Blank.mkv"),
        ("Homestead", "Homestead.S01E01.Homecoming.mkv"),
        ("Homestead The Series", "Homestead.S01E02.Threshold.mkv"),
    ):
        seasonDir = tvStorage / showName / "Season 01"
        seasonDir.mkdir(parents=True)
        (seasonDir / filename).write_bytes(b"x" * 20)

    (tvStorage / "Hijack [419254]" / "series.xml").write_text(
        "<Series><SeriesID>419254</SeriesID></Series>", encoding="utf-8"
    )

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            with caplog.at_level("INFO"):
                stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 7, "errors": 0}
    assert (
        "rescan found possible duplicate TV show folders for canonical name "
        "Grimm: Grimm, Grimm (2011)"
    ) in caplog.text
    assert (
        "rescan found possible duplicate TV show folders for canonical name "
        "Hijack: Hijack 2023, Hijack [419254], Hijak"
    ) in caplog.text
    assert (
        "rescan found possible duplicate TV show folders for canonical name "
        "Homestead: Homestead, Homestead The Series"
    ) in caplog.text


def testResetTvEpisodeTitlesRepairsIncompleteShowMetadata(
    tmp_path: Path,
    confirmedOrganizer: VideoOrganizer,
    caplog: pytest.LogCaptureFixture,
):
    tvStorage = tmp_path / "video1" / "TV"
    seasonDir = tvStorage / "After Life" / "Season 01"
    metadataDir = seasonDir / "metadata"
    metadataDir.mkdir(parents=True)
    (seasonDir.parent / "series.xml").write_text(
        "<Series><SeriesName>After Life</SeriesName></Series>", encoding="utf-8"
    )
    (seasonDir.parent / "mcm_id__broken.dvdid.xml").write_text(
        "<Item />", encoding="utf-8"
    )
    (metadataDir / "After.Life.S01E04.Sic.Semper.Systema.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Item>
    <EpisodeID>10751471</EpisodeID>
    <EpisodeNumber>4</EpisodeNumber>
    <SeasonNumber>1</SeasonNumber>
    <EpisodeName>Sic Semper Systema</EpisodeName>
    <SeriesID>361563</SeriesID>
</Item>
""",
        encoding="utf-8",
    )
    episodeFile = seasonDir / "After.Life.S01E04.Sic.Semper.Systema.mkv"
    episodeFile.write_bytes(b"x" * 20)

    with patch.object(
        confirmedOrganizer,
        "_fetchTvMetadataFromScraper",
        side_effect=AssertionError("scraper lookup should not run"),
    ):
        with patch.object(
            confirmedOrganizer,
            "scanStorageLocations",
            return_value=([], [tvStorage]),
        ):
            with patch.object(
                confirmedOrganizer,
                "_getMetadataLibraryPath",
                return_value=tmp_path / "metadataLibrary.json",
            ):
                with caplog.at_level("INFO"):
                    stats = confirmedOrganizer.resetTvEpisodeTitles()

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert "<SeriesID>361563</SeriesID>" in (seasonDir.parent / "series.xml").read_text(
        encoding="utf-8"
    )
    assert "<SeriesID>361563</SeriesID>" in (
        seasonDir.parent / "mcm_id__broken.dvdid.xml"
    ).read_text(encoding="utf-8")
    assert f"update metadata: {seasonDir.parent / 'series.xml'}" in caplog.text
    assert (
        f"update metadata: {seasonDir.parent / 'mcm_id__broken.dvdid.xml'}"
        in caplog.text
    )
    assert "preserving existing metadata" not in caplog.text


def testVideoOrganizerDoesNotExposeGrokMethods(organizer: VideoOrganizer):
    """Grok helpers are retained separately and no longer exposed on VideoOrganizer."""
    assert not hasattr(organizer, "importFirefoxSession")
    assert not hasattr(organizer, "resetGrokConfig")
    assert not hasattr(organizer, "scrapeGrokSavedMedia")


def testGrokModuleRemainsImportableForFutureReuse():
    """The retained Grok implementation is still available as a separate module."""
    import organiseMyVideo.grok as grok_module

    assert hasattr(grok_module, "GrokMixin")


@pytest.mark.parametrize("flag", ["--grok", "--import-firefox-session"])
def testMainRejectsRemovedGrokOptions(flag: str, capsys):
    """The CLI no longer accepts the removed Grok integration flags."""
    with patch("sys.argv", ["organiseMyVideo", flag]):
        with pytest.raises(SystemExit) as exc_info:
            omv_main.main()

    assert exc_info.value.code == 2
    assert flag in capsys.readouterr().err


def testMainLogsStartupProgressBeforeProcessing(caplog: pytest.LogCaptureFixture):
    """CLI startup should log source/mode progress before processing begins."""
    organizerInstance = MagicMock()

    with patch(
        "organiseMyVideo.VideoOrganizer", return_value=organizerInstance
    ) as mockOrganizer:
        with patch(
            "sys.argv",
            ["organiseMyVideo", "--source", "/tmp/source"],
        ):
            with caplog.at_level("INFO"):
                omv_main.main()

    mockOrganizer.assert_called_once_with(
        sourceDir="/tmp/source",
        dryRun=True,
        refreshMetadataLibrary=False,
        useCurses=True,
    )
    organizerInstance.processFiles.assert_called_once_with(interactive=True)
    assert "source directory: /tmp/source" in caplog.text
    assert "mode: process" in caplog.text
    assert "initializing video organizer..." in caplog.text
    assert "...video organizer initialized" in caplog.text
    assert "running file organisation mode..." in caplog.text


def testMainPassesRefreshAndNoCursesFlagsToOrganizer():
    organizerInstance = MagicMock()

    with patch(
        "organiseMyVideo.VideoOrganizer", return_value=organizerInstance
    ) as mockOrganizer:
        with patch(
            "sys.argv",
            [
                "organiseMyVideo",
                "--source",
                "/tmp/source",
                "--refresh",
                "--no-curses",
            ],
        ):
            omv_main.main()

    mockOrganizer.assert_called_once_with(
        sourceDir="/tmp/source",
        dryRun=True,
        refreshMetadataLibrary=True,
        useCurses=False,
    )


def testMainAutoModeDisablesPromptsAndSetsSummaryPath():
    organizerInstance = MagicMock()

    with patch(
        "organiseMyVideo.VideoOrganizer", return_value=organizerInstance
    ) as mockOrganizer:
        with patch(
            "sys.argv",
            ["organiseMyVideo", "--source", "/tmp/source", "--auto"],
        ):
            omv_main.main()

    mockOrganizer.assert_called_once_with(
        sourceDir="/tmp/source",
        dryRun=True,
        refreshMetadataLibrary=False,
        useCurses=True,
    )
    assert organizerInstance.summaryReportPath == Path(
        "/tmp/source/organiseMyVideo-auto-summary.txt"
    )
    organizerInstance.processFiles.assert_called_once_with(interactive=False)


def testGetSummaryReportPathAddsIncrementWhenAutoSummaryExists(tmp_path: Path):
    sourceDir = tmp_path / "source"
    sourceDir.mkdir()
    (sourceDir / "organiseMyVideo-auto-summary.txt").write_text(
        "existing", encoding="utf-8"
    )

    assert omv_main._getSummaryReportPath(str(sourceDir), "process") == (
        sourceDir / "organiseMyVideo-auto-summary.01.txt"
    )


def testGetSummaryReportPathSkipsUsedAutoSummaryIncrements(tmp_path: Path):
    sourceDir = tmp_path / "source"
    sourceDir.mkdir()
    (sourceDir / "organiseMyVideo-auto-summary.txt").write_text(
        "existing", encoding="utf-8"
    )
    (sourceDir / "organiseMyVideo-auto-summary.01.txt").write_text(
        "existing", encoding="utf-8"
    )

    assert omv_main._getSummaryReportPath(str(sourceDir), "process") == (
        sourceDir / "organiseMyVideo-auto-summary.02.txt"
    )


def testMainRescanModeCallsResetTvEpisodeTitlesAndSetsSummaryPath():
    organizerInstance = MagicMock()

    with patch(
        "organiseMyVideo.VideoOrganizer", return_value=organizerInstance
    ) as mockOrganizer:
        with patch(
            "sys.argv",
            ["organiseMyVideo", "--source", "/tmp/source", "--rescan"],
        ):
            omv_main.main()

    mockOrganizer.assert_called_once_with(
        sourceDir="/tmp/source",
        dryRun=True,
        refreshMetadataLibrary=False,
        useCurses=True,
    )
    assert organizerInstance.summaryReportPath == Path(
        "/tmp/source/organiseMyVideo-rescan-summary.txt"
    )
    organizerInstance.resetTvEpisodeTitles.assert_called_once_with()
    organizerInstance.processFiles.assert_not_called()


def testGetSummaryReportPathAddsIncrementWhenRescanSummaryExists(tmp_path: Path):
    sourceDir = tmp_path / "source"
    sourceDir.mkdir()
    (sourceDir / "organiseMyVideo-rescan-summary.txt").write_text(
        "existing", encoding="utf-8"
    )

    assert omv_main._getSummaryReportPath(str(sourceDir), "rescan") == (
        sourceDir / "organiseMyVideo-rescan-summary.01.txt"
    )


def testMainConfiguresConsoleTimestampWithoutMilliseconds():
    organizerInstance = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizerInstance):
        with patch("sys.argv", ["organiseMyVideo", "--source", "/tmp/source"]):
            omv_main.main()

    consoleHandlers = [
        handler
        for handler in omv_main.logger.logger.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert consoleHandlers
    assert all(
        handler.formatter is not None
        and handler.formatter.datefmt == "%Y-%m-%d %H:%M:%S"
        for handler in consoleHandlers
    )


def testMainEnablesDebugLogging():
    organizerInstance = MagicMock()
    previousLevel = omv_main.logger.logger.level

    try:
        with patch("organiseMyVideo.VideoOrganizer", return_value=organizerInstance):
            with patch(
                "sys.argv",
                ["organiseMyVideo", "--source", "/tmp/source", "--debug"],
            ):
                omv_main.main()

        assert omv_main.logger.logger.level == logging.DEBUG
    finally:
        omv_main.logger.logger.setLevel(previousLevel)
