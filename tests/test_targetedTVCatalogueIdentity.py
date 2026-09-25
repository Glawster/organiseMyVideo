"""Regression tests for catalogue-backed targeted TV scan matching."""

from pathlib import Path
from unittest.mock import patch

from organiseMyVideo import VideoOrganizer
from organiseMyVideo.mediaCatalogue import MediaCatalogue, TvSeriesCatalogueRecord


def testTargetedTvScanMatchesCatalogueIdentityAcrossStorageRoots(
    tmp_path: Path,
):
    """A targeted scan includes alias folders whose catalogue title matches."""
    sourceDir = tmp_path / "source"
    sourceDir.mkdir()
    organizer = VideoOrganizer(sourceDir=str(sourceDir), dryRun=False)

    firstRoot = tmp_path / "video2" / "TV"
    secondRoot = tmp_path / "video3" / "TV"
    firstShow = firstRoot / "Terminator The Sarah Connor Chronicles"
    secondShow = secondRoot / "Terminator SSC"
    (firstShow / "Season 01").mkdir(parents=True)
    (secondShow / "Season 01").mkdir(parents=True)
    (firstShow / "Season 01" / "Terminator.S01E01.Pilot.mkv").write_bytes(b"one")
    (secondShow / "Season 01" / "Terminator.S01E02.Gnothi.Seauton.mkv").write_bytes(
        b"two"
    )

    catalogueRows = [
        TvSeriesCatalogueRecord(
            showName="Terminator: The Sarah Connor Chronicles",
            folderPath=str(firstShow),
        ),
        TvSeriesCatalogueRecord(
            showName="Terminator: The Sarah Connor Chronicles",
            folderPath=str(secondShow),
        ),
    ]

    with (
        patch.object(MediaCatalogue, "catalogueTvSeriesList", return_value=catalogueRows),
        patch.object(organizer, "_shouldPromptInteractively", return_value=False),
        patch.object(organizer, "_resetTvEpisodeTitleForFile", return_value="skipped"),
        patch.object(
            organizer,
            "_maybeRenameResetTvShowFolder",
            side_effect=lambda _tvDir, showName, videoFiles: (showName, videoFiles),
        ),
    ):
        stats = organizer.resetTvEpisodeTitles(
            [firstRoot, secondRoot],
            showFilter="Terminator: The Sarah Connor Chronicles",
            deepScan=False,
        )

    assert stats == {"renamed": 0, "skipped": 2, "errors": 0}
