"""Tests for organiseMyVideo.py"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

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
# scanStorageLocations
# ---------------------------------------------------------------------------


def testScanStorageLocationsFindsMovieDirs(tmp_path: Path, organizer: VideoOrganizer):
    """movie<n> directories are detected as movie storage."""
    mnt = tmp_path / "mnt"
    (mnt / "movie1").mkdir(parents=True)
    (mnt / "movie2").mkdir(parents=True)
    with patch("organiseMyVideo.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert len(movieDirs) == 2
    assert len(videoDirs) == 0


def testScanStorageLocationsFindsMyPicturesAsMovieStorage(tmp_path: Path, organizer: VideoOrganizer):
    """/mnt/myPictures root is used as movie storage when no Movies subdir exists."""
    mnt = tmp_path / "mnt"
    (mnt / "myPictures").mkdir(parents=True)
    with patch("organiseMyVideo.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert any(d.name == "myPictures" for d in movieDirs)
    assert len(videoDirs) == 0


def testScanStorageLocationsUsesMyPicturesMoviesSubdir(tmp_path: Path, organizer: VideoOrganizer):
    """/mnt/myPictures/Movies is used as movie storage when the Movies subdir exists."""
    mnt = tmp_path / "mnt"
    (mnt / "myPictures" / "Movies").mkdir(parents=True)
    with patch("organiseMyVideo.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert any(d.name == "Movies" for d in movieDirs)
    assert len(videoDirs) == 0


def testScanStorageLocationsFindsMyVideoAsTvStorage(tmp_path: Path, organizer: VideoOrganizer):
    """/mnt/myVideo/TV is detected as TV storage."""
    mnt = tmp_path / "mnt"
    tvDir = mnt / "myVideo" / "TV"
    tvDir.mkdir(parents=True)
    with patch("organiseMyVideo.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert len(movieDirs) == 0
    assert any(d.name == "TV" for d in videoDirs)


def testScanStorageLocationsFindsAllLocationTypes(tmp_path: Path, organizer: VideoOrganizer):
    """movie<n>, myPictures, video<n>/TV, and myVideo/TV are all detected."""
    mnt = tmp_path / "mnt"
    (mnt / "movie1").mkdir(parents=True)
    (mnt / "myPictures").mkdir(parents=True)
    (mnt / "video1" / "TV").mkdir(parents=True)
    (mnt / "myVideo" / "TV").mkdir(parents=True)
    with patch("organiseMyVideo.Path") as mockPath:
        mockPath.return_value = mnt
        movieDirs, videoDirs = organizer.scanStorageLocations()
    assert len(movieDirs) == 2
    assert len(videoDirs) == 2


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
    assert stats["skipped"] == 2  # MovieA + MovieB/Sample (has direct video content)
    assert stats["errors"] == 0
    assert realDir.exists()
    assert not emptyDir.exists()
    assert not sampleDir.exists()


def testCleanEmptyFoldersRemovesNestedEmptyDir(sourceDir: Path, confirmedOrganizer: VideoOrganizer):
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


def testProcessFilesFindsVideoInSubdirectory(tmp_path: Path, confirmedOrganizer: VideoOrganizer):
    """Files inside a subdirectory of sourceDir are found and moved."""
    subDir = confirmedOrganizer.sourceDir / "One Mile (2026)"
    subDir.mkdir(parents=True)
    srcFile = subDir / "One.Mile.2026.1080p.WEBRip.x264.mp4"
    srcFile.write_bytes(b"x" * 100)

    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()

    with patch.object(confirmedOrganizer, "scanStorageLocations", return_value=([movieStorage], [tmp_path / "TV"])):
        with patch.object(confirmedOrganizer, "promptUserConfirmation",
                          return_value={"name": "One Mile (2026)", "type": "movie"}):
            confirmedOrganizer.processFiles(interactive=True)

    destFile = movieStorage / "One Mile (2026)" / "One.Mile.2026.1080p.WEBRip.x264.mp4"
    assert destFile.exists()
    assert not srcFile.exists()


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


# ---------------------------------------------------------------------------
# removeTorrentsInLibrary — dry-run mode
# ---------------------------------------------------------------------------


def testRemoveTorrentsInLibraryMissingDirReturnsZeroStats(organizer: VideoOrganizer, tmp_path: Path):
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
    (tvRoot / "The Office").mkdir(parents=True)

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

    assert not torrentFile.exists(), "prefixed torrent should be deleted when matched after prefix strip"
    assert stats["deleted"] == 1
    assert stats["errors"] == 0


# ---------------------------------------------------------------------------
# cleanTorrentNames — rename .torrent files by stripping site prefixes
# ---------------------------------------------------------------------------


def testCleanTorrentNamesMissingDirReturnsZeroStats(organizer: VideoOrganizer, tmp_path: Path):
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
    prefixedDir = downloadDir / "www.Torrenting.com - Silent.Witness.S28E09.720p.x265-TiPEX"
    prefixedDir.mkdir(parents=True)
    torrentFile = prefixedDir / "www.Torrenting.com - Silent.Witness.S28E09.720p.x265-TiPEX.torrent"
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


def testRemoveTorrentsInLibraryDeletesMatchingDownloadFolderWithPrefixedTorrent(tmp_path: Path):
    """Confirm mode: a matching download folder is removed when it contains a prefixed torrent."""
    downloadDir = tmp_path / "Download"
    prefixedDir = downloadDir / "www.UIndex.org    -    FBI Most Wanted S06E13 Greek Tragedy 1080p"
    prefixedDir.mkdir(parents=True)
    torrentFile = prefixedDir / "www.UIndex.org    -    FBI.Most.Wanted.S06E04.MULTi.1080p.WEB.x264-AMB3R.torrent"
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


def testExtractMediaUrlsFromHtmlFindsSupportedExtensions(organizer: VideoOrganizer):
    html = (
        '<img src="https://example.com/image01.png">'
        '<video src="https://example.com/clip01.mp4"></video>'
        '<a href="https://example.com/readme.txt">ignore</a>'
    )
    urls = organizer._extractMediaUrlsFromHtml(html)
    assert urls == ["https://example.com/clip01.mp4", "https://example.com/image01.png"]


def testExtractMediaUrlsFromPageFiltersToUserContentDomains(organizer: VideoOrganizer):
    """Only URLs from known Grok user-content CDN domains are returned."""
    userImage = "https://imagine-public.x.ai/imagine-public/images/abc123.png"
    userImageFromImagesPublic = "https://images-public.x.ai/xai-images-public/mj/images/def456.jpg"
    systemImage = "https://x.ai/images/news/grok-4-1.webp"
    promoVideo = "https://data.x.ai/grok-4-fast-side-by-side.mp4"
    nonMedia = "https://imagine-public.x.ai/imagine-public/images/page.html"

    fakePage = MagicMock()
    fakePage.eval_on_selector_all.return_value = [
        userImage,
        userImageFromImagesPublic,
        systemImage,
        promoVideo,
        nonMedia,
        "",
        None,
    ]

    urls = organizer._extractMediaUrlsFromPage(fakePage)

    assert userImage in urls
    assert userImageFromImagesPublic in urls
    assert systemImage not in urls
    assert promoVideo not in urls
    assert nonMedia not in urls


# ---------------------------------------------------------------------------
# _collectPostUrls
# ---------------------------------------------------------------------------


def testCollectPostUrlsExtractsPostLinks(organizer: VideoOrganizer):
    """Links matching /imagine/post/ are extracted from the page DOM."""
    post1 = "https://grok.com/imagine/post/9a826579-a4c4-4b44-b29c-e2a20d316c92"
    post2 = "https://grok.com/imagine/post/1b2c3d4e-0000-1111-2222-333344445555"

    fakePage = MagicMock()
    # The CSS selector a[href*='/imagine/post/'] already excludes non-post hrefs;
    # the mock returns only what the selector would yield.
    fakePage.eval_on_selector_all.return_value = [post1, post2, ""]

    urls = organizer._collectPostUrls(fakePage)

    assert post1 in urls
    assert post2 in urls
    assert "" not in urls
    assert len(urls) == 2
    fakePage.eval_on_selector_all.assert_called_once_with(
        "a[href*='/imagine/post/']",
        "els => els.map(el => el.href)",
    )


def testCollectPostUrlsDeduplicates(organizer: VideoOrganizer):
    """Duplicate hrefs (same post linked twice on the gallery page) are collapsed."""
    post = "https://grok.com/imagine/post/9a826579-a4c4-4b44-b29c-e2a20d316c92"

    fakePage = MagicMock()
    fakePage.eval_on_selector_all.return_value = [post, post, post]

    urls = organizer._collectPostUrls(fakePage)

    assert urls == [post]


def testCollectPostUrlsReturnsEmptyWhenNoLinks(organizer: VideoOrganizer):
    """An empty gallery page yields an empty list without raising."""
    fakePage = MagicMock()
    fakePage.eval_on_selector_all.return_value = []

    assert organizer._collectPostUrls(fakePage) == []


def testIsGrokMediaResponseMatchesByExtension(organizer: VideoOrganizer):
    """Media extension in URL path is sufficient when the host is a known user-content CDN."""
    for domain in ("imagine-public.x.ai", "images-public.x.ai"):
        assert organizer._isGrokMediaResponse(f"https://{domain}/user/abc.png", "")
        assert organizer._isGrokMediaResponse(f"https://{domain}/user/abc.jpg", "")
        assert organizer._isGrokMediaResponse(f"https://{domain}/user/abc.mp4", "")
        assert organizer._isGrokMediaResponse(f"https://{domain}/user/abc.webp", "")
        assert not organizer._isGrokMediaResponse(f"https://{domain}/user/abc.js", "")
        assert not organizer._isGrokMediaResponse(f"https://{domain}/user/abc.html", "")


def testIsGrokMediaResponseMatchesByContentType(organizer: VideoOrganizer):
    """image/* and video/* content-types are captured from known user-content CDN domains."""
    for domain in ("imagine-public.x.ai", "images-public.x.ai"):
        assert organizer._isGrokMediaResponse(f"https://{domain}/image", "image/png")
        assert organizer._isGrokMediaResponse(f"https://{domain}/image", "image/jpeg")
        assert organizer._isGrokMediaResponse(f"https://{domain}/video", "video/mp4")
        assert organizer._isGrokMediaResponse(f"https://{domain}/video", "video/webm")
        assert not organizer._isGrokMediaResponse(f"https://{domain}/api", "application/json")
        assert not organizer._isGrokMediaResponse(f"https://{domain}/js", "text/javascript")


def testIsGrokMediaResponseExcludesGrokComDomain(organizer: VideoOrganizer):
    """Responses from grok.com itself are never captured — it is not a user-content CDN."""
    assert not organizer._isGrokMediaResponse("https://grok.com/images/logo.png", "image/png")
    assert not organizer._isGrokMediaResponse("https://www.grok.com/promo.jpg", "image/jpeg")
    assert not organizer._isGrokMediaResponse("https://grok.com/clip.mp4", "video/mp4")


def testIsGrokMediaResponseExcludesUnknownCdnDomains(organizer: VideoOrganizer):
    """Images from third-party or unknown CDN domains are excluded by the allowlist."""
    # Profile pictures, analytics pixels, ad networks, etc. must all be rejected.
    assert not organizer._isGrokMediaResponse("https://cdn.example.ai/user/abc.png", "image/png")
    assert not organizer._isGrokMediaResponse("https://pbs.twimg.com/profile_img/photo.jpg", "image/jpeg")
    assert not organizer._isGrokMediaResponse("https://ads.tracker.com/pixel.gif", "image/gif")
    # Only the known user-content CDN domain should pass through.
    assert organizer._isGrokMediaResponse("https://imagine-public.x.ai/user/abc.png", "image/png")


def testDownloadMediaFilesDryRunDoesNotWrite(organizer: VideoOrganizer, tmp_path: Path):
    destDir = tmp_path / "Downloads" / "Grok"
    with patch("organiseMyVideo.Path.home", return_value=tmp_path):
        stats = organizer._downloadMediaFiles(["https://example.com/image01.png"])
    assert stats == {"downloaded": 1, "skipped": 0, "errors": 0}
    assert not (destDir / "image01.png").exists()


def testDownloadMediaFilesSkipsExisting(confirmedOrganizer: VideoOrganizer, tmp_path: Path):
    destDir = tmp_path / "Downloads" / "Grok"
    destDir.mkdir(parents=True)
    target = destDir / "image01.png"
    target.write_bytes(b"exists")
    with patch("organiseMyVideo.Path.home", return_value=tmp_path):
        stats = confirmedOrganizer._downloadMediaFiles(["https://example.com/image01.png"])
    assert stats == {"downloaded": 0, "skipped": 1, "errors": 0}


def testDownloadMediaFilesUsesPlaywrightContext(confirmedOrganizer: VideoOrganizer, tmp_path: Path):
    """When a playwright context is supplied the authenticated request path is used."""
    fakeResponse = MagicMock()
    fakeResponse.ok = True
    fakeResponse.body.return_value = b"image-data"

    fakeContext = MagicMock()
    fakeContext.request.get.return_value = fakeResponse

    with patch("organiseMyVideo.Path.home", return_value=tmp_path):
        stats = confirmedOrganizer._downloadMediaFiles(
            ["https://example.com/image01.png"], playwrightContext=fakeContext
        )

    assert stats == {"downloaded": 1, "skipped": 0, "errors": 0}
    fakeContext.request.get.assert_called_once_with(
        "https://example.com/image01.png", headers={"Referer": "https://grok.com/"}
    )
    assert (tmp_path / "Downloads" / "Grok" / "image01.png").read_bytes() == b"image-data"


def testDownloadMediaFilesPlaywrightContextNonOkResponse(confirmedOrganizer: VideoOrganizer, tmp_path: Path):
    """A non-OK playwright response is counted as an error."""
    fakeResponse = MagicMock()
    fakeResponse.ok = False
    fakeResponse.status = 403

    fakeContext = MagicMock()
    fakeContext.request.get.return_value = fakeResponse

    with patch("organiseMyVideo.Path.home", return_value=tmp_path):
        stats = confirmedOrganizer._downloadMediaFiles(
            ["https://example.com/image01.png"], playwrightContext=fakeContext
        )

    assert stats == {"downloaded": 0, "skipped": 0, "errors": 1}


# ---------------------------------------------------------------------------
# _loadOrPromptGrokCredentials
# ---------------------------------------------------------------------------


def testLoadOrPromptGrokCredentialsLoadsFromFile(organizer: VideoOrganizer, tmp_path: Path):
    """Existing credentials file is read without prompting the user."""
    credFile = tmp_path / "grokCredentials.json"
    credFile.write_text(json.dumps({"username": "user@example.com", "password": "s3cr3t"}))

    username, password = organizer._loadOrPromptGrokCredentials(credentialsFile=credFile)

    assert username == "user@example.com"
    assert password == "s3cr3t"


def testLoadOrPromptGrokCredentialsPromptsAndSavesWhenFileMissing(
    organizer: VideoOrganizer, tmp_path: Path
):
    """When no credentials file exists, the user is prompted and the result is saved."""
    credFile = tmp_path / "sub" / "grokCredentials.json"

    with patch("builtins.input", return_value="user@example.com"), patch(
        "getpass.getpass", return_value="s3cr3t"
    ):
        username, password = organizer._loadOrPromptGrokCredentials(credentialsFile=credFile)

    assert username == "user@example.com"
    assert password == "s3cr3t"
    assert credFile.exists()
    saved = json.loads(credFile.read_text())
    assert saved["username"] == "user@example.com"
    assert saved["password"] == "s3cr3t"


def testLoadOrPromptGrokCredentialsPromptsWhenFileIncomplete(
    organizer: VideoOrganizer, tmp_path: Path
):
    """A credentials file missing the password triggers a fresh prompt."""
    credFile = tmp_path / "grokCredentials.json"
    credFile.write_text(json.dumps({"username": "user@example.com", "password": ""}))

    with patch("builtins.input", return_value="user@example.com"), patch(
        "getpass.getpass", return_value="newpass"
    ):
        username, password = organizer._loadOrPromptGrokCredentials(credentialsFile=credFile)

    assert password == "newpass"
    saved = json.loads(credFile.read_text())
    assert saved["password"] == "newpass"


# ---------------------------------------------------------------------------
# _autofillLoginPage
# ---------------------------------------------------------------------------


def testAutofillLoginPageFillsEmailOnly(organizer: VideoOrganizer):
    """Only the email field is filled — Next click and password are left for the user
    so that Cloudflare Turnstile sees a real human interaction."""
    fakePage = MagicMock()
    organizer._autofillLoginPage(fakePage, "user@example.com")

    # page.fill(selector, value) — check the value argument (index 1) of each call
    filled_values = [call.args[1] for call in fakePage.fill.call_args_list]
    assert "user@example.com" in filled_values, "email not filled"
    assert "s3cr3t" not in filled_values, "password must not be filled automatically"
    # Next/submit button must NOT be clicked automatically
    fakePage.click.assert_not_called()


def testAutofillLoginPageFallsBackGracefullyOnError(organizer: VideoOrganizer):
    """A timeout or missing selector is caught and does not propagate."""
    fakePage = MagicMock()
    fakePage.wait_for_selector.side_effect = Exception("timeout waiting for selector")
    # Should not raise
    organizer._autofillLoginPage(fakePage, "u@e.com")


# ---------------------------------------------------------------------------
# scrapeGrokSavedMedia — session file behaviour
# ---------------------------------------------------------------------------


def testScrapeGrokSavedMediaUsesSessionFileWhenPresent(
    confirmedOrganizer: VideoOrganizer, tmp_path: Path
):
    """When a session file exists the browser context is initialised from it
    and the login form automation code is never reached."""
    sessionFile = tmp_path / "grokSession.json"
    sessionFile.write_text("{}")  # minimal valid storage-state

    fakePage = MagicMock()
    fakePage.url = "https://grok.com/imagine/saved"  # valid session → stays on saved page
    fakePage.eval_on_selector_all.return_value = []  # empty gallery → 0 posts

    fakeContext = MagicMock()
    fakeContext.new_page.return_value = fakePage
    fakeContext.storage_state.return_value = None

    fakeBrowser = MagicMock()
    fakeBrowser.new_context.return_value = fakeContext

    fakePW = MagicMock()
    fakePW.chromium.launch.return_value = fakeBrowser

    with patch("organiseMyVideo.sync_playwright") as mockPW:
        mockPW.return_value.__enter__.return_value = fakePW
        stats = confirmedOrganizer.scrapeGrokSavedMedia(sessionFile=sessionFile)

    # new_context must have been called with storage_state, not with credentials
    call_kwargs = fakeBrowser.new_context.call_args
    assert call_kwargs is not None
    assert "storage_state" in call_kwargs.kwargs
    assert call_kwargs.kwargs["storage_state"] == str(sessionFile)
    assert stats["postsFound"] == 0


def testScrapeGrokSavedMediaSavesSessionAfterLogin(
    confirmedOrganizer: VideoOrganizer, tmp_path: Path
):
    """When no session file exists the browser is relaunched non-headless,
    the email is pre-filled via _autofillLoginPage, and storage_state()
    persists the session."""
    sessionFile = tmp_path / "new_session.json"
    credFile = tmp_path / "grokCredentials.json"
    credFile.write_text(json.dumps({"username": "user@example.com", "password": "s3cr3t"}))
    assert not sessionFile.exists()

    fakePage = MagicMock()
    fakePage.url = "https://grok.com/imagine/saved"  # successful login → stays on saved page
    fakePage.eval_on_selector_all.return_value = []

    fakeContext = MagicMock()
    fakeContext.new_page.return_value = fakePage
    fakeContext.storage_state.return_value = None

    fakeBrowser = MagicMock()
    fakeBrowser.new_context.return_value = fakeContext

    fakePW = MagicMock()
    fakePW.chromium.launch.return_value = fakeBrowser

    with (
        patch("organiseMyVideo.sync_playwright") as mockPW,
        patch("builtins.input", return_value=""),  # simulate user pressing Enter
    ):
        mockPW.return_value.__enter__.return_value = fakePW
        confirmedOrganizer.scrapeGrokSavedMedia(
            sessionFile=sessionFile, credentialsFile=credFile
        )

    # The browser should have been relaunched non-headless for manual login
    launch_calls = fakePW.chromium.launch.call_args_list
    assert any(
        c.kwargs.get("headless") is False for c in launch_calls
    ), "expected at least one non-headless browser launch for manual login"

    # Only email should have been pre-filled; password is left for the user
    filled_values = [call.args[1] for call in fakePage.fill.call_args_list]
    assert "user@example.com" in filled_values, "email not filled"
    assert "s3cr3t" not in filled_values, "password must not be filled automatically"

    # storage_state should have been called (at least once) to save the session
    assert fakeContext.storage_state.called
    saved_paths = [
        call.kwargs.get("path") or (call.args[0] if call.args else None)
        for call in fakeContext.storage_state.call_args_list
    ]
    assert str(sessionFile) in saved_paths


# ---------------------------------------------------------------------------
# resetGrokConfig
# ---------------------------------------------------------------------------


def testResetGrokConfigDeletesBothFiles(confirmedOrganizer: VideoOrganizer, tmp_path: Path):
    """Both session and credentials files are deleted when they exist."""
    sessionFile = tmp_path / "grokSession.json"
    credFile = tmp_path / "grokCredentials.json"
    sessionFile.write_text("{}")
    credFile.write_text(json.dumps({"username": "u", "password": "p"}))

    result = confirmedOrganizer.resetGrokConfig(sessionFile=sessionFile, credentialsFile=credFile)

    assert not sessionFile.exists()
    assert not credFile.exists()
    assert str(sessionFile) in result["deleted"]
    assert str(credFile) in result["deleted"]
    assert result["notFound"] == []


def testResetGrokConfigReportsNotFoundWhenFilesAbsent(confirmedOrganizer: VideoOrganizer, tmp_path: Path):
    """Files that don't exist are reported in notFound, nothing is deleted."""
    sessionFile = tmp_path / "grokSession.json"
    credFile = tmp_path / "grokCredentials.json"

    result = confirmedOrganizer.resetGrokConfig(sessionFile=sessionFile, credentialsFile=credFile)

    assert result["deleted"] == []
    assert str(sessionFile) in result["notFound"]
    assert str(credFile) in result["notFound"]


def testResetGrokConfigDryRunDoesNotDelete(organizer: VideoOrganizer, tmp_path: Path):
    """In dry-run mode the files are NOT deleted but are reported as deleted."""
    sessionFile = tmp_path / "grokSession.json"
    credFile = tmp_path / "grokCredentials.json"
    sessionFile.write_text("{}")
    credFile.write_text(json.dumps({"username": "u", "password": "p"}))

    result = organizer.resetGrokConfig(sessionFile=sessionFile, credentialsFile=credFile)

    # Files must still exist in dry-run mode
    assert sessionFile.exists()
    assert credFile.exists()
    # But they are still reported in the deleted list (dry-run shows what would happen)
    assert str(sessionFile) in result["deleted"]
    assert str(credFile) in result["deleted"]


def testResetGrokConfigDeletesOnlyExistingFiles(confirmedOrganizer: VideoOrganizer, tmp_path: Path):
    """Only the session file exists — only it is deleted; credentials go to notFound."""
    sessionFile = tmp_path / "grokSession.json"
    credFile = tmp_path / "grokCredentials.json"
    sessionFile.write_text("{}")

    result = confirmedOrganizer.resetGrokConfig(sessionFile=sessionFile, credentialsFile=credFile)

    assert not sessionFile.exists()
    assert str(sessionFile) in result["deleted"]
    assert str(credFile) in result["notFound"]
