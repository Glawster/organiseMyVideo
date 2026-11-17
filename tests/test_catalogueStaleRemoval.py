"""REQ-043 tests for removing stale locations and retiring dropped roots."""

import json
import shutil
from pathlib import Path

from organiseMyVideo import video as videoModule
from organiseMyVideo.mediaCatalogue import (
    LOCATION_STATES,
    MediaCatalogue,
    _removeStale,
)
from organiseMyVideo.video import VideoMixin

_MOVIE_KIND = frozenset({"movie"})
_TV_KIND = frozenset({"tv"})


def _movie(root: Path, name: str) -> Path:
    """Create one movie folder with a feature file."""

    folder = root / name
    folder.mkdir(parents=True)
    (folder / f"{name}.mkv").write_bytes(b"movie")
    return folder


def _show(root: Path, name: str) -> Path:
    """Create one TV show folder with a single episode file."""

    folder = root / name
    folder.mkdir(parents=True)
    (folder / f"{name}.S01E01.mkv").write_bytes(b"episode")
    return folder


def _catalogue(tmp_path: Path) -> MediaCatalogue:
    """Return an empty catalogue stored beneath the test directory."""

    return MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")


def _movieStates(catalogue: MediaCatalogue) -> dict[str, str]:
    """Return stored movie folder paths and their location states."""

    return {
        row.folderPath: row.locationState
        for row in catalogue.catalogueMoviesList(states=LOCATION_STATES)
    }


def _coverageRoots(catalogue: MediaCatalogue) -> set[str]:
    """Return every recorded storage root."""

    return {item.rootPath for item in catalogue.catalogueCoverageList()}


def testStaleLocationSurvivesOneScanThenIsRemoved(tmp_path: Path):
    root = tmp_path / "Movies"
    live = _movie(root, "Live (2020)")
    gone = _movie(root, "Gone (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([root], [])
    shutil.rmtree(gone)

    catalogue.catalogueReplaceFromStorage([root], [])
    assert _movieStates(catalogue) == {str(live): "current", str(gone): "stale"}

    catalogue.catalogueReplaceFromStorage([root], [])
    assert _movieStates(catalogue) == {str(live): "current"}


def testStaleLocationThatReturnsIsKept(tmp_path: Path):
    root = tmp_path / "Movies"
    folder = _movie(root, "Back (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([root], [])
    shutil.rmtree(folder)
    catalogue.catalogueReplaceFromStorage([root], [])
    _movie(root, "Back (2020)")

    catalogue.catalogueReplaceFromStorage([root], [])

    assert _movieStates(catalogue) == {str(folder): "current"}


def testStaleTvRowsAreRemovedOnTheNextScan(tmp_path: Path):
    root = tmp_path / "TV"
    live = _show(root, "Live")
    gone = _show(root, "Gone")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([], [root])
    shutil.rmtree(gone)
    catalogue.catalogueReplaceFromStorage([], [root])

    catalogue.catalogueReplaceFromStorage([], [root])

    series = catalogue.catalogueTvSeriesList(states=LOCATION_STATES)
    episodes = catalogue.catalogueTvEpisodesList(states=LOCATION_STATES)
    assert [row.folderPath for row in series] == [str(live)]
    assert [row.seriesFolderPath for row in episodes] == [str(live)]


def testStaleRowInWithheldDirectoryIsKept(tmp_path: Path):
    root = tmp_path / "TV"
    gone = _show(root, "Gone")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([], [root])
    shutil.rmtree(gone)
    catalogue.catalogueReplaceFromStorage([], [root])

    with catalogue._databaseConnect() as connection:
        removed = _removeStale(
            connection,
            "tvEpisode",
            "filePath",
            [root],
            extraPathColumn="seriesFolderPath",
            withheldRoots=[gone],
        )

    assert removed == 0


def testDroppedMissingRootIsRetiredThenRemoved(tmp_path: Path):
    oldRoot = tmp_path / "movie2" / "Movies"
    liveRoot = tmp_path / "raid" / "Movies"
    old = _movie(oldRoot, "Old (2020)")
    live = _movie(liveRoot, "Live (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([oldRoot, liveRoot], [])
    shutil.rmtree(oldRoot.parent)

    catalogue.catalogueReplaceFromStorage([liveRoot], [], retiredRootKinds=_MOVIE_KIND)
    assert _movieStates(catalogue) == {str(live): "current", str(old): "stale"}
    assert str(oldRoot) in _coverageRoots(catalogue)

    catalogue.catalogueReplaceFromStorage([liveRoot], [], retiredRootKinds=_MOVIE_KIND)
    assert _movieStates(catalogue) == {str(live): "current"}
    assert _coverageRoots(catalogue) == {str(liveRoot)}


def testRetiredTvRootRemovesSeriesAndEpisodes(tmp_path: Path):
    oldRoot = tmp_path / "video1" / "TV"
    liveRoot = tmp_path / "raid" / "TV"
    _show(oldRoot, "Old")
    live = _show(liveRoot, "Live")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([], [oldRoot, liveRoot])
    shutil.rmtree(oldRoot.parent)

    for _ in range(2):
        catalogue.catalogueReplaceFromStorage([], [liveRoot], retiredRootKinds=_TV_KIND)

    series = catalogue.catalogueTvSeriesList(states=LOCATION_STATES)
    episodes = catalogue.catalogueTvEpisodesList(states=LOCATION_STATES)
    assert [row.folderPath for row in series] == [str(live)]
    assert [row.seriesFolderPath for row in episodes] == [str(live)]


def testDiscoveredRootThatDisappearsIsNotRetired(tmp_path: Path):
    oldRoot = tmp_path / "movie2" / "Movies"
    liveRoot = tmp_path / "raid" / "Movies"
    old = _movie(oldRoot, "Old (2020)")
    live = _movie(liveRoot, "Live (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([oldRoot, liveRoot], [])
    shutil.rmtree(oldRoot.parent)

    for _ in range(3):
        catalogue.catalogueReplaceFromStorage([liveRoot], [])

    assert _movieStates(catalogue) == {str(live): "current", str(old): "current"}


def testConfiguredRootThatIsUnavailableIsNotRetired(tmp_path: Path):
    unmounted = tmp_path / "unmounted" / "Movies"
    liveRoot = tmp_path / "raid" / "Movies"
    old = _movie(unmounted, "Old (2020)")
    live = _movie(liveRoot, "Live (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([unmounted, liveRoot], [])
    shutil.rmtree(unmounted.parent)

    for _ in range(3):
        catalogue.catalogueReplaceFromStorage(
            [unmounted, liveRoot], [], retiredRootKinds=_MOVIE_KIND
        )

    assert _movieStates(catalogue) == {str(live): "current", str(old): "current"}


def testNoRootIsRetiredWhenNoConfiguredRootCouldBeListed(tmp_path: Path):
    oldRoot = tmp_path / "movie2" / "Movies"
    outage = tmp_path / "raid" / "Movies"
    old = _movie(oldRoot, "Old (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([oldRoot], [])
    shutil.rmtree(oldRoot.parent)

    catalogue.catalogueReplaceFromStorage([outage], [], retiredRootKinds=_MOVIE_KIND)

    assert _movieStates(catalogue) == {str(old): "current"}


def testRetiringMoviesLeavesTvRootsAlone(tmp_path: Path):
    tvRoot = tmp_path / "video1" / "TV"
    movieRoot = tmp_path / "raid" / "Movies"
    show = _show(tvRoot, "Show")
    _movie(movieRoot, "Live (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([movieRoot], [tvRoot])
    shutil.rmtree(tvRoot.parent)

    for _ in range(2):
        catalogue.catalogueReplaceFromStorage(
            [movieRoot], [], retiredRootKinds=_MOVIE_KIND
        )

    series = catalogue.catalogueTvSeriesList(states=LOCATION_STATES)
    assert {row.folderPath: row.locationState for row in series} == {
        str(show): "current"
    }


def testDroppedRootThatStillExistsLosesOnlyItsStaleRows(tmp_path: Path):
    droppedRoot = tmp_path / "myVideo" / "Movies"
    liveRoot = tmp_path / "raid" / "Movies"
    kept = _movie(droppedRoot, "Kept (2020)")
    gone = _movie(droppedRoot, "Gone (2020)")
    live = _movie(liveRoot, "Live (2020)")
    catalogue = _catalogue(tmp_path)
    catalogue.catalogueReplaceFromStorage([droppedRoot, liveRoot], [])
    shutil.rmtree(gone)
    catalogue.catalogueReplaceFromStorage([droppedRoot, liveRoot], [])

    catalogue.catalogueReplaceFromStorage([liveRoot], [], retiredRootKinds=_MOVIE_KIND)

    assert _movieStates(catalogue) == {str(live): "current", str(kept): "current"}


class _Storage(VideoMixin):
    """Expose the storage configuration reader without the full organiser."""


def _configure(monkeypatch, path: Path, content: dict) -> None:
    """Point the application at one test configuration file."""

    path.write_text(json.dumps(content), encoding="utf-8")
    monkeypatch.setattr(videoModule, "APP_CONFIG_FILE", path)


def testConfiguredStorageKindsFollowStatedLists(tmp_path: Path, monkeypatch):
    configPath = tmp_path / "config.json"
    _configure(
        monkeypatch, configPath, {"storage_locations": {"movies": [str(tmp_path)]}}
    )

    assert _Storage().configuredStorageKinds() == _MOVIE_KIND


def testNoConfiguredStorageKindsWithoutConfig(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(videoModule, "APP_CONFIG_FILE", tmp_path / "absent.json")

    assert _Storage().configuredStorageKinds() == frozenset()
