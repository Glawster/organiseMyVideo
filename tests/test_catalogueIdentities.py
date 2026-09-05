"""Additive catalogue upgrades and future media model contracts (REQ-016)."""

from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from cameraFixtures import dashcamTreeBuild
from organiseMyVideo.cameraInventory import CameraInventory
from organiseMyVideo.mediaCatalogue import (
    HomeVideoCatalogueRecord,
    MediaCatalogue,
    catalogueSchemaApply,
)

# Deliberately independent of the current schema: represents pre-identity files.
LEGACY_SCHEMA = """
CREATE TABLE movieItem (
    movieId INTEGER PRIMARY KEY, title TEXT NOT NULL, year TEXT,
    folderPath TEXT NOT NULL UNIQUE, videoPath TEXT, xmlPath TEXT,
    imdbId TEXT, tmdbId TEXT, scannedAt TEXT NOT NULL
);
CREATE TABLE tvSeries (
    seriesId INTEGER PRIMARY KEY, showName TEXT NOT NULL,
    folderPath TEXT NOT NULL UNIQUE, scannedAt TEXT NOT NULL
);
CREATE TABLE tvEpisode (
    episodeId INTEGER PRIMARY KEY, seriesFolderPath TEXT NOT NULL,
    showName TEXT NOT NULL, season INTEGER, episode INTEGER, episodeTitle TEXT,
    filePath TEXT NOT NULL UNIQUE, scannedAt TEXT NOT NULL
);
CREATE TABLE cardInventory (
    inventoryId INTEGER PRIMARY KEY, cardId INTEGER NOT NULL,
    inventoriedAt TEXT NOT NULL, sourcePath TEXT NOT NULL, volumeLabel TEXT,
    filesystemId TEXT, cardSizeBytes INTEGER, usedBytes INTEGER, freeBytes INTEGER,
    contentBytes INTEGER NOT NULL, dateStart TEXT, dateEnd TEXT,
    dateSource TEXT NOT NULL, cameraKinds TEXT NOT NULL, videoCount INTEGER NOT NULL,
    photoCount INTEGER NOT NULL, thumbnailCount INTEGER NOT NULL,
    previewCount INTEGER NOT NULL, sidecarCount INTEGER NOT NULL,
    otherCount INTEGER NOT NULL, thumbnailSampled INTEGER NOT NULL,
    contentSummary TEXT NOT NULL, visionStatus TEXT NOT NULL
);
CREATE TABLE cardInventoryFile (
    fileId INTEGER PRIMARY KEY, inventoryId INTEGER NOT NULL,
    relativePath TEXT NOT NULL, sizeBytes INTEGER NOT NULL, modifiedAt TEXT,
    captureAt TEXT, kind TEXT NOT NULL, cameraKind TEXT NOT NULL,
    FOREIGN KEY (inventoryId) REFERENCES cardInventory(inventoryId)
);
INSERT INTO movieItem VALUES (7, 'Movie', '2000', '/movies/a', NULL, NULL,
                              'tt0000007', '007', 'old');
INSERT INTO tvSeries VALUES (8, 'Show', '/tv/a', 'old');
INSERT INTO tvEpisode VALUES (9, '/tv/a', 'Show', 1, 2, 'Pilot', '/tv/a/2.mkv', 'old');
INSERT INTO cardInventory VALUES (10, 3, 'old', '/card', 'label', 'fs', 100, 40, 60,
    40, NULL, NULL, 'unknown', 'gopro', 1, 0, 0, 0, 0, 0, 0, 'summary', 'unavailable');
INSERT INTO cardInventoryFile VALUES (11, 10, 'DCIM/a.mp4', 40, NULL, NULL,
                                      'video', 'gopro');
CREATE TABLE unrelated (value TEXT);
INSERT INTO unrelated VALUES ('keep');
CREATE INDEX unrelatedIndex ON unrelated(value);
"""


@pytest.mark.parametrize(
    "firstList",
    ["catalogueCardsList", "catalogueMoviesList", "catalogueTvEpisodesList"],
)
def testLegacyCatalogueOpensWithoutLosingRows(tmp_path: Path, firstList: str):
    databasePath = tmp_path / "catalogue.sqlite"
    with sqlite3.connect(databasePath) as connection:
        connection.executescript(LEGACY_SCHEMA)
        tables = [
            "movieItem",
            "tvSeries",
            "tvEpisode",
            "cardInventory",
            "cardInventoryFile",
            "unrelated",
        ]
        before = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
        }
        definitions = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE name LIKE 'unrelated%'"
        ).fetchall()
    catalogue = MediaCatalogue(databasePath)

    assert len(getattr(catalogue, firstList)()) == 1
    assert catalogue.catalogueCardsList()[0].volumeKind == "sd"
    assert catalogue.catalogueMoviesList()[0].imdbId == "tt0000007"
    assert catalogue.catalogueTvEpisodesList()[0].tvdbEpisodeId is None
    assert catalogue.catalogueTvSeriesList()[0].tvdbId is None
    # Reopen and repeat the migration to verify it persists and is idempotent.
    with sqlite3.connect(databasePath) as connection:
        catalogueSchemaApply(connection)
        catalogueSchemaApply(connection)
        for table, rows in before.items():
            after = connection.execute(f"SELECT * FROM {table}").fetchall()
            assert [row[: len(rows[0])] for row in after] == rows
        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE name LIKE 'unrelated%'"
            ).fetchall()
            == definitions
        )
        assert connection.execute("SELECT * FROM homeVideoItem").fetchall() == []


@pytest.mark.parametrize("legacy", [False, True])
def testIdentityColumnsRoundTrip(tmp_path: Path, legacy: bool):
    databasePath = tmp_path / "catalogue.sqlite"
    with sqlite3.connect(databasePath) as connection:
        if legacy:
            connection.executescript(LEGACY_SCHEMA)
        catalogueSchemaApply(connection)
        for table, columns in [
            ("tvSeries", ("tvdbId", "tmdbId", "imdbId")),
            ("tvEpisode", ("tvdbEpisodeId", "tmdbEpisodeId", "imdbId")),
        ]:
            info = {
                row[1]: row for row in connection.execute(f"PRAGMA table_info({table})")
            }
            assert all(info[column][2:4] == ("TEXT", 0) for column in columns)
        connection.execute(
            "INSERT INTO tvSeries (showName, folderPath, scannedAt, tvdbId, tmdbId, imdbId) VALUES ('Other', '/other', 'now', '001', '002', 'tt003')"
        )
        connection.execute(
            "INSERT INTO tvEpisode (seriesFolderPath, showName, filePath, scannedAt, tvdbEpisodeId, tmdbEpisodeId, imdbId) VALUES ('/other', 'Other', '/other/a.mkv', 'now', '004', '005', 'tt006')"
        )
    catalogue = MediaCatalogue(databasePath)
    series = next(
        row for row in catalogue.catalogueTvSeriesList() if row.showName == "Other"
    )
    episode = next(
        row for row in catalogue.catalogueTvEpisodesList() if row.showName == "Other"
    )
    assert (series.tvdbId, series.tmdbId, series.imdbId) == ("001", "002", "tt003")
    assert (episode.tvdbEpisodeId, episode.tmdbEpisodeId, episode.imdbId) == (
        "004",
        "005",
        "tt006",
    )


def testHomeVideoTableRoundTripAndConstraints(tmp_path: Path):
    with sqlite3.connect(tmp_path / "catalogue.sqlite") as connection:
        connection.row_factory = sqlite3.Row
        catalogueSchemaApply(connection)
        values = (
            "GoPro",
            "GoPro/a.mp4",
            "/homeVideo/GoPro/a.mp4",
            None,
            "unknown",
            42,
            "2026-09-05T10:00:00",
        )
        insert = "INSERT INTO homeVideoItem (kind, relativePath, filePath, captureAt, dateSource, sizeBytes, scannedAt) VALUES (?, ?, ?, ?, ?, ?, ?)"
        connection.execute(insert, values)
        row = HomeVideoCatalogueRecord(
            **dict(connection.execute("SELECT * FROM homeVideoItem").fetchone())
        )
        assert row == HomeVideoCatalogueRecord(1, *values)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(insert, values)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                insert, (*values[:2], "/negative", None, "unknown", -1, values[-1])
            )
        connection.execute(
            insert,
            (
                "Drone",
                "Drone/b.mp4",
                "/homeVideo/Drone/b.mp4",
                "2020-01-02T03:04:05",
                "metadata",
                0,
                values[-1],
            ),
        )
        assert (
            connection.execute(
                "SELECT captureAt FROM homeVideoItem WHERE homeVideoId = 2"
            ).fetchone()[0]
            == "2020-01-02T03:04:05"
        )


@pytest.mark.parametrize("volumeKind", ["sd", "usb"])
def testVolumeKindPersistsWithoutNewScanning(tmp_path: Path, volumeKind: str):
    databasePath = tmp_path / "catalogue.sqlite"
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    record = service.inventoryScan(
        dashcamTreeBuild(tmp_path / "card", layout="blackvue"), 3
    )
    assert record.volumeKind == "sd"
    # Model-only USB value; this does not introduce USB source discovery.
    service.inventoryPersist(replace(record, volumeKind=volumeKind))
    assert MediaCatalogue(databasePath).catalogueCardsList()[0].volumeKind == volumeKind
    assert service.inventoryShow(3).volumeKind == volumeKind
