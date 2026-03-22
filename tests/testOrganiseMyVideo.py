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
# findBestMatchingTvShow
# ---------------------------------------------------------------------------


def testFindBestMatchingTvShowExactMatch(tmp_path: Path, organizer: VideoOrganizer):
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Breaking Bad").mkdir()
    result = organizer.findBestMatchingTvShow("Breaking Bad", [tvRoot])
    assert result == "Breaking Bad"


def testFindBestMatchingTvShowFuzzyMatchReturnsFolder(tmp_path: Path, organizer: VideoOrganizer):
    """Folder name is returned even when the parsed show name differs slightly."""
    tvRoot = tmp_path / "TV"
    tvRoot.mkdir()
    (tvRoot / "Law and Order Special Victims Unit").mkdir()
    # Simulates a parsed show name that omits the trailing word
    result = organizer.findBestMatchingTvShow("Law and Order Special Victims Unit", [tvRoot])
    assert result == "Law and Order Special Victims Unit"


def testFindBestMatchingTvShowCaseInsensitive(tmp_path: Path, organizer: VideoOrganizer):
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


def testPromptUserConfirmationTUsesMatchingTvFolderAsDefault(tmp_path: Path, organizer: VideoOrganizer):
    """When videoDirs is provided and a folder matches the parsed show name, use it as default."""
    tvDir = tmp_path / "TV"
    tvDir.mkdir()
    (tvDir / "Law and Order Special Victims Unit").mkdir()
    filename = "Law.and.Order.Special.Victims.Unit.S27E13.Corrosive.1080p.mkv"
    with patch("builtins.input", side_effect=["t", ""]):
        result = organizer.promptUserConfirmation(filename, "Law and Order Special Victims Unit S27E13 Corrosive (1080)", "movie", videoDirs=[tvDir])
    assert result == {"name": "Law and Order Special Victims Unit", "type": "tv"}


def testPromptUserConfirmationTFallsBackToDefaultWhenNoTvFolderMatch(tmp_path: Path, organizer: VideoOrganizer):
    """When videoDirs has no matching folder, fall back to the original defaultName."""
    tvDir = tmp_path / "TV"
    tvDir.mkdir()
    (tvDir / "Breaking Bad").mkdir()
    filename = "Law.and.Order.Special.Victims.Unit.S27E13.Corrosive.1080p.mkv"
    with patch("builtins.input", side_effect=["t", ""]):
        result = organizer.promptUserConfirmation(filename, "Law and Order Special Victims Unit S27E13 Corrosive (1080)", "movie", videoDirs=[tvDir])
    assert result == {"name": "Law and Order Special Victims Unit S27E13 Corrosive (1080)", "type": "tv"}


def testPromptUserConfirmationTUserCanOverrideSuggestedTvFolder(tmp_path: Path, organizer: VideoOrganizer):
    """User can override the suggested TV folder name by typing a custom name."""
    tvDir = tmp_path / "TV"
    tvDir.mkdir()
    (tvDir / "Law and Order Special Victims Unit").mkdir()
    filename = "Law.and.Order.Special.Victims.Unit.S27E13.Corrosive.1080p.mkv"
    with patch("builtins.input", side_effect=["t", "My Custom Show"]):
        result = organizer.promptUserConfirmation(filename, "Some Movie (2024)", "movie", videoDirs=[tvDir])
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
    with patch("builtins.input", return_value="y"), \
         patch("builtins.print") as mockPrint:
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
    with patch("builtins.input", return_value="y"), \
         patch("builtins.print") as mockPrint:
        organizer.promptUserConfirmation("file.mkv", "Show One", "tv")
        mockPrint.reset_mock()
        result = organizer.promptUserConfirmation("file.mkv", "Show Two", "tv")
    assert result == {"name": "Show Two", "type": "tv"}
    mockPrint.assert_not_called()


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
