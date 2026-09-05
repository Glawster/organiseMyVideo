"""Tests for the SQLite movie and TV catalogue updated on library scan."""

import json
from pathlib import Path

import sqlite3

import pytest

from cameraFixtures import cardVolumeFake, dashcamTreeBuild
from organiseMyVideo import constants
from organiseMyVideo import metadata as metadataModule
from organiseMyVideo.cameraInventory import CameraInventory
from organiseMyVideo.mediaCatalogue import MediaCatalogue
from organiseMyVideo.video import VideoMixin


def _libraryTree(tmp_path: Path) -> tuple[Path, Path]:
    movieRoot = tmp_path / "movie1"
    movieFolder = movieRoot / "Inception (2010)"
    movieFolder.mkdir(parents=True)
    (movieFolder / "Inception (2010).mkv").write_bytes(b"movie")
    (movieFolder / "movie.xml").write_text(
        "<Title><LocalTitle>Inception</LocalTitle>"
        "<ProductionYear>2010</ProductionYear>"
        "<IMDbId>tt1375666</IMDbId></Title>",
        encoding="utf-8",
    )
    tvRoot = tmp_path / "video1" / "TV"
    season = tvRoot / "After Life" / "Season 01"
    season.mkdir(parents=True)
    (season / "After.Life.S01E04.Sic.Semper.Systema.mkv").write_bytes(b"tv")
    return movieRoot, tvRoot


def testCatalogueReplaceStoresMoviesAndEpisodes(tmp_path: Path):
    movieRoot, tvRoot = _libraryTree(tmp_path)
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")

    counts = catalogue.catalogueReplaceFromStorage([movieRoot], [tvRoot])
    movies = catalogue.catalogueMoviesList()
    episodes = catalogue.catalogueTvEpisodesList()

    assert counts == {"movies": 1, "episodes": 1}
    assert movies[0].title == "Inception"
    assert movies[0].year == "2010"
    assert movies[0].imdbId == "tt1375666"
    assert movies[0].videoPath.endswith("Inception (2010).mkv")
    assert episodes[0].showName == "After Life"
    assert episodes[0].season == 1
    assert episodes[0].episode == 4
    assert episodes[0].episodeTitle == "Sic Semper Systema"


def testSecondScanDropsRemovedMovieFolders(tmp_path: Path):
    movieRoot, tvRoot = _libraryTree(tmp_path)
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([movieRoot], [tvRoot])
    removed = movieRoot / "Inception (2010)"
    for child in removed.iterdir():
        child.unlink()
    removed.rmdir()

    catalogue.catalogueReplaceFromStorage([movieRoot], [tvRoot])

    assert catalogue.catalogueMoviesList() == []
    assert len(catalogue.catalogueTvEpisodesList()) == 1


def testLibraryRescanUpdatesSharedCatalogue(tmp_path: Path):
    movieRoot, tvRoot = _libraryTree(tmp_path)
    organizer = VideoMixin.__new__(VideoMixin)
    organizer.scanStorageLocations = lambda: ([movieRoot], [tvRoot])
    organizer._prepareMetadataLibrary = lambda movieDirs, videoDirs: None
    organizer.resetMovieMetadata = lambda movieDirs: {
        "renamed": 0,
        "skipped": 0,
        "errors": 0,
    }
    organizer.resetTvEpisodeTitles = lambda videoDirs: {
        "renamed": 0,
        "skipped": 0,
        "errors": 0,
    }
    organizer._writeSummaryReport = lambda: None
    organizer._suppressResetNoiseLogs = _nullContext

    organizer.resetLibraryMetadata(target="both")

    catalogue = MediaCatalogue(databasePath=constants.MEDIA_CATALOGUE_DATABASE)
    assert len(catalogue.catalogueMoviesList()) == 1
    assert len(catalogue.catalogueTvEpisodesList()) == 1


def testCatalogueUsesMcmEpisodeTitleOverFilename(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    season = tvRoot / "After Life" / "Season 01"
    metadataDir = season / "metadata"
    metadataDir.mkdir(parents=True)
    (season / "After.Life.S01E04.Pilot.mkv").write_bytes(b"tv")
    (tvRoot / "After Life" / "series.xml").write_text(
        "<Series><LocalTitle>After Life</LocalTitle>"
        "<SeriesID>347507</SeriesID><IMDbId>tt8095986</IMDbId></Series>",
        encoding="utf-8",
    )
    (metadataDir / "After.Life.S01E04.Pilot.xml").write_text(
        "<Item><SeasonNumber>1</SeasonNumber><EpisodeNumber>4</EpisodeNumber>"
        "<EpisodeName>Sic Semper Systema</EpisodeName>"
        "<EpisodeID>7321843</EpisodeID>"
        "<IMDbId>tt9184982</IMDbId></Item>",
        encoding="utf-8",
    )
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")

    catalogue.catalogueReplaceFromStorage([], [tvRoot])
    episode = catalogue.catalogueTvEpisodesList()[0]
    series = catalogue.catalogueTvSeriesList()[0]

    assert episode.showName == "After Life"
    assert episode.season == 1
    assert episode.episode == 4
    assert episode.episodeTitle == "Sic Semper Systema"
    assert episode.tvdbEpisodeId == "7321843"
    assert episode.imdbId == "tt9184982"
    assert series.tvdbId == "347507"
    assert series.imdbId == "tt8095986"


def testCatalogueUsesMetadataLibraryOverFilename(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    season = tvRoot / "After Life" / "Season 01"
    season.mkdir(parents=True)
    (season / "After.Life.S01E04.Pilot.mkv").write_bytes(b"tv")
    metadataModule.METADATA_LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    metadataModule.METADATA_LIBRARY_FILE.write_text(
        json.dumps(
            {
                "version": 1,
                "movies": {},
                "tv": {
                    "series": {
                        "show:afterlife": {
                            "type": "tv",
                            "showName": "After Life",
                            "seriesId": "347507",
                            "imdbId": "tt8095986",
                            "tmdbId": "87108",
                        }
                    },
                    "episodes": {
                        "show:afterlife:s01e04": {
                            "type": "tv",
                            "showName": "After Life",
                            "season": 1,
                            "episode": 4,
                            "episodeTitle": "Sic Semper Systema",
                            "episodeId": "7321843",
                            "tmdbEpisodeId": "123456",
                            "imdbId": "tt9184982",
                            "metadataSource": "tvdb",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")

    catalogue.catalogueReplaceFromStorage([], [tvRoot])
    episode = catalogue.catalogueTvEpisodesList()[0]

    assert episode.episodeTitle == "Sic Semper Systema"
    assert episode.showName == "After Life"
    assert episode.tvdbEpisodeId == "7321843"
    assert episode.tmdbEpisodeId == "123456"
    assert episode.imdbId == "tt9184982"
    series = catalogue.catalogueTvSeriesList()[0]
    assert series.tvdbId == "347507"
    assert series.tmdbId == "87108"
    assert series.imdbId == "tt8095986"


def testCatalogueDoesNotScrapeWhenRecordingKnownMetadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    tvRoot = tmp_path / "TV"
    season = tvRoot / "After Life" / "Season 01"
    season.mkdir(parents=True)
    (season / "After.Life.S01E04.Pilot.mkv").write_bytes(b"tv")

    def boom(*args, **kwargs):
        raise AssertionError("catalogue must not scrape metadata")

    monkeypatch.setattr(
        metadataModule.MetadataMixin,
        "_fetchTvMetadataFromProviders",
        boom,
    )
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")

    catalogue.catalogueReplaceFromStorage([], [tvRoot])
    episode = catalogue.catalogueTvEpisodesList()[0]

    assert episode.season == 1
    assert episode.episode == 4
    assert episode.episodeTitle == "Pilot"


def testCatalogueFallsBackToSeasonFolderWhenFilenameHasNoNumbers(tmp_path: Path):
    tvRoot = tmp_path / "TV"
    season = tvRoot / "After Life" / "Season 02"
    season.mkdir(parents=True)
    (season / "special-clip.mkv").write_bytes(b"tv")
    catalogue = MediaCatalogue(databasePath=tmp_path / "mediaCatalogue.sqlite")

    catalogue.catalogueReplaceFromStorage([], [tvRoot])
    episode = catalogue.catalogueTvEpisodesList()[0]

    assert episode.showName == "After Life"
    assert episode.season == 2
    assert episode.episode is None
    assert episode.tvdbEpisodeId is None
    series = catalogue.catalogueTvSeriesList()[0]
    assert series.tvdbId is None


def testCatalogueAddsTvProviderIdColumnsToOlderFiles(tmp_path: Path):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    connection = sqlite3.connect(databasePath)
    connection.executescript(
        """
        CREATE TABLE tvSeries (
            seriesId INTEGER PRIMARY KEY,
            showName TEXT NOT NULL,
            folderPath TEXT NOT NULL UNIQUE,
            scannedAt TEXT NOT NULL
        );
        CREATE TABLE tvEpisode (
            episodeId INTEGER PRIMARY KEY,
            seriesFolderPath TEXT NOT NULL,
            showName TEXT NOT NULL,
            season INTEGER,
            episode INTEGER,
            episodeTitle TEXT,
            filePath TEXT NOT NULL UNIQUE,
            scannedAt TEXT NOT NULL
        );
        """
    )
    connection.close()
    from organiseMyVideo.mediaCatalogue import catalogueSchemaApply

    connection = sqlite3.connect(databasePath)
    catalogueSchemaApply(connection)
    seriesColumns = {
        row[1] for row in connection.execute("PRAGMA table_info(tvSeries)")
    }
    episodeColumns = {
        row[1] for row in connection.execute("PRAGMA table_info(tvEpisode)")
    }
    connection.close()

    assert {"tvdbId", "tmdbId", "imdbId"} <= seriesColumns
    assert {"tvdbEpisodeId", "tmdbEpisodeId", "imdbId"} <= episodeColumns


def testCatalogueCardsListExposesSizeAndFreeSpace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    card = dashcamTreeBuild(tmp_path / "card", layout="blackvue")
    cardVolumeFake(monkeypatch, 128_000_000_000, 12_400_000_000)
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    scanned = service.inventoryScan(card, 3)
    service.inventoryPersist(scanned)

    cards = MediaCatalogue(databasePath=databasePath).catalogueCardsList()

    assert len(cards) == 1
    assert cards[0].cardId == 3
    assert cards[0].cardRatedGigabytes == 128
    assert cards[0].freeBytes == 12_400_000_000
    assert cards[0].cardSizeBytes == 128_000_000_000
    assert cards[0].usedBytes == 115_600_000_000
    assert cards[0].contentBytes == scanned.capacity.contentBytes


def testCameraSnapshotSharesCatalogueFile(tmp_path: Path):
    databasePath = tmp_path / "mediaCatalogue.sqlite"
    card = dashcamTreeBuild(tmp_path / "card", layout="blackvue")
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    service.inventoryPersist(service.inventoryScan(card, 3))
    movieRoot, tvRoot = _libraryTree(tmp_path / "lib")
    MediaCatalogue(databasePath=databasePath).catalogueReplaceFromStorage(
        [movieRoot], [tvRoot]
    )

    catalogue = MediaCatalogue(databasePath=databasePath)
    connection = sqlite3.connect(databasePath)
    cardCount = connection.execute("SELECT COUNT(*) FROM cardInventory").fetchone()[0]
    connection.close()

    assert cardCount == 1
    assert len(catalogue.catalogueMoviesList()) == 1
    assert len(catalogue.catalogueTvEpisodesList()) == 1


class _nullContext:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
