"""SQLite catalogue of movies, TV, and camera cards for UI queries."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import MEDIA_CATALOGUE_DATABASE, VIDEO_EXTENSIONS

logger = getLogger()

MOVIE_FOLDER_NAME = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)$")

CATALOGUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS cardInventory (
    inventoryId INTEGER PRIMARY KEY,
    cardId INTEGER NOT NULL,
    inventoriedAt TEXT NOT NULL,
    sourcePath TEXT NOT NULL,
    volumeLabel TEXT,
    volumeKind TEXT NOT NULL DEFAULT 'sd',
    manufacturer TEXT,
    cameraModel TEXT,
    cameraSerial TEXT,
    firmwareVersion TEXT,
    cameraWifiMac TEXT,
    goproCardId TEXT,
    cardBrand TEXT,
    filesystemId TEXT,
    cardSizeBytes INTEGER,
    usedBytes INTEGER,
    freeBytes INTEGER,
    contentBytes INTEGER NOT NULL,
    cardRatedGigabytes INTEGER,
    dateStart TEXT,
    dateEnd TEXT,
    dateSource TEXT NOT NULL,
    cameraKinds TEXT NOT NULL,
    videoCount INTEGER NOT NULL,
    photoCount INTEGER NOT NULL,
    thumbnailCount INTEGER NOT NULL,
    previewCount INTEGER NOT NULL,
    sidecarCount INTEGER NOT NULL,
    otherCount INTEGER NOT NULL,
    thumbnailSampled INTEGER NOT NULL,
    contentSummary TEXT NOT NULL,
    visionStatus TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cardInventoryCardIdIndex
    ON cardInventory(cardId, inventoriedAt);
CREATE TABLE IF NOT EXISTS cardInventoryFile (
    fileId INTEGER PRIMARY KEY,
    inventoryId INTEGER NOT NULL,
    relativePath TEXT NOT NULL,
    sizeBytes INTEGER NOT NULL,
    modifiedAt TEXT,
    captureAt TEXT,
    kind TEXT NOT NULL,
    cameraKind TEXT NOT NULL,
    FOREIGN KEY (inventoryId) REFERENCES cardInventory(inventoryId)
);
CREATE TABLE IF NOT EXISTS homeVideoItem (
    homeVideoId INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    relativePath TEXT NOT NULL,
    filePath TEXT NOT NULL UNIQUE,
    captureAt TEXT,
    dateSource TEXT NOT NULL,
    sizeBytes INTEGER NOT NULL CHECK (sizeBytes >= 0),
    scannedAt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movieItem (
    movieId INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    year TEXT,
    folderPath TEXT NOT NULL UNIQUE,
    videoPath TEXT,
    xmlPath TEXT,
    imdbId TEXT,
    tmdbId TEXT,
    scannedAt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tvSeries (
    seriesId INTEGER PRIMARY KEY,
    showName TEXT NOT NULL,
    folderPath TEXT NOT NULL UNIQUE,
    tvdbId TEXT,
    tmdbId TEXT,
    imdbId TEXT,
    scannedAt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tvEpisode (
    episodeId INTEGER PRIMARY KEY,
    seriesFolderPath TEXT NOT NULL,
    showName TEXT NOT NULL,
    season INTEGER,
    episode INTEGER,
    episodeTitle TEXT,
    filePath TEXT NOT NULL UNIQUE,
    tvdbEpisodeId TEXT,
    tmdbEpisodeId TEXT,
    imdbId TEXT,
    scannedAt TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class MovieCatalogueRecord:
    """One movie folder stored for UI queries."""

    title: str
    year: Optional[str]
    folderPath: str
    videoPath: Optional[str]
    xmlPath: Optional[str]
    imdbId: Optional[str]
    tmdbId: Optional[str]


@dataclass(frozen=True)
class CardCatalogueRecord:
    """Latest card snapshot for UI size and free-space display."""

    cardId: int
    inventoriedAt: str
    cardRatedGigabytes: Optional[int]
    cardSizeBytes: Optional[int]
    freeBytes: Optional[int]
    usedBytes: Optional[int]
    contentBytes: int
    cameraKinds: tuple[str, ...]
    dateStart: Optional[str]
    dateEnd: Optional[str]
    volumeKind: str = "sd"


@dataclass(frozen=True)
class HomeVideoCatalogueRecord:
    """One future home-video row; no scanning or query workflow is provided."""

    homeVideoId: int
    kind: str
    relativePath: str
    filePath: str
    captureAt: Optional[str]
    dateSource: str
    sizeBytes: int
    scannedAt: str


@dataclass(frozen=True)
class TvEpisodeCatalogueRecord:
    """One TV episode file stored for UI queries."""

    showName: str
    seriesFolderPath: str
    season: Optional[int]
    episode: Optional[int]
    episodeTitle: Optional[str]
    filePath: str
    tvdbEpisodeId: Optional[str] = None
    tmdbEpisodeId: Optional[str] = None
    imdbId: Optional[str] = None


@dataclass(frozen=True)
class TvSeriesCatalogueRecord:
    """One TV show folder stored for UI queries."""

    showName: str
    folderPath: str
    tvdbId: Optional[str] = None
    tmdbId: Optional[str] = None
    imdbId: Optional[str] = None


class MediaCatalogue:
    """Replace and read the SQLite media catalogue used by the UI."""

    def __init__(self, databasePath: Optional[Path] = None):
        """Open the catalogue at *databasePath* or the application default."""

        self.databasePath = (
            Path(databasePath) if databasePath else MEDIA_CATALOGUE_DATABASE
        )

    ## catalogue

    def catalogueCardsList(self) -> list[CardCatalogueRecord]:
        """Return the latest snapshot per card ID for UI queries."""

        if not self.databasePath.is_file():
            return []
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                """
                SELECT c.cardId, c.inventoriedAt, c.cardRatedGigabytes,
                       c.cardSizeBytes, c.freeBytes, c.usedBytes, c.contentBytes,
                       c.cameraKinds, c.dateStart, c.dateEnd, c.volumeKind
                FROM cardInventory c
                INNER JOIN (
                    SELECT cardId, MAX(inventoryId) AS inventoryId
                    FROM cardInventory
                    GROUP BY cardId
                ) latest ON c.inventoryId = latest.inventoryId
                ORDER BY c.cardId
                """
            ).fetchall()
        return [
            CardCatalogueRecord(
                cardId=row["cardId"],
                inventoriedAt=row["inventoriedAt"],
                cardRatedGigabytes=row["cardRatedGigabytes"],
                cardSizeBytes=row["cardSizeBytes"],
                freeBytes=row["freeBytes"],
                usedBytes=row["usedBytes"],
                contentBytes=row["contentBytes"],
                cameraKinds=tuple(
                    part for part in (row["cameraKinds"] or "").split(",") if part
                ),
                dateStart=row["dateStart"],
                dateEnd=row["dateEnd"],
                volumeKind=row["volumeKind"],
            )
            for row in rows
        ]

    def catalogueMoviesList(self) -> list[MovieCatalogueRecord]:
        """Return stored movie rows ordered by title and year."""

        if not self.databasePath.is_file():
            return []
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                """
                SELECT title, year, folderPath, videoPath, xmlPath, imdbId, tmdbId
                FROM movieItem
                ORDER BY title, year
                """
            ).fetchall()
        return [
            MovieCatalogueRecord(
                title=row["title"],
                year=row["year"],
                folderPath=row["folderPath"],
                videoPath=row["videoPath"],
                xmlPath=row["xmlPath"],
                imdbId=row["imdbId"],
                tmdbId=row["tmdbId"],
            )
            for row in rows
        ]

    def catalogueReplaceFromStorage(
        self,
        movieDirs: list[Path],
        videoDirs: list[Path],
        *,
        replaceMovies: bool = True,
        replaceTv: bool = True,
    ) -> dict[str, int]:
        """Replace movie and/or TV tables from current storage roots."""

        scannedAt = _timestampNow()
        identity = _catalogueIdentitySource()
        movies = _moviesCollect(movieDirs, identity) if replaceMovies else None
        episodes = None
        series = None
        if replaceTv:
            episodes, series = _tvCollect(videoDirs, identity)
        self.databasePath.parent.mkdir(parents=True, exist_ok=True)
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            if movies is not None:
                logger.doing("updating movie catalogue")
                _moviesReplace(connection, movies, scannedAt)
                logger.value("movie rows", len(movies))
            if episodes is not None and series is not None:
                logger.doing("updating tv catalogue")
                _tvReplace(connection, episodes, series, scannedAt)
                logger.value("tv episode rows", len(episodes))
            connection.commit()
        counts = {
            "movies": 0 if movies is None else len(movies),
            "episodes": 0 if episodes is None else len(episodes),
        }
        logger.done("media catalogue updated")
        return counts

    def catalogueTvEpisodesList(self) -> list[TvEpisodeCatalogueRecord]:
        """Return stored TV episode rows ordered by show and episode."""

        if not self.databasePath.is_file():
            return []
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                """
                SELECT showName, seriesFolderPath, season, episode, episodeTitle,
                       filePath, tvdbEpisodeId, tmdbEpisodeId, imdbId
                FROM tvEpisode
                ORDER BY showName, season, episode, filePath
                """
            ).fetchall()
        return [
            TvEpisodeCatalogueRecord(
                showName=row["showName"],
                seriesFolderPath=row["seriesFolderPath"],
                season=row["season"],
                episode=row["episode"],
                episodeTitle=row["episodeTitle"],
                filePath=row["filePath"],
                tvdbEpisodeId=row["tvdbEpisodeId"],
                tmdbEpisodeId=row["tmdbEpisodeId"],
                imdbId=row["imdbId"],
            )
            for row in rows
        ]

    def catalogueTvSeriesList(self) -> list[TvSeriesCatalogueRecord]:
        """Return stored TV series rows ordered by show name."""

        if not self.databasePath.is_file():
            return []
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                """
                SELECT showName, folderPath, tvdbId, tmdbId, imdbId
                FROM tvSeries
                ORDER BY showName, folderPath
                """
            ).fetchall()
        return [
            TvSeriesCatalogueRecord(
                showName=row["showName"],
                folderPath=row["folderPath"],
                tvdbId=row["tvdbId"],
                tmdbId=row["tmdbId"],
                imdbId=row["imdbId"],
            )
            for row in rows
        ]

    def _databaseConnect(self) -> sqlite3.Connection:
        """Open the catalogue with camelCase row access."""

        connection = sqlite3.connect(self.databasePath)
        connection.row_factory = sqlite3.Row
        return connection


def catalogueSchemaApply(connection: sqlite3.Connection) -> None:
    """Create missing tables and add columns without replacing existing rows."""

    connection.executescript(CATALOGUE_SCHEMA)
    # Additive upgrades preserve snapshots and permit repeated opens of old files.
    _catalogueColumnEnsure(connection, "cardInventory", "cardRatedGigabytes", "INTEGER")
    _catalogueColumnEnsure(
        connection, "cardInventory", "volumeKind", "TEXT NOT NULL DEFAULT 'sd'"
    )
    for column in (
        "manufacturer",
        "cameraModel",
        "cameraSerial",
        "firmwareVersion",
        "cameraWifiMac",
        "goproCardId",
        "cardBrand",
    ):
        _catalogueColumnEnsure(connection, "cardInventory", column, "TEXT")
    _catalogueColumnEnsure(connection, "tvSeries", "tvdbId", "TEXT")
    _catalogueColumnEnsure(connection, "tvSeries", "tmdbId", "TEXT")
    _catalogueColumnEnsure(connection, "tvSeries", "imdbId", "TEXT")
    _catalogueColumnEnsure(connection, "tvEpisode", "tvdbEpisodeId", "TEXT")
    _catalogueColumnEnsure(connection, "tvEpisode", "tmdbEpisodeId", "TEXT")
    _catalogueColumnEnsure(connection, "tvEpisode", "imdbId", "TEXT")


def _catalogueColumnEnsure(
    connection: sqlite3.Connection, table: str, column: str, sqlType: str
) -> None:
    """Add *column* to *table* when an older catalogue file lacks it."""

    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sqlType}")


## movies


def _moviesCollect(movieDirs: list[Path], identity) -> list[MovieCatalogueRecord]:
    """Walk movie storage roots and record known movie metadata."""

    records: list[MovieCatalogueRecord] = []
    seen: set[str] = set()
    for root in movieDirs:
        root = Path(root)
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir())
        except OSError:
            continue
        for folder in children:
            if not folder.is_dir():
                continue
            record = _movieFromFolder(folder, identity)
            if record is None or record.folderPath in seen:
                continue
            seen.add(record.folderPath)
            records.append(record)
    records.sort(
        key=lambda item: (item.title.lower(), item.year or "", item.folderPath)
    )
    return records


def _movieFromFolder(folder: Path, identity) -> Optional[MovieCatalogueRecord]:
    """Build a movie row from MCM, the metadata library, then folder/file names."""

    videos = _videoFiles(folder, recursive=False)
    videoPath = videos[0] if videos else None
    parsedFolder = MOVIE_FOLDER_NAME.match(folder.name)
    folderHints = {
        "type": "movie",
        "title": parsedFolder.group("title").strip() if parsedFolder else None,
        "year": parsedFolder.group("year") if parsedFolder else None,
    }
    filenameHints = identity.parseMovieFilename(videoPath.name) if videoPath else None
    mcm = identity._readMovieMcmHints(videoPath) if videoPath else None
    if mcm and mcm.get("type") != "movie":
        mcm = None
    seed = _knownMetadataApply(
        identity, mcm=mcm, library=None, filename=filenameHints, folder=folderHints
    )
    library = identity._lookupMovieMetadataInLibrary(seed)
    resolved = _knownMetadataApply(
        identity,
        mcm=mcm,
        library=library,
        filename=filenameHints,
        folder=folderHints,
    )
    title = resolved.get("title")
    if not title:
        return None
    xmlPath = folder / "movie.xml"
    return MovieCatalogueRecord(
        title=title,
        year=resolved.get("year"),
        folderPath=str(folder),
        videoPath=str(videoPath) if videoPath else None,
        xmlPath=str(xmlPath) if xmlPath.is_file() else None,
        imdbId=resolved.get("imdbId"),
        tmdbId=resolved.get("tmdbId"),
    )


def _moviesReplace(
    connection: sqlite3.Connection,
    movies: list[MovieCatalogueRecord],
    scannedAt: str,
) -> None:
    """Replace all movie rows with the current scan."""

    connection.execute("DELETE FROM movieItem")
    connection.executemany(
        """
        INSERT INTO movieItem (
            title, year, folderPath, videoPath, xmlPath, imdbId, tmdbId, scannedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.title,
                item.year,
                item.folderPath,
                item.videoPath,
                item.xmlPath,
                item.imdbId,
                item.tmdbId,
                scannedAt,
            )
            for item in movies
        ],
    )


## tv


def _tvCollect(
    videoDirs: list[Path], identity
) -> tuple[list[TvEpisodeCatalogueRecord], list[TvSeriesCatalogueRecord]]:
    """Walk TV storage roots and record known series and episode metadata."""

    episodes: list[TvEpisodeCatalogueRecord] = []
    seriesByFolder: dict[str, TvSeriesCatalogueRecord] = {}
    seen: set[str] = set()
    for root in videoDirs:
        root = Path(root)
        if not root.is_dir():
            continue
        try:
            shows = sorted(path for path in root.iterdir() if path.is_dir())
        except OSError:
            continue
        for showDir in shows:
            folderPath = str(showDir)
            seriesByFolder[folderPath] = _tvSeriesFromFolder(showDir, identity)
            for dirPath, dirNames, fileNames in os.walk(showDir):
                dirNames[:] = [name for name in dirNames if not name.startswith(".")]
                current = Path(dirPath)
                seasonHint = identity._inferSeasonFromPath(current)
                for fileName in fileNames:
                    path = current / fileName
                    if path.suffix.lower() not in VIDEO_EXTENSIONS:
                        continue
                    record = _tvEpisodeFromFile(path, showDir, seasonHint, identity)
                    if record.filePath in seen:
                        continue
                    seen.add(record.filePath)
                    episodes.append(record)
    episodes.sort(
        key=lambda item: (
            item.showName.lower(),
            item.season or 0,
            item.episode or 0,
            item.filePath,
        )
    )
    series = sorted(
        seriesByFolder.values(),
        key=lambda item: (item.showName.lower(), item.folderPath),
    )
    return episodes, series


def _tvEpisodeFromFile(
    path: Path, showDir: Path, seasonHint: Optional[int], identity
) -> TvEpisodeCatalogueRecord:
    """Build an episode row from MCM, the metadata library, then names."""

    folderHints = {
        "type": "tv",
        "showName": showDir.name,
        "season": seasonHint,
        "episode": None,
        "episodeTitle": None,
    }
    filenameHints = identity.parseTvFilename(path.name)
    mcm = identity._readTvMcmHints(path)
    if mcm and mcm.get("type") != "tv":
        mcm = None
    seed = _knownMetadataApply(
        identity,
        mcm=mcm,
        library=None,
        filename=filenameHints,
        folder=folderHints,
    )
    library = identity._lookupTvMetadataInLibrary(seed)
    episodeLibrary = identity._firstStoredMetadataRecord(
        identity._loadMetadataLibrary()["tv"]["episodes"],
        identity._tvEpisodeLibraryKeys(seed),
    )
    resolved = _knownMetadataApply(
        identity,
        mcm=mcm,
        library=library,
        filename=filenameHints,
        folder=folderHints,
    )
    return TvEpisodeCatalogueRecord(
        showName=resolved.get("showName") or showDir.name,
        seriesFolderPath=str(showDir),
        season=resolved.get("season"),
        episode=resolved.get("episode"),
        episodeTitle=resolved.get("episodeTitle"),
        filePath=str(path),
        tvdbEpisodeId=_tvIdText(
            (episodeLibrary or {}).get("tvdbEpisodeId")
            or (episodeLibrary or {}).get("episodeId")
            or resolved.get("tvdbEpisodeId")
            or resolved.get("episodeId")
        ),
        tmdbEpisodeId=_tvIdText(
            (episodeLibrary or {}).get("tmdbEpisodeId") or resolved.get("tmdbEpisodeId")
        ),
        imdbId=_tvIdText(
            (episodeLibrary or {}).get("imdbId") or resolved.get("imdbId")
        ),
    )


def _tvReplace(
    connection: sqlite3.Connection,
    episodes: list[TvEpisodeCatalogueRecord],
    series: list[TvSeriesCatalogueRecord],
    scannedAt: str,
) -> None:
    """Replace series and episode rows from the current scan."""

    connection.execute("DELETE FROM tvEpisode")
    connection.execute("DELETE FROM tvSeries")
    connection.executemany(
        """
        INSERT INTO tvSeries (
            showName, folderPath, tvdbId, tmdbId, imdbId, scannedAt
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.showName,
                item.folderPath,
                item.tvdbId,
                item.tmdbId,
                item.imdbId,
                scannedAt,
            )
            for item in series
        ],
    )
    connection.executemany(
        """
        INSERT INTO tvEpisode (
            seriesFolderPath, showName, season, episode, episodeTitle, filePath,
            tvdbEpisodeId, tmdbEpisodeId, imdbId, scannedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.seriesFolderPath,
                item.showName,
                item.season,
                item.episode,
                item.episodeTitle,
                item.filePath,
                item.tvdbEpisodeId,
                item.tmdbEpisodeId,
                item.imdbId,
                scannedAt,
            )
            for item in episodes
        ],
    )


def _tvSeriesFromFolder(showDir: Path, identity) -> TvSeriesCatalogueRecord:
    """Build a series row from MCM and the metadata library."""

    folderHints = {"type": "tv", "showName": showDir.name}
    mcm = identity._readTvSeriesMcmHints(showDir)
    seed = _knownMetadataApply(
        identity, mcm=mcm, library=None, filename=None, folder=folderHints
    )
    library = identity._loadMetadataLibrary()
    seriesLibrary = identity._firstStoredMetadataRecord(
        library["tv"]["series"], identity._tvSeriesLibraryKeys(seed)
    )
    resolved = _knownMetadataApply(
        identity,
        mcm=mcm,
        library=seriesLibrary,
        filename=None,
        folder=folderHints,
    )
    return TvSeriesCatalogueRecord(
        showName=resolved.get("showName") or showDir.name,
        folderPath=str(showDir),
        tvdbId=_tvIdText(resolved.get("tvdbId") or resolved.get("seriesId")),
        tmdbId=_tvIdText(resolved.get("tmdbId")),
        imdbId=_tvIdText(resolved.get("imdbId")),
    )


## identity


def _catalogueIdentitySource():
    """Return an organiser mixin instance that reads stored metadata only."""

    from .filesystemOperations import FilesystemOperations
    from .metadata import MetadataMixin
    from .video import VideoMixin

    class CatalogueIdentitySource(MetadataMixin, VideoMixin):
        """Read MCM files and the metadata library without scraping."""

    source = CatalogueIdentitySource.__new__(CatalogueIdentitySource)
    source.sourceDir = Path("/")
    source.dryRun = True
    source.filesystem = FilesystemOperations(dryRun=True)
    source.stateFilesystem = FilesystemOperations(dryRun=False)
    source.refreshMetadataLibrary = False
    source._metadataLibraryCache = None
    source._metadataLibraryLoadState = "missing"
    source._metadataMovieLogStarted = False
    source._metadataShowLogStarted = False
    source._tvdbApiKeyPromptAttempted = True
    source.tvdbApiKeyPrompt = None
    return source


def _knownMetadataApply(
    identity,
    *,
    mcm: Optional[dict],
    library: Optional[dict],
    filename: Optional[dict],
    folder: Optional[dict],
) -> dict:
    """Merge known metadata with MCM first and folder names last."""

    resolved = dict(folder or {})
    resolved = identity._mergeMetadata(filename, resolved)
    resolved = identity._mergeMetadata(library, resolved)
    resolved = identity._mergeMetadata(mcm, resolved)
    return resolved or {}


## utilities


def _timestampNow() -> str:
    """Return the current UTC time as a naive ISO string."""

    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat()


def _tvIdText(value: object) -> Optional[str]:
    """Return a provider ID as text when one is present."""

    if value in (None, ""):
        return None
    return str(value)


def _videoFiles(folder: Path, *, recursive: bool) -> list[Path]:
    """Return video files in *folder*, optionally including subfolders."""

    if recursive:
        paths = folder.rglob("*")
    else:
        try:
            paths = folder.iterdir()
        except OSError:
            return []
    videos = [
        path
        for path in paths
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return sorted(videos)
