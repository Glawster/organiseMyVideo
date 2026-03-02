"""Tests for organiseMyVideo.py"""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

# conftest.py stubs organiseMyProjects before this import
import organiseMyVideo as omv
from organiseMyVideo import VideoOrganizer


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


# ---------------------------------------------------------------------------
# parseTvFilename
# ---------------------------------------------------------------------------


def testParseTvFilenameValid(organizer: VideoOrganizer):
    result = organizer.parseTvFilename("Breaking.Bad.S01E01.Pilot.mkv")
    assert result is not None
    assert result["showName"] == "Breaking Bad"
    assert result["season"] == 1
    assert result["episode"] == 1
    assert result["type"] == "tv"


def testParseTvFilenameHighSeasonEpisode(organizer: VideoOrganizer):
    result = organizer.parseTvFilename("The.Office.S12E25.Finale.mkv")
    assert result is not None
    assert result["showName"] == "The Office"
    assert result["season"] == 12
    assert result["episode"] == 25


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


def testFindExistingTvShowDirNotFound(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    result = organizer.findExistingTvShowDir("Breaking Bad", [tvRoot])
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


def testCleanEmptyFoldersDryRunDoesNotRemove(sourceDir: Path, organizer: VideoOrganizer):
    emptyDir = sourceDir / "EmptyDir"
    emptyDir.mkdir()
    stats = organizer.cleanEmptyFolders()
    assert emptyDir.exists(), "dry-run must not remove the folder"
    assert stats["removed"] == 1
    assert stats["errors"] == 0


def testCleanEmptyFoldersDryRunKeepsRealContent(sourceDir: Path, organizer: VideoOrganizer):
    realDir = sourceDir / "MovieA"
    realDir.mkdir()
    (realDir / "MovieA.mkv").write_bytes(b"x" * 100)
    stats = organizer.cleanEmptyFolders()
    assert realDir.exists()
    assert stats["skipped"] == 1
    assert stats["removed"] == 0


def testCleanEmptyFoldersDryRunSampleOnlyCountedAsRemoved(sourceDir: Path, organizer: VideoOrganizer):
    sampleDir = sourceDir / "MovieB"
    (sampleDir / "Sample").mkdir(parents=True)
    (sampleDir / "Sample" / "sample.mkv").write_bytes(b"x" * 50)
    stats = organizer.cleanEmptyFolders()
    assert sampleDir.exists(), "dry-run must not remove sample-only folder"
    assert stats["removed"] == 1


# ---------------------------------------------------------------------------
# cleanEmptyFolders — confirm mode (actual removal)
# ---------------------------------------------------------------------------


def testCleanEmptyFoldersRemovesEmptyDir(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    emptyDir = sourceDir / "EmptyDir"
    emptyDir.mkdir()
    stats = confirmedOrganizer.cleanEmptyFolders()
    assert not emptyDir.exists()
    assert stats["removed"] == 1


def testCleanEmptyFoldersRemovesSampleOnlyDir(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    sampleDir = sourceDir / "MovieB"
    (sampleDir / "Sample").mkdir(parents=True)
    (sampleDir / "Sample" / "sample.mkv").write_bytes(b"x" * 50)
    stats = confirmedOrganizer.cleanEmptyFolders()
    assert not sampleDir.exists()
    assert stats["removed"] == 1


def testCleanEmptyFoldersKeepsRealContentDir(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
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
    assert stats["skipped"] == 1
    assert stats["errors"] == 0
    assert realDir.exists()
    assert not emptyDir.exists()
    assert not sampleDir.exists()


# ---------------------------------------------------------------------------
# moveMovie — dry-run
# ---------------------------------------------------------------------------


def testMoveMovieDryRunReturnsTrueWithoutMoving(tmp_path: Path, organizer: VideoOrganizer):
    srcFile = organizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    movieInfo = {"title": "Inception", "year": "2010", "extension": ".mp4", "type": "movie"}

    with patch("organiseMyVideo.shutil.move") as mockMove:
        result = organizer.moveMovie(srcFile, movieInfo, [movieStorage], interactive=False)

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

    movieInfo = {"title": "Inception", "year": "2010", "extension": ".mp4", "type": "movie"}
    result = confirmedOrganizer.moveMovie(srcFile, movieInfo, [movieStorage], interactive=False)

    assert result is True
    destFile = movieStorage / "Inception (2010)" / "Inception (2010).mp4"
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveMovieUsesExistingDir(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    existingDir = movieStorage / "Inception (2010)"
    existingDir.mkdir(parents=True)

    movieInfo = {"title": "Inception", "year": "2010", "extension": ".mp4", "type": "movie"}
    result = confirmedOrganizer.moveMovie(srcFile, movieInfo, [movieStorage], interactive=False)

    assert result is True
    assert (existingDir / "Inception (2010).mp4").exists()


def testMoveMovieNoStorageReturnsFalse(organizer: VideoOrganizer):
    srcFile = organizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieInfo = {"title": "Inception", "year": "2010", "extension": ".mp4", "type": "movie"}
    # Pass no storage dirs and disable dry-run so it reaches the "no storage" branch
    org = VideoOrganizer(sourceDir=str(organizer.sourceDir), dryRun=False)
    result = org.moveMovie(srcFile, movieInfo, [], interactive=False)
    assert result is False


# ---------------------------------------------------------------------------
# moveTvShow — dry-run
# ---------------------------------------------------------------------------


def testMoveTvShowDryRunReturnsTrueWithoutMoving(tmp_path: Path, organizer: VideoOrganizer):
    srcFile = organizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1,
              "extension": ".mkv", "type": "tv"}

    with patch("organiseMyVideo.shutil.move") as mockMove:
        result = organizer.moveTvShow(srcFile, tvInfo, [tvStorage], interactive=False)

    assert result is True
    mockMove.assert_not_called()
    assert srcFile.exists()


# ---------------------------------------------------------------------------
# moveTvShow — confirm mode
# ---------------------------------------------------------------------------


def testMoveTvShowConfirmMovesFile(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)

    tvStorage = tmp_path / "video1" / "TV"
    tvStorage.mkdir(parents=True)

    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1,
              "extension": ".mkv", "type": "tv"}
    result = confirmedOrganizer.moveTvShow(srcFile, tvInfo, [tvStorage], interactive=False)

    assert result is True
    destFile = tvStorage / "Breaking Bad" / "Season 01" / "Breaking.Bad.S01E01.Pilot.mkv"
    assert destFile.exists()
    assert not srcFile.exists()


def testMoveTvShowNoStorageReturnsFalse(confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1,
              "extension": ".mkv", "type": "tv"}
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
        result = organizer.promptUserConfirmation("file.mkv", "Inception (2010)", "movie")
    assert result == {"name": "Breaking Bad", "type": "tv"}


def testPromptUserConfirmationTDefaultsToCurrentName(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["t", ""]):
        result = organizer.promptUserConfirmation("file.mkv", "Inception (2010)", "movie")
    assert result == {"name": "Inception (2010)", "type": "tv"}


def testPromptUserConfirmationMSwitchesToMovie(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["m", "Inception"]):
        result = organizer.promptUserConfirmation("file.mkv", "Breaking Bad", "tv")
    assert result == {"name": "Inception", "type": "movie"}


def testPromptUserConfirmationMDefaultsToCurrentName(organizer: VideoOrganizer):
    with patch("builtins.input", side_effect=["m", ""]):
        result = organizer.promptUserConfirmation("file.mkv", "Breaking Bad", "tv")
    assert result == {"name": "Breaking Bad", "type": "movie"}


# ---------------------------------------------------------------------------
# moveMovie — skip and type-switch via promptUserConfirmation
# ---------------------------------------------------------------------------


def testMoveMovieUsesDefaultWhenUserEntersBlank(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Inception (2010).mp4"
    srcFile.write_bytes(b"x" * 100)
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    movieInfo = {"title": "Inception", "year": "2010", "extension": ".mp4", "type": "movie"}
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
    movieInfo = {"title": "Inception", "year": "2010", "extension": ".mp4", "type": "movie"}
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


def testMoveTvShowUsesDefaultWhenUserEntersBlank(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "tv1"
    tvStorage.mkdir()
    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1,
              "extension": ".mkv", "type": "tv"}
    with patch("builtins.input", side_effect=["n", ""]):
        result = confirmedOrganizer.moveTvShow(srcFile, tvInfo, [tvStorage])
    assert result is True
    assert not srcFile.exists()
    destFile = tvStorage / "Breaking Bad" / "Season 01" / "Breaking.Bad.S01E01.Pilot.mkv"
    assert destFile.exists()


def testMoveTvShowSwitchesToMovie(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    srcFile = confirmedOrganizer.sourceDir / "Breaking.Bad.S01E01.Pilot.mkv"
    srcFile.write_bytes(b"x" * 100)
    tvStorage = tmp_path / "tv1"
    tvStorage.mkdir()
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    tvInfo = {"showName": "Breaking Bad", "season": 1, "episode": 1,
              "extension": ".mkv", "type": "tv"}
    # user says 'm', enters movie title "Breaking Bad Movie", year 2013
    with patch("builtins.input", side_effect=["m", "Breaking Bad Movie", "2013"]):
        result = confirmedOrganizer.moveTvShow(
            srcFile, tvInfo, [tvStorage], movieDirs=[movieStorage]
        )
    assert result is True
    destFile = movieStorage / "Breaking Bad Movie (2013)" / "Breaking.Bad.S01E01.Pilot.mkv"
    assert destFile.exists()
    assert not srcFile.exists()


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


def testCleanNamesConfirmRenamesFolder(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    original = sourceDir / "www.UIndex.org - Some Movie (2020)"
    original.mkdir()
    stats = confirmedOrganizer.cleanNames()
    expected = sourceDir / "Some Movie (2020)"
    assert not original.exists()
    assert expected.exists()
    assert stats["renamed"] == 1
    assert stats["errors"] == 0


def testCleanNamesConfirmRenamesFile(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    original = sourceDir / "www.Torrenting.com - Great Show S01E01.mkv"
    original.write_bytes(b"x" * 50)
    stats = confirmedOrganizer.cleanNames()
    expected = sourceDir / "Great Show S01E01.mkv"
    assert not original.exists()
    assert expected.exists()
    assert stats["renamed"] == 1


def testCleanNamesConfirmCaseInsensitive(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
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


def testCleanNamesLeavesNonMatchingUntouched(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    keep = sourceDir / "Normal Movie (2019)"
    keep.mkdir()
    original = sourceDir / "www.UIndex.org - Prefixed Movie (2020)"
    original.mkdir()
    stats = confirmedOrganizer.cleanNames()
    assert keep.exists()
    assert stats["renamed"] == 1


def testCleanNamesSkippedCounterWhenResultIsEmpty(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
    """A name that is only the prefix should be skipped (stripped result is empty)."""
    prefixOnly = sourceDir / "www.UIndex.org - "
    prefixOnly.mkdir()
    stats = confirmedOrganizer.cleanNames()
    assert prefixOnly.exists(), "prefix-only folder must not be removed"
    assert stats["skipped"] == 1
    assert stats["renamed"] == 0
