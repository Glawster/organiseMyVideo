"""Tests for cleanup of duplicate TV folders during targeted rescans."""

from pathlib import Path

from organiseMyVideo import VideoOrganizer


def testRescanMergeRemovesIdenticalCollisionAndEmptySource(tmp_path: Path):
    source = tmp_path / "Untamed 2025"
    destination = tmp_path / "Untamed"
    source.mkdir()
    destination.mkdir()
    (source / "backdrop.jpg").write_bytes(b"same artwork")
    (destination / "backdrop.jpg").write_bytes(b"same artwork")

    organizer = VideoOrganizer(sourceDir=str(tmp_path), dryRun=False, useCurses=False)
    organizer._mergeResetTvShowFolderContents(source, destination)

    assert not source.exists()
    assert (destination / "backdrop.jpg").read_bytes() == b"same artwork"
    assert any(
        "removed identical duplicate" in item
        for item in organizer._summaryCleanupTasks
    )


def testRescanMergeMovesUniqueFilesButPreservesRealConflict(tmp_path: Path):
    source = tmp_path / "Untamed 2025"
    destination = tmp_path / "Untamed"
    source.mkdir()
    destination.mkdir()
    (source / "banner.jpg").write_bytes(b"source banner")
    (destination / "banner.jpg").write_bytes(b"destination banner")
    (source / "episode.mkv").write_bytes(b"episode")

    organizer = VideoOrganizer(sourceDir=str(tmp_path), dryRun=False, useCurses=False)
    organizer._mergeResetTvShowFolderContents(source, destination)

    assert source.exists()
    assert (source / "banner.jpg").read_bytes() == b"source banner"
    assert (destination / "banner.jpg").read_bytes() == b"destination banner"
    assert not (source / "episode.mkv").exists()
    assert (destination / "episode.mkv").read_bytes() == b"episode"
    assert any("conflicts with existing" in item for item in organizer._summaryCleanupTasks)


def testRescanMergeCleansIdenticalFilesInsideSeasonFolders(tmp_path: Path):
    source = tmp_path / "Untamed 2025"
    destination = tmp_path / "Untamed"
    sourceSeason = source / "Season 01"
    destinationSeason = destination / "Season 01"
    sourceSeason.mkdir(parents=True)
    destinationSeason.mkdir(parents=True)
    (sourceSeason / "Untamed.S01E01.mkv").write_bytes(b"same episode")
    (destinationSeason / "Untamed.S01E01.mkv").write_bytes(b"same episode")

    organizer = VideoOrganizer(sourceDir=str(tmp_path), dryRun=False, useCurses=False)
    organizer._mergeResetTvShowFolderContents(source, destination)

    assert not source.exists()
    assert (destinationSeason / "Untamed.S01E01.mkv").exists()
