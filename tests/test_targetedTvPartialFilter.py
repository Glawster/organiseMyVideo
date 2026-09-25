"""Regression tests for partial targeted TV show scan filters."""

from unittest.mock import patch

import pytest

from organiseMyVideo import VideoOrganizer
from organiseMyVideo.mediaCatalogue import MediaCatalogue, TvSeriesCatalogueRecord


def testTargetedTvFilterMatchesLongShowName():
    organizer = VideoOrganizer()

    assert organizer._resetTvShowMatchesFilter(
        "Terminator The Sarah Connor Chronicles", "terminator"
    )


def testTargetedTvFilterMatchesAbbreviatedFolderName():
    organizer = VideoOrganizer()

    assert organizer._resetTvShowMatchesFilter("Terminator SSC", "terminator")


def testTargetedTvFilterRejectsUnrelatedShow():
    organizer = VideoOrganizer()

    assert not organizer._resetTvShowMatchesFilter("Lanterns", "terminator")


@pytest.mark.parametrize(
    "showFilter", ["Terminator: The Sarah Connor Chronicles", "terminator"]
)
def testTargetedTvSelectionSharesCatalogueFolders(tmp_path, showFilter):
    """Canonical aliases and physical matches share one selection across roots."""
    organizer = VideoOrganizer(sourceDir=str(tmp_path), dryRun=True)
    roots = [tmp_path / "video2" / "TV", tmp_path / "video3" / "TV"]
    shows = [roots[0] / "TSSC", roots[1] / "Sarah Connor"]
    physicalMatch = roots[0] / "Terminator The Sarah Connor Chronicles"
    # The same basename elsewhere must not inherit another folder's identity.
    unrelated = roots[0] / "Sarah Connor"
    episodes = []
    for show in [*shows, physicalMatch, unrelated]:
        show.mkdir(parents=True)
        episode = show / "episode.S01E01.mkv"
        episode.write_bytes(b"episode")
        episodes.append(episode)
    rows = [
        TvSeriesCatalogueRecord(
            showName="Terminator: The Sarah Connor Chronicles",
            folderPath=str(show.parent) + "//" + show.name + "/",
        )
        for show in shows
    ]
    rows.append(TvSeriesCatalogueRecord(showName="Lanterns", folderPath=str(unrelated)))

    with (
        patch.object(
            MediaCatalogue, "catalogueTvSeriesList", return_value=rows
        ) as lookup,
        patch.object(organizer, "_shouldPromptInteractively", return_value=False),
        patch.object(organizer, "_recordSummaryDuplicateTvShow") as duplicates,
        patch.object(
            organizer, "_resetTvEpisodeTitleForFile", return_value="skipped"
        ) as scan,
        patch.object(
            organizer,
            "_maybeRenameResetTvShowFolder",
            side_effect=lambda _root, name, files: (name, files),
        ),
    ):
        stats = organizer.resetTvEpisodeTitles(roots, showFilter=showFilter)

    lookup.assert_called_once_with()
    assert stats == {"renamed": 0, "skipped": 3, "errors": 0}
    assert {call.args[0] for call in scan.call_args_list} == set(episodes[:3])
    assert set(duplicates.call_args.args[1]) == {
        str(show) for show in [*shows, physicalMatch]
    }
