"""Tests for canonical TV show-folder article inversion."""

from pathlib import Path

from organiseMyVideo.filesystemOperations import FilesystemOperations
from organiseMyVideo.showFolders import (
    canonicalMovieFolderName,
    canonicalTvShowFolderName,
    normaliseMovieFolderNames,
    normaliseTvShowFolderNames,
    restoreLeadingThe,
)


def testCanonicalTvShowFolderNameMovesLeadingThe():
    assert canonicalTvShowFolderName("The Boys") == "Boys, The"
    assert canonicalTvShowFolderName("the office") == "office, The"
    assert canonicalTvShowFolderName("Boys, The") == "Boys, The"
    assert canonicalTvShowFolderName("Office, the") == "Office, The"
    assert canonicalTvShowFolderName("Breaking Bad") == "Breaking Bad"
    assert canonicalTvShowFolderName("The") == "The"
    assert restoreLeadingThe("Boys, The") == "The Boys"
    assert restoreLeadingThe("The Boys") == "The Boys"
    assert canonicalMovieFolderName("The Godfather (1972)") == "Godfather, The (1972)"
    assert canonicalMovieFolderName("Godfather, The (1972)") == "Godfather, The (1972)"
    assert canonicalMovieFolderName("Inception (2010)") == "Inception (2010)"


def testNormaliseRenamesLeadingTheShowFolder(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    oldShow = tvRoot / "The Boys"
    season = oldShow / "Season 1"
    season.mkdir(parents=True)
    episode = season / "The.Boys.S01E01.mkv"
    episode.write_bytes(b"episode")

    stats = normaliseTvShowFolderNames(
        [tvRoot],
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    newShow = tvRoot / "Boys, The"
    assert (newShow / "Season 1" / episode.name).read_bytes() == b"episode"
    assert not oldShow.exists()
    assert stats.renamed == 1
    assert stats.errors == 0


def testNormaliseMergesIntoExistingCanonicalShowFolder(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    canonical = tvRoot / "Boys, The" / "Season 1"
    source = tvRoot / "The Boys" / "Season 1"
    canonical.mkdir(parents=True)
    source.mkdir(parents=True)
    existing = canonical / "The.Boys.S01E01.mkv"
    unique = source / "The.Boys.S01E02.mkv"
    existing.write_bytes(b"one")
    unique.write_bytes(b"two")

    stats = normaliseTvShowFolderNames(
        [tvRoot],
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    assert (tvRoot / "Boys, The" / "Season 1" / unique.name).read_bytes() == b"two"
    assert existing.exists()
    assert not (tvRoot / "The Boys").exists()
    assert stats.renamed == 1


def testNormaliseDryRunLeavesLeadingTheFolder(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    oldShow = tvRoot / "The Boys"
    oldShow.mkdir(parents=True)
    (oldShow / "Season 1").mkdir()

    stats = normaliseTvShowFolderNames(
        [tvRoot],
        filesystem=FilesystemOperations(dryRun=True),
        dryRun=True,
    )

    assert oldShow.is_dir()
    assert not (tvRoot / "Boys, The").exists()
    assert stats.renamed == 1


def testNormaliseRenamesLeadingTheMovieFolder(tmp_path: Path):
    movieRoot = tmp_path / "movie1"
    oldFolder = movieRoot / "The Godfather (1972)"
    oldFolder.mkdir(parents=True)
    video = oldFolder / "The Godfather (1972).mkv"
    video.write_bytes(b"movie")

    stats = normaliseMovieFolderNames(
        [movieRoot],
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    newFolder = movieRoot / "Godfather, The (1972)"
    assert (newFolder / video.name).read_bytes() == b"movie"
    assert not oldFolder.exists()
    assert stats.renamed == 1
