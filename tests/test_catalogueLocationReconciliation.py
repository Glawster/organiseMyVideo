"""Regression tests for stale catalogue locations across mounted media roots."""

import os
import sqlite3
from pathlib import Path

import pytest

from organiseMyVideo.cli import _runMediaLocate
from organiseMyVideo.filesystemOperations import FilesystemOperations
from organiseMyVideo.mediaCatalogue import (
    LOCATION_STATES,
    MediaCatalogue,
    TvEpisodeCatalogueRecord,
    TvSeriesCatalogueRecord,
    catalogueSchemaApply,
)
from organiseMyVideo.mediaLocate import locateTvShow
from organiseMyVideo.mediaMerge import TvLibraryMerger
from organiseMyVideo.showFolders import normaliseTvShowFolderNames
from organiseMyVideo.tvLibraryScan import scanTvLibrary


def _show(root: Path, name: str) -> Path:
    """Create one TV show folder with a single episode file."""

    folder = root / name
    folder.mkdir(parents=True)
    (folder / f"{name}.S01E01.mkv").write_bytes(b"episode")
    return folder


def _movie(root: Path, name: str) -> Path:
    """Create one movie folder with a feature file."""

    folder = root / name
    folder.mkdir(parents=True)
    (folder / f"{name}.mkv").write_bytes(b"movie")
    return folder


def _states(catalogue: MediaCatalogue) -> dict[str, str]:
    """Return folder path to stored location state for every TV series row."""

    return {
        row.folderPath: row.locationState
        for row in catalogue.catalogueTvSeriesList(states=LOCATION_STATES)
    }


def testAuthoritativeScanMarksMissingLanternsStale(tmp_path: Path):
    video1 = tmp_path / "video1" / "TV"
    video2 = tmp_path / "video2" / "TV"
    removed = _show(video1, "Lanterns")
    live = _show(video2, "Lanterns")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [video1, video2])
    removed.joinpath(removed.name + ".S01E01.mkv").unlink()
    removed.rmdir()

    before = locateTvShow("Lanterns", catalogue=catalogue)
    catalogue.catalogueReplaceFromStorage([], [video1, video2])
    after = locateTvShow("Lanterns", catalogue=catalogue)
    visible = catalogue.catalogueTvSeriesList()
    episodes = catalogue.catalogueTvEpisodesList(states=LOCATION_STATES)

    assert {item.folderPath: item.state for item in before} == {
        str(removed): "unverified",
        str(live): "current",
    }
    assert {item.folderPath: item.state for item in after} == {
        str(live): "current",
        str(removed): "stale",
    }
    assert [item.folderPath for item in visible] == [str(live)]
    assert _states(catalogue)[str(removed)] == "stale"
    assert {row.filePath: row.locationState for row in episodes}[
        str(live / "Lanterns.S01E01.mkv")
    ] == "current"
    assert any(
        row.locationState == "stale" and row.seriesFolderPath == str(removed)
        for row in episodes
    )


def testLocateShowsLanternsStates(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    video1 = tmp_path / "video1" / "TV"
    video2 = tmp_path / "video2" / "TV"
    removed = _show(video1, "Lanterns")
    live = _show(video2, "Lanterns")
    catalogue = MediaCatalogue()
    catalogue.catalogueReplaceFromStorage([], [video1, video2])
    removed.joinpath("Lanterns.S01E01.mkv").unlink()
    removed.rmdir()
    catalogue.catalogueReplaceFromStorage([], [video1, video2])

    assert _runMediaLocate(["Lanterns"]) == 0
    output = capsys.readouterr().out

    assert output == (
        "TV: Lanterns\n" f"  {live}    current\n" f"  {removed}    stale\n"
    )


def testMergeDiscoveryIgnoresStaleLanternsFolder(tmp_path: Path):
    video1 = tmp_path / "video1" / "TV"
    video2 = tmp_path / "video2" / "TV"
    removed = _show(video1, "Lanterns")
    live = _show(video2, "Lanterns")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [video1, video2])
    removed.joinpath("Lanterns.S01E01.mkv").unlink()
    removed.rmdir()
    catalogue.catalogueReplaceFromStorage([], [video1, video2])

    found = [
        row.folderPath
        for row in scanTvLibrary([video1, video2]).catalogueTvSeriesList()
        if row.showName == "Lanterns"
    ]
    stale = TvSeriesCatalogueRecord(
        showName="Lanterns", folderPath=str(removed), tvdbId="100"
    )
    current = TvSeriesCatalogueRecord(
        showName="Lanterns", folderPath=str(live), tvdbId="100"
    )

    class PersistentCatalogue:
        def catalogueTvSeriesList(self, states=None):
            return [stale, current]

        def catalogueTvEpisodesList(self, states=None):
            return []

    stats = TvLibraryMerger(catalogue=PersistentCatalogue(), dryRun=True).merge()

    assert found == [str(live)]
    assert stats.groupsFound == 0


def testUnavailableRootDoesNotMarkItsLocationsStale(tmp_path: Path):
    mounted = tmp_path / "video2" / "TV"
    unmounted = tmp_path / "video1" / "TV"
    kept = _show(unmounted, "Lanterns")
    _show(mounted, "Other")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [unmounted, mounted])
    unmounted.rename(tmp_path / "video1-offline")

    catalogue.catalogueReplaceFromStorage([], [mounted, unmounted])

    assert _states(catalogue)[str(kept)] == "current"
    coverage = {
        (item.kind, item.rootPath): item.outcome
        for item in catalogue.catalogueCoverageList()
    }
    assert coverage[("tv", str(unmounted))] == "unavailable"
    assert coverage[("tv", str(mounted))] == "authoritative"
    assert locateTvShow("Lanterns", catalogue=catalogue)[0].state == "unverified"


def testUnscannedRootSurvivesAnEmptyDiscovery(tmp_path: Path):
    movieRoot = tmp_path / "movies"
    tvRoot = tmp_path / "TV"
    movie = _movie(movieRoot, "Lanterns (2026)")
    show = _show(tvRoot, "Lanterns")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([movieRoot], [tvRoot])

    catalogue.catalogueReplaceFromStorage([], [])

    assert [item.folderPath for item in catalogue.catalogueMoviesList()] == [str(movie)]
    assert [item.folderPath for item in catalogue.catalogueTvSeriesList()] == [
        str(show)
    ]


def testUnreadableRootDoesNotMarkItsLocationsStale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = tmp_path / "TV"
    show = _show(root, "Lanterns")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [root])
    original = Path.iterdir

    def guarded(self: Path):
        if self == root:
            raise OSError("root unlistable")
        return original(self)

    monkeypatch.setattr(Path, "iterdir", guarded)
    catalogue.catalogueReplaceFromStorage([], [root])

    assert _states(catalogue)[str(show)] == "current"
    assert catalogue.catalogueCoverageList()[0].outcome == "error"


def testAuthoritativeScanMarksMissingMovieStale(tmp_path: Path):
    firstRoot = tmp_path / "movie1"
    secondRoot = tmp_path / "movie2"
    removed = _movie(firstRoot, "Lanterns (2026)")
    live = _movie(secondRoot, "Lanterns (2026)")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([firstRoot, secondRoot], [])
    for child in removed.iterdir():
        child.unlink()
    removed.rmdir()

    catalogue.catalogueReplaceFromStorage([firstRoot, secondRoot], [])
    rows = catalogue.catalogueMoviesList(states=LOCATION_STATES)

    assert {row.folderPath: row.locationState for row in rows} == {
        str(live): "current",
        str(removed): "stale",
    }
    assert [row.folderPath for row in catalogue.catalogueMoviesList()] == [str(live)]


def testConfirmedShowRenameCarriesProviderIdentity(tmp_path: Path):
    root = tmp_path / "TV"
    show = _show(root, "The Lanterns")
    episode = show / "The Lanterns.S01E01.mkv"
    catalogue = MediaCatalogue()
    catalogue.catalogueReplaceFromStorage([], [root])
    with sqlite3.connect(catalogue.databasePath) as connection:
        connection.execute(
            "UPDATE tvSeries SET tvdbId = ? WHERE folderPath = ?",
            ("4242", str(show)),
        )
        connection.execute(
            "UPDATE tvEpisode SET tvdbEpisodeId = ? WHERE filePath = ?",
            ("episode-1", str(episode)),
        )

    normaliseTvShowFolderNames([root], dryRun=False)
    rows = catalogue.catalogueTvSeriesList(states=LOCATION_STATES)
    episodes = catalogue.catalogueTvEpisodesList(states=LOCATION_STATES)
    renamed = root / "Lanterns, The"

    assert {row.folderPath: (row.locationState, row.tvdbId) for row in rows} == {
        str(renamed): ("current", "4242"),
        str(show): ("stale", "4242"),
    }
    assert {
        row.filePath: (row.locationState, row.tvdbEpisodeId) for row in episodes
    } == {
        str(renamed / episode.name): ("current", "episode-1"),
        str(episode): ("stale", "episode-1"),
    }


def testConfirmedMergeCarriesEpisodeIdentity(tmp_path: Path):
    destination = tmp_path / "video1" / "TV" / "Lanterns" / "Season 1"
    source = tmp_path / "video2" / "TV" / "Lanterns" / "Season 1"
    destination.mkdir(parents=True)
    source.mkdir(parents=True)
    kept = destination / "Lanterns.S01E01.mkv"
    moved = source / "Lanterns.S01E02.mkv"
    kept.write_bytes(b"one")
    moved.write_bytes(b"two")
    destinationShow = destination.parent
    sourceShow = source.parent
    catalogue = MediaCatalogue()
    catalogue.catalogueReplaceFromStorage(
        [], [destinationShow.parent, sourceShow.parent]
    )
    with sqlite3.connect(catalogue.databasePath) as connection:
        catalogueSchemaApply(connection)
        connection.execute(
            "UPDATE tvEpisode SET tvdbEpisodeId = ? WHERE filePath = ?",
            ("episode-2", str(moved)),
        )

    class Stored:
        def catalogueTvSeriesList(self, states=None):
            return [
                TvSeriesCatalogueRecord(
                    showName="Lanterns", folderPath=str(destinationShow), tvdbId="7"
                ),
                TvSeriesCatalogueRecord(
                    showName="Lanterns", folderPath=str(sourceShow), tvdbId="7"
                ),
            ]

        def catalogueTvEpisodesList(self, states=None):
            return [
                TvEpisodeCatalogueRecord(
                    showName="Lanterns",
                    seriesFolderPath=str(destinationShow),
                    season=1,
                    episode=1,
                    episodeTitle=None,
                    filePath=str(kept),
                ),
                TvEpisodeCatalogueRecord(
                    showName="Lanterns",
                    seriesFolderPath=str(sourceShow),
                    season=1,
                    episode=2,
                    episodeTitle=None,
                    filePath=str(moved),
                    tvdbEpisodeId="episode-2",
                ),
            ]

    stats = TvLibraryMerger(
        catalogue=Stored(),
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    ).merge()
    episodes = catalogue.catalogueTvEpisodesList(states=LOCATION_STATES)
    movedTo = destination / moved.name

    assert stats.groupsMerged == 1
    assert movedTo.read_bytes() == b"two"
    assert {row.filePath: (row.locationState, row.tvdbEpisodeId) for row in episodes}[
        str(movedTo)
    ] == ("current", "episode-2")
    assert {row.filePath: row.locationState for row in episodes}[str(moved)] == "stale"


def testLocateRequiresSearch():
    with pytest.raises(SystemExit) as error:
        _runMediaLocate([])

    assert error.value.code == 2


def testUnifiedLocateFindsEachCataloguedShow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    root = tmp_path / "TV"
    lanterns = _show(root, "Lanterns")
    pitt = _show(root, "Pitt")
    catalogue = MediaCatalogue()
    catalogue.catalogueReplaceFromStorage([], [root])

    assert _runMediaLocate(["Lanterns"]) == 0
    assert capsys.readouterr().out == "TV: Lanterns\n" f"  {lanterns}    current\n"

    assert _runMediaLocate(["Pitt"]) == 0
    assert capsys.readouterr().out == "TV: Pitt\n" f"  {pitt}    current\n"


def testUnreadableShowSubtreeDoesNotMarkExistingEpisodesStale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An unread season is not evidence that its episodes have gone."""

    root = tmp_path / "TV"
    lanterns = root / "Lanterns"
    season = lanterns / "Season 1"
    readable = lanterns / "Season 2"
    season.mkdir(parents=True)
    readable.mkdir()
    kept = season / "Lanterns.S01E01.mkv"
    removedEpisode = readable / "Lanterns.S02E01.mkv"
    kept.write_bytes(b"one")
    removedEpisode.write_bytes(b"two")
    other = _show(root, "Pitt")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [root])
    removedEpisode.unlink()
    other.joinpath("Pitt.S01E01.mkv").unlink()
    other.rmdir()

    from organiseMyVideo import mediaCatalogue as catalogueModule

    realWalk = os.walk

    def guardedWalk(top, topdown=True, onerror=None, followlinks=False):
        if Path(top) != lanterns:
            yield from realWalk(top, topdown, onerror, followlinks)
            return
        # os.walk reports an unlistable directory through onerror and then
        # yields none of its files. Forgetting onerror swallows that error.
        if onerror is not None:
            onerror(OSError(13, "Permission denied", str(season)))
        for dirPath, dirNames, fileNames in realWalk(
            top, topdown, onerror, followlinks
        ):
            current = Path(dirPath)
            if current == season or season in current.parents:
                continue
            if current == lanterns:
                dirNames = [name for name in dirNames if name != season.name]
            yield dirPath, dirNames, fileNames

    monkeypatch.setattr(catalogueModule.os, "walk", guardedWalk)
    catalogue.catalogueReplaceFromStorage([], [root])
    episodes = {
        row.filePath: row.locationState
        for row in catalogue.catalogueTvEpisodesList(states=LOCATION_STATES)
    }

    assert episodes[str(kept)] == "current"
    assert episodes[str(removedEpisode)] == "stale"
    assert _states(catalogue) == {str(lanterns): "current", str(other): "stale"}


def testMergeReconcilesWhenNoGroupIsMerged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A merge that moves nothing still retires a folder its roots listed away."""

    from organiseMyVideo.mainLegacy import main
    from organiseMyVideo.mediaMerge import TvMergeStats

    video1 = tmp_path / "video1" / "TV"
    video2 = tmp_path / "video2" / "TV"
    removed = _show(video1, "Lanterns")
    _show(video2, "Lanterns")
    catalogue = MediaCatalogue()
    catalogue.catalogueReplaceFromStorage([], [video1, video2])
    removed.joinpath("Lanterns.S01E01.mkv").unlink()
    removed.rmdir()
    source = tmp_path / "toFile"
    source.mkdir()

    class Organizer:
        def __init__(self, **kwargs):
            self.sourceDir = Path(kwargs["sourceDir"])

        def scanStorageLocations(self):
            return ([], [video1, video2])

    monkeypatch.setattr("organiseMyVideo.VideoOrganizer", Organizer)
    monkeypatch.setattr(
        "organiseMyVideo.mediaMerge.mergeDuplicateTvShows",
        lambda **kwargs: TvMergeStats(),
    )
    monkeypatch.setattr(
        "organiseMyVideo.mediaMerge.mergeDuplicateMovies",
        lambda **kwargs: TvMergeStats(),
    )

    assert main(["media", "organise", "--merge", "--source", str(source)]) == 0
    assert _states(catalogue) == {
        str(removed): "stale",
        str(video2 / "Lanterns"): "current",
    }
