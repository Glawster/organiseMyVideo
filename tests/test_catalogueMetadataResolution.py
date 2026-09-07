"""REQ-017 production-path evidence for offline catalogue resolution."""

import json
import socket
import sqlite3
from pathlib import Path

import pytest

from organiseMyVideo import metadata as metadataModule
from organiseMyVideo.mediaCatalogue import MediaCatalogue
from organiseMyVideo.video import VideoMixin


@pytest.fixture(autouse=True)
def networkBlock(monkeypatch):
    """Fail if scans attempt provider identification, prompting or networking."""

    def networkReject(*args, **kwargs):
        raise AssertionError("catalogue scan attempted external identification")

    monkeypatch.setattr(socket.socket, "connect", networkReject)
    monkeypatch.setattr("builtins.input", networkReject)
    for name in vars(metadataModule.MetadataMixin):
        if name.startswith(("_fetch", "_enrich", "_scrape", "_prepare")):
            monkeypatch.setattr(metadataModule.MetadataMixin, name, networkReject)
    monkeypatch.setattr(VideoMixin, "__init__", networkReject)


def _libraryWrite(movies=None, series=None, episodes=None):
    libraryPath = metadataModule.METADATA_LIBRARY_FILE
    libraryPath.parent.mkdir(parents=True, exist_ok=True)
    libraryPath.write_text(
        json.dumps(
            {
                "movies": movies or {},
                "tv": {"series": series or {}, "episodes": episodes or {}},
            }
        )
    )


@pytest.mark.parametrize("source", ["mcm", "library", "filename", "folder", "xmlOnly"])
def testMovieEvidencePriority(tmp_path: Path, source: str):
    root = tmp_path / "movies"
    folder = root / "Folder (1999)"
    folder.mkdir(parents=True)
    if source != "xmlOnly":
        (
            folder / ("Canonical (2000).mkv" if source != "folder" else "clip.mkv")
        ).touch()
    if source in ("mcm", "xmlOnly"):
        (folder / "movie.xml").write_text(
            "<Title><LocalTitle>MCM</LocalTitle><ProductionYear>2001</ProductionYear>"
            "<IMDbId>tt001</IMDbId><TMDbId>002</TMDbId></Title>"
        )
    _libraryWrite(
        movies=(
            {
                "title:canonical:2000": {
                    "title": "Library",
                    "year": "2002",
                    "imdbId": "tt003",
                },
                "imdb:tt001": {"title": "Wrong", "year": "1900", "imdbId": "tt004"},
            }
            if source in ("mcm", "library")
            else {}
        )
    )
    catalogue = MediaCatalogue(tmp_path / "catalogue.sqlite")

    catalogue.catalogueReplaceFromStorage([root], [], replaceTv=False)

    movie = catalogue.catalogueMoviesList()[0]
    expected = {
        "mcm": ("MCM", "2001", "tt001"),
        "xmlOnly": ("MCM", "2001", "tt001"),
        "library": ("Library", "2002", "tt003"),
        "filename": ("Canonical", "2000", None),
        "folder": ("Folder", "1999", None),
    }
    assert (movie.title, movie.year, movie.imdbId) == expected[source]


@pytest.mark.parametrize("stronger", [False, True])
def testRescanPreservesOnlyMissingProviderIds(tmp_path: Path, stronger: bool):
    movieRoot = tmp_path / "movies"
    movieDir = movieRoot / "Current (2000)"
    movieDir.mkdir(parents=True)
    (movieDir / "Current (2000).mkv").touch()
    tvRoot = tmp_path / "TV"
    showDir = tvRoot / "Current Show"
    seasonDir = showDir / "Season 01"
    seasonDir.mkdir(parents=True)
    (seasonDir / "Current.Show.S01E02.Current.Title.mkv").touch()
    catalogue = MediaCatalogue(tmp_path / "catalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([movieRoot], [tvRoot])
    with sqlite3.connect(catalogue.databasePath) as connection:
        connection.execute(
            "UPDATE movieItem SET title='Stale', year='1900', imdbId='ttOld', tmdbId='oldMovie'"
        )
        connection.execute(
            "UPDATE tvSeries SET showName='Stale', tvdbId='oldSeries', tmdbId='oldTmdb', imdbId='ttSeries'"
        )
        connection.execute(
            "UPDATE tvEpisode SET showName='Stale', season=9, episode=9, episodeTitle='Stale', tvdbEpisodeId='oldEpisode', tmdbEpisodeId='oldTmdbEpisode', imdbId='ttEpisode'"
        )
    if stronger:
        _libraryWrite(
            movies={"title:current:2000": {"imdbId": "ttNew", "title": "Current"}},
            series={"show:currentshow": {"tvdbId": "newSeries", "tmdbId": "newTmdb"}},
            episodes={
                "show:currentshow:s01e02": {
                    "tvdbEpisodeId": "newEpisode",
                    "imdbId": "ttNewEpisode",
                }
            },
        )
    # Selected replacements leave the other collection exactly as it was.
    oldEpisodes = catalogue.catalogueTvEpisodesList()
    oldSeries = catalogue.catalogueTvSeriesList()
    catalogue.catalogueReplaceFromStorage([movieRoot], [], replaceTv=False)
    assert catalogue.catalogueTvEpisodesList() == oldEpisodes
    assert catalogue.catalogueTvSeriesList() == oldSeries
    movies = catalogue.catalogueMoviesList()
    catalogue.catalogueReplaceFromStorage([], [tvRoot], replaceMovies=False)
    assert catalogue.catalogueMoviesList() == movies
    movie = movies[0]
    series = catalogue.catalogueTvSeriesList()[0]
    episode = catalogue.catalogueTvEpisodesList()[0]
    assert (movie.title, movie.year) == ("Current", "2000")
    assert movie.imdbId == ("ttNew" if stronger else "ttOld")
    assert movie.tmdbId == "oldMovie"
    assert series.showName == episode.showName == "Current Show"
    assert series.tvdbId == ("newSeries" if stronger else "oldSeries")
    assert series.tmdbId == ("newTmdb" if stronger else "oldTmdb")
    assert series.imdbId == "ttSeries"
    assert (episode.season, episode.episode, episode.episodeTitle) == (
        1,
        2,
        "Current Title",
    )
    assert episode.tvdbEpisodeId == ("newEpisode" if stronger else "oldEpisode")
    assert episode.tmdbEpisodeId == "oldTmdbEpisode"
    assert episode.imdbId == ("ttNewEpisode" if stronger else "ttEpisode")


@pytest.mark.parametrize("episodeXml", [False, True])
def testTvMcmPriorityAndIdentityScope(tmp_path: Path, episodeXml: bool):
    root = tmp_path / "TV"
    showDir = root / "Folder Show"
    seasonDir = showDir / "Season 09"
    (seasonDir / "metadata").mkdir(parents=True)
    (seasonDir / "Filename.Show.S01E02.Pilot.mkv").touch()
    (showDir / "series.xml").write_text(
        "<Series><LocalTitle>MCM Show</LocalTitle><SeriesID>001</SeriesID>"
        "<TMDbId>002</TMDbId><IMDbId>ttSeries</IMDbId></Series>"
    )
    if episodeXml:
        (seasonDir / "metadata" / "Filename.Show.S01E02.Pilot.xml").write_text(
            "<Item><SeasonNumber>0</SeasonNumber><EpisodeNumber>3</EpisodeNumber>"
            "<EpisodeName>MCM Title</EpisodeName><EpisodeID>003</EpisodeID>"
            "<TMDbEpisodeId>004</TMDbEpisodeId><IMDbId>ttMcmEpisode</IMDbId></Item>"
        )
    _libraryWrite(
        series={
            "series:001": {
                "showName": "Wrong",
                "tvdbId": "wrong",
                "imdbId": "ttWrongSeries",
            }
        },
        episodes={
            "episode:003": {
                "episodeId": "old",
                "tvdbEpisodeId": "old",
                "tmdbEpisodeId": "old",
                "imdbId": "ttOld",
                "episodeTitle": "Old",
            }
        },
    )
    catalogue = MediaCatalogue(tmp_path / "catalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [root])
    series = catalogue.catalogueTvSeriesList()[0]
    episode = catalogue.catalogueTvEpisodesList()[0]
    assert (series.showName, series.tvdbId, series.tmdbId, series.imdbId) == (
        "MCM Show",
        "001",
        "002",
        "ttSeries",
    )
    assert episode.showName == "MCM Show"
    if episodeXml:
        assert (episode.season, episode.episode, episode.episodeTitle) == (
            0,
            3,
            "MCM Title",
        )
        assert (episode.tvdbEpisodeId, episode.tmdbEpisodeId, episode.imdbId) == (
            "003",
            "004",
            "ttMcmEpisode",
        )
    else:
        assert (episode.season, episode.episode) == (1, 2)
        assert episode.imdbId is None
        assert episode.tvdbEpisodeId is None


def testEpisodeLibraryUsesKnownSeriesIdentity(tmp_path: Path):
    root = tmp_path / "TV"
    seasonDir = root / "Known Show" / "Season 01"
    seasonDir.mkdir(parents=True)
    (seasonDir / "Known.Show.S01E02.Pilot.mkv").touch()
    _libraryWrite(
        series={"show:knownshow": {"tvdbId": "001", "showName": "Canonical Show"}},
        episodes={
            "series:001:s01e02": {"tvdbEpisodeId": "002", "episodeTitle": "Known Title"}
        },
    )
    catalogue = MediaCatalogue(tmp_path / "catalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [root])
    episode = catalogue.catalogueTvEpisodesList()[0]
    assert episode.tvdbEpisodeId == "002"
    assert episode.episodeTitle == "Known Title"
    assert episode.showName == "Canonical Show"
