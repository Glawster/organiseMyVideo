"""Tests for canonical TV season-folder naming."""

from pathlib import Path

from organiseMyVideo.filesystemOperations import FilesystemOperations
from organiseMyVideo.seasonFolders import (
    canonicalSeasonFolderName,
    normaliseTvSeasonFolders,
)


def testCanonicalSeasonFolderNameRemovesLeadingZeroes():
    assert canonicalSeasonFolderName("Season 03") == "Season 3"
    assert canonicalSeasonFolderName("season 0007") == "Season 7"
    assert canonicalSeasonFolderName("Season 12") == "Season 12"
    assert canonicalSeasonFolderName("Specials") is None


def testNormaliseRenamesSeasonFolder(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    oldSeason = tvRoot / "Grimm" / "Season 03"
    oldSeason.mkdir(parents=True)
    episode = oldSeason / "Grimm S03E01.mkv"
    episode.write_bytes(b"episode")

    stats = normaliseTvSeasonFolders(
        [tvRoot],
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    newSeason = tvRoot / "Grimm" / "Season 3"
    assert newSeason.is_dir()
    assert (newSeason / episode.name).read_bytes() == b"episode"
    assert not oldSeason.exists()
    assert stats.renamed == 1
    assert stats.errors == 0


def testNormaliseMergesIntoExistingCanonicalSeasonWithoutOverwrite(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    show = tvRoot / "Grimm"
    oldSeason = show / "Season 03"
    canonical = show / "Season 3"
    oldSeason.mkdir(parents=True)
    canonical.mkdir(parents=True)
    unique = oldSeason / "Grimm S03E02.mkv"
    unique.write_bytes(b"two")
    existing = canonical / "Grimm S03E01.mkv"
    existing.write_bytes(b"one")

    stats = normaliseTvSeasonFolders(
        [tvRoot],
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    assert (canonical / unique.name).read_bytes() == b"two"
    assert existing.read_bytes() == b"one"
    assert not oldSeason.exists()
    assert stats.filesMoved == 1
    assert stats.renamed == 1
    assert stats.conflicts == 0


def testNormalisePreservesConflictingDestinationFile(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    show = tvRoot / "Grimm"
    oldSeason = show / "Season 03"
    canonical = show / "Season 3"
    oldSeason.mkdir(parents=True)
    canonical.mkdir(parents=True)
    source = oldSeason / "poster.jpg"
    destination = canonical / "poster.jpg"
    source.write_bytes(b"source")
    destination.write_bytes(b"destination")

    stats = normaliseTvSeasonFolders(
        [tvRoot],
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"destination"
    assert oldSeason.exists()
    assert stats.conflicts == 1


def testNormaliseDryRunPlansRenameWithoutChangingFolder(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    oldSeason = tvRoot / "Grimm" / "Season 03"
    oldSeason.mkdir(parents=True)
    filesystem = FilesystemOperations(dryRun=True)

    stats = normaliseTvSeasonFolders(
        [tvRoot],
        filesystem=filesystem,
        dryRun=True,
    )

    assert oldSeason.exists()
    assert not (oldSeason.parent / "Season 3").exists()
    assert stats.renamed == 1
    assert any(operation.action == "move" for operation in filesystem.operations)
