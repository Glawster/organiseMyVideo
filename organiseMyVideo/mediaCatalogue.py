"""SQLite catalogue of movies, TV, and camera cards for UI queries."""

from __future__ import annotations

from contextlib import contextmanager
import os
import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import MEDIA_CATALOGUE_DATABASE, VIDEO_EXTENSIONS
from .terminalProgress import TerminalProgress

logger = getLogger()

MOVIE_FOLDER_NAME = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)$")
LOCATION_CURRENT = "current"
LOCATION_STALE = "stale"
LOCATION_UNVERIFIED = "unverified"
LOCATION_STATES = (LOCATION_CURRENT, LOCATION_STALE, LOCATION_UNVERIFIED)
# Stale rows stay in the database but are not part of the visible library.
VISIBLE_LOCATION_STATES = (LOCATION_CURRENT, LOCATION_UNVERIFIED)


@contextmanager
def _bufferCatalogueDiagnostics():
    """Buffer catalogue warnings/errors until the active progress line finishes."""
    from . import metadata as metadata_module
    from . import video as video_module

    targets = (logger, metadata_module.logger, video_module.logger)
    methodNames = ("warning", "error")
    originals = {
        target: {name: getattr(target, name) for name in methodNames}
        for target in targets
    }
    events = []

    def _capture(original):
        def _buffered(*args, **kwargs):
            events.append((original, args, kwargs))

        return _buffered

    try:
        for target in targets:
            for name in methodNames:
                setattr(target, name, _capture(originals[target][name]))
        yield events
    finally:
        for target, methods in originals.items():
            for name, original in methods.items():
                setattr(target, name, original)


def _flushCatalogueDiagnostics(events: list) -> None:
    """Emit buffered catalogue warnings/errors after progress is complete."""
    for original, args, kwargs in events:
        original(*args, **kwargs)


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
CREATE TABLE IF NOT EXISTS cameraCaptureCorrection (
    ruleId TEXT PRIMARY KEY,
    importId TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cameraCaptureTime (
    importId TEXT NOT NULL,
    relativePath TEXT NOT NULL,
    ruleId TEXT NOT NULL,
    filePath TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    rawCaptureAt TEXT NOT NULL,
    correctedCaptureAt TEXT NOT NULL,
    dateSource TEXT NOT NULL,
    PRIMARY KEY (importId, relativePath)
);
CREATE INDEX IF NOT EXISTS cameraCaptureTimePathIndex ON cameraCaptureTime(filePath);
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
    scannedAt TEXT NOT NULL,
    locationState TEXT NOT NULL DEFAULT 'unverified'
);
CREATE TABLE IF NOT EXISTS tvSeries (
    seriesId INTEGER PRIMARY KEY,
    showName TEXT NOT NULL,
    folderPath TEXT NOT NULL UNIQUE,
    tvdbId TEXT,
    tmdbId TEXT,
    imdbId TEXT,
    scannedAt TEXT NOT NULL,
    locationState TEXT NOT NULL DEFAULT 'unverified'
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
    scannedAt TEXT NOT NULL,
    locationState TEXT NOT NULL DEFAULT 'unverified'
);
CREATE TABLE IF NOT EXISTS catalogueScanRoot (
    rootPath TEXT NOT NULL,
    kind TEXT NOT NULL,
    scannedAt TEXT NOT NULL,
    outcome TEXT NOT NULL,
    PRIMARY KEY (rootPath, kind)
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
    locationState: str = LOCATION_CURRENT


@dataclass(frozen=True)
class CatalogueRootCoverage:
    """Whether one storage root was listed during a catalogue reconcile."""

    rootPath: str
    kind: str
    outcome: str


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
    locationState: str = LOCATION_CURRENT


@dataclass(frozen=True)
class TvSeriesCatalogueRecord:
    """One TV show folder stored for UI queries."""

    showName: str
    folderPath: str
    tvdbId: Optional[str] = None
    tmdbId: Optional[str] = None
    imdbId: Optional[str] = None
    locationState: str = LOCATION_CURRENT


class MediaCatalogue:
    """Reconcile and read the SQLite media catalogue used by the UI."""

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
            rows = connection.execute("""
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
                """).fetchall()
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

    def catalogueCoverageList(self) -> list[CatalogueRootCoverage]:
        """Return the latest reconcile outcome recorded for each storage root."""

        if not self.databasePath.is_file():
            return []
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute("""
                SELECT rootPath, kind, outcome
                FROM catalogueScanRoot
                ORDER BY kind, rootPath
                """).fetchall()
        return [
            CatalogueRootCoverage(
                rootPath=row["rootPath"],
                kind=row["kind"],
                outcome=row["outcome"],
            )
            for row in rows
        ]

    def catalogueMoviesList(
        self, *, states: Optional[tuple[str, ...]] = None
    ) -> list[MovieCatalogueRecord]:
        """Return stored movie rows ordered by title and year.

        The default list is the visible library: current and not-yet-verified
        rows. Pass ``states`` to include stale locations.
        """

        if not self.databasePath.is_file():
            return []
        clause, parameters = _locationStateClause(states)
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                f"""
                SELECT title, year, folderPath, videoPath, xmlPath, imdbId, tmdbId,
                       locationState
                FROM movieItem
                WHERE {clause}
                ORDER BY title, year
                """,
                parameters,
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
                locationState=row["locationState"],
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
        """Reconcile movie and/or TV rows from the supplied storage roots.

        A root that can be listed is authoritative for the folders directly
        beneath it. Those folders become current, and catalogued folders under
        it that are absent become stale. A missing or unlistable root is not
        authoritative, so rows already stored beneath it are left unchanged.
        A directory inside a TV show that cannot be listed does not make the
        episodes beneath it stale.
        """

        scannedAt = _timestampNow()
        identity = _catalogueIdentitySource()
        movies = None
        movieCoverage: list[CatalogueRootCoverage] = []
        episodes = None
        series = None
        tvCoverage: list[CatalogueRootCoverage] = []
        incompleteDirectories: list[Path] = []
        if replaceMovies:
            movies, movieCoverage = _moviesCollect(movieDirs, identity)
        if replaceTv:
            episodes, series, tvCoverage, incompleteDirectories = _tvCollect(
                videoDirs, identity
            )
        self.databasePath.parent.mkdir(parents=True, exist_ok=True)
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            # Lock the snapshot before reading durable identities.
            connection.execute("BEGIN IMMEDIATE")
            if movies is not None:
                logger.doing("updating movie catalogue")
                _moviesReconcile(connection, movies, scannedAt, movieCoverage)
                logger.value("movie rows", len(movies))
            if episodes is not None and series is not None:
                logger.doing("updating tv catalogue")
                _tvReconcile(
                    connection,
                    episodes,
                    series,
                    scannedAt,
                    tvCoverage,
                    incompleteDirectories,
                )
                logger.value("tv episode rows", len(episodes))
            _coverageStore(connection, [*movieCoverage, *tvCoverage], scannedAt)
            connection.commit()
        counts = {
            "movies": 0 if movies is None else len(movies),
            "episodes": 0 if episodes is None else len(episodes),
        }
        logger.done("media catalogue updated")
        return counts

    def catalogueTvEpisodesList(
        self, *, states: Optional[tuple[str, ...]] = None
    ) -> list[TvEpisodeCatalogueRecord]:
        """Return stored TV episode rows ordered by show and episode."""

        if not self.databasePath.is_file():
            return []
        clause, parameters = _locationStateClause(states)
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                f"""
                SELECT showName, seriesFolderPath, season, episode, episodeTitle,
                       filePath, tvdbEpisodeId, tmdbEpisodeId, imdbId, locationState
                FROM tvEpisode
                WHERE {clause}
                ORDER BY showName, season, episode, filePath
                """,
                parameters,
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
                locationState=row["locationState"],
            )
            for row in rows
        ]

    def catalogueTvSeriesList(
        self, *, states: Optional[tuple[str, ...]] = None
    ) -> list[TvSeriesCatalogueRecord]:
        """Return stored TV series rows ordered by show name."""

        if not self.databasePath.is_file():
            return []
        clause, parameters = _locationStateClause(states)
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            rows = connection.execute(
                f"""
                SELECT showName, folderPath, tvdbId, tmdbId, imdbId, locationState
                FROM tvSeries
                WHERE {clause}
                ORDER BY showName, folderPath
                """,
                parameters,
            ).fetchall()
        return [
            TvSeriesCatalogueRecord(
                showName=row["showName"],
                folderPath=row["folderPath"],
                tvdbId=row["tvdbId"],
                tmdbId=row["tmdbId"],
                imdbId=row["imdbId"],
                locationState=row["locationState"],
            )
            for row in rows
        ]

    def catalogueRetargetPath(self, source: Path, destination: Path) -> None:
        """Point catalogue rows at a folder or file this application has moved.

        The destination becomes current and receives provider IDs from the
        source when the destination does not already have them. The source row
        stays in the catalogue as stale. A catalogue that does not exist yet
        is left uncreated.
        """

        if source == destination or _pathIsInside(destination, source):
            return
        if not self.databasePath.is_file():
            return
        scannedAt = _timestampNow()
        with self._databaseConnect() as connection:
            catalogueSchemaApply(connection)
            connection.execute("BEGIN IMMEDIATE")
            _moviePathRetarget(connection, source, destination, scannedAt)
            _seriesPathRetarget(connection, source, destination, scannedAt)
            _episodePathsRetarget(connection, source, destination, scannedAt)
            connection.commit()

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
    # Existing libraries have not been checked against a root listing yet.
    for table in ("movieItem", "tvSeries", "tvEpisode"):
        _catalogueColumnEnsure(
            connection,
            table,
            "locationState",
            "TEXT NOT NULL DEFAULT 'unverified'",
        )


def _catalogueColumnEnsure(
    connection: sqlite3.Connection, table: str, column: str, sqlType: str
) -> None:
    """Add *column* to *table* when an older catalogue file lacks it."""

    existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sqlType}")


## movies


def _moviesCollect(
    movieDirs: list[Path], identity
) -> tuple[list[MovieCatalogueRecord], list[CatalogueRootCoverage]]:
    """Walk movie storage roots and record known movie metadata."""

    folders: list[Path] = []
    coverage: list[CatalogueRootCoverage] = []
    for root in movieDirs:
        children, rootCoverage = _storageRootChildren(Path(root), "movie")
        coverage.append(rootCoverage)
        if children is not None:
            folders.extend(children)

    progress = TerminalProgress(len(folders), "Cataloguing movie library")
    records: list[MovieCatalogueRecord] = []
    seen: set[str] = set()
    diagnostics = []
    try:
        with _bufferCatalogueDiagnostics() as diagnostics:
            for completed, folder in enumerate(folders):
                progress.render(completed, folder.name)
                record = _movieFromFolder(folder, identity)
                if record is not None and record.folderPath not in seen:
                    seen.add(record.folderPath)
                    records.append(record)
                progress.render(completed + 1, folder.name)
    finally:
        progress.finish()
    _flushCatalogueDiagnostics(diagnostics)

    records.sort(
        key=lambda item: (item.title.lower(), item.year or "", item.folderPath)
    )
    return records, coverage


def _movieFromFolder(folder: Path, identity) -> Optional[MovieCatalogueRecord]:
    """Build a movie row from MCM, the metadata library, then folder/file names."""

    videos = _videoFiles(folder, recursive=False)
    videoPath = videos[0] if videos else None
    xmlPath = folder / "movie.xml"
    parsedFolder = MOVIE_FOLDER_NAME.match(folder.name)
    from .showFolders import restoreLeadingThe

    folderTitle = parsedFolder.group("title").strip() if parsedFolder else None
    folderHints = {
        "type": "movie",
        "title": restoreLeadingThe(folderTitle) if folderTitle else None,
        "year": parsedFolder.group("year") if parsedFolder else None,
    }
    filenameHints = identity.parseMovieFilename(videoPath.name) if videoPath else None
    hintFile = videoPath or (xmlPath if xmlPath.is_file() else None)
    mcm = identity._readMovieMcmHints(hintFile) if hintFile else None
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
    return MovieCatalogueRecord(
        title=title,
        year=resolved.get("year"),
        folderPath=str(folder),
        videoPath=str(videoPath) if videoPath else None,
        xmlPath=str(xmlPath) if xmlPath.is_file() else None,
        imdbId=resolved.get("imdbId"),
        tmdbId=resolved.get("tmdbId"),
    )


def _moviesReconcile(
    connection: sqlite3.Connection,
    movies: list[MovieCatalogueRecord],
    scannedAt: str,
    coverage: list[CatalogueRootCoverage],
) -> None:
    """Upsert movies from authoritative roots and mark absent ones stale."""

    movies = _providerIdsPreserve(
        connection, "movieItem", "folderPath", movies, ("imdbId", "tmdbId")
    )
    connection.executemany(
        """
        INSERT INTO movieItem (
            title, year, folderPath, videoPath, xmlPath, imdbId, tmdbId, scannedAt,
            locationState
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folderPath) DO UPDATE SET
            title = excluded.title,
            year = excluded.year,
            videoPath = excluded.videoPath,
            xmlPath = excluded.xmlPath,
            imdbId = excluded.imdbId,
            tmdbId = excluded.tmdbId,
            scannedAt = excluded.scannedAt,
            locationState = excluded.locationState
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
                LOCATION_CURRENT,
            )
            for item in movies
        ],
    )
    staleCount = _markAbsentStale(
        connection,
        "movieItem",
        "folderPath",
        {item.folderPath for item in movies},
        _authoritativeRoots(coverage),
        scannedAt,
    )
    if staleCount:
        logger.value("stale movie locations", staleCount)


## tv


def _tvCollect(videoDirs: list[Path], identity) -> tuple[
    list[TvEpisodeCatalogueRecord],
    list[TvSeriesCatalogueRecord],
    list[CatalogueRootCoverage],
    list[Path],
]:
    """Walk TV storage roots and record known series and episode metadata.

    The fourth value lists directories whose contents could not be read.
    ``os.walk`` hides those errors unless ``onerror`` records them, and an
    unread directory is not evidence that the episodes inside it are gone.
    """

    shows: list[Path] = []
    coverage: list[CatalogueRootCoverage] = []
    for root in videoDirs:
        children, rootCoverage = _storageRootChildren(Path(root), "tv")
        coverage.append(rootCoverage)
        if children is not None:
            shows.extend(children)

    progress = TerminalProgress(len(shows), "Cataloguing TV library")
    episodes: list[TvEpisodeCatalogueRecord] = []
    seriesByFolder: dict[str, TvSeriesCatalogueRecord] = {}
    seen: set[str] = set()
    incompleteDirectories: list[Path] = []
    diagnostics = []
    try:
        with _bufferCatalogueDiagnostics() as diagnostics:
            for completed, showDir in enumerate(shows):
                progress.render(completed, showDir.name)
                folderPath = str(showDir)
                seriesByFolder[folderPath] = _tvSeriesFromFolder(showDir, identity)

                def _onShowWalkError(error: OSError, showDir: Path = showDir) -> None:
                    filename = error.filename
                    incompleteDirectories.append(
                        Path(filename) if filename else showDir
                    )
                    logger.value(
                        "show subtree skipped",
                        f"{filename or showDir} ({error.strerror or error.__class__.__name__})",
                    )

                for dirPath, dirNames, fileNames in os.walk(
                    showDir, onerror=_onShowWalkError
                ):
                    dirNames[:] = [
                        name for name in dirNames if not name.startswith(".")
                    ]
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
                progress.render(completed + 1, showDir.name)
    finally:
        progress.finish()
    _flushCatalogueDiagnostics(diagnostics)
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
    return episodes, series, coverage, incompleteDirectories


def _tvEpisodeFromFile(
    path: Path, showDir: Path, seasonHint: Optional[int], identity
) -> TvEpisodeCatalogueRecord:
    """Build an episode row from MCM, the metadata library, then names."""

    from .showFolders import restoreLeadingThe

    folderHints = {
        "type": "tv",
        "showName": restoreLeadingThe(showDir.name),
        "season": seasonHint,
        "episode": None,
        "episodeTitle": None,
    }
    filenameHints = identity.parseTvFilename(path.name)
    mcm = identity._readTvMcmHints(path, evidenceOnly=True, showDir=showDir)
    if mcm and mcm.get("type") != "tv":
        mcm = None
    seed = _knownMetadataApply(
        identity,
        mcm=mcm,
        library=None,
        filename=filenameHints,
        folder=folderHints,
    )
    seriesLibrary = identity._firstStoredMetadataRecord(
        identity._loadMetadataLibrary()["tv"]["series"],
        identity._tvSeriesLibraryKeys(seed),
    )
    # Known series IDs can locate episodes stored only under a provider key.
    episodeSeed = identity._mergeMetadata(
        mcm, identity._mergeMetadata(_providerAliasesNormalise(seriesLibrary), seed)
    )
    episodeLibrary = identity._firstStoredMetadataRecord(
        identity._loadMetadataLibrary()["tv"]["episodes"],
        identity._tvEpisodeLibraryKeys(episodeSeed),
    )
    # A series can supply a show name, never episode provider IDs.
    library = identity._mergeMetadata(
        episodeLibrary, {"showName": (seriesLibrary or {}).get("showName")}
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
        tvdbEpisodeId=_tvIdText(resolved.get("tvdbEpisodeId")),
        tmdbEpisodeId=_tvIdText(resolved.get("tmdbEpisodeId")),
        imdbId=_tvIdText(resolved.get("imdbId")),
    )


def _tvReconcile(
    connection: sqlite3.Connection,
    episodes: list[TvEpisodeCatalogueRecord],
    series: list[TvSeriesCatalogueRecord],
    scannedAt: str,
    coverage: list[CatalogueRootCoverage],
    incompleteDirectories: list[Path],
) -> None:
    """Upsert TV rows from authoritative roots and mark absent ones stale."""

    series = _providerIdsPreserve(
        connection, "tvSeries", "folderPath", series, ("tvdbId", "tmdbId", "imdbId")
    )
    episodes = _providerIdsPreserve(
        connection,
        "tvEpisode",
        "filePath",
        episodes,
        ("tvdbEpisodeId", "tmdbEpisodeId", "imdbId"),
    )
    roots = _authoritativeRoots(coverage)
    _seriesUpsert(connection, series, scannedAt)
    _episodeUpsert(connection, episodes, scannedAt)
    staleSeries = _markAbsentStale(
        connection,
        "tvSeries",
        "folderPath",
        {item.folderPath for item in series},
        roots,
        scannedAt,
    )
    staleEpisodes = _markAbsentStale(
        connection,
        "tvEpisode",
        "filePath",
        {item.filePath for item in episodes},
        roots,
        scannedAt,
        extraPathColumn="seriesFolderPath",
        withheldRoots=incompleteDirectories,
    )
    if staleSeries:
        logger.value("stale tv locations", staleSeries)
    if staleEpisodes:
        logger.value("stale tv episodes", staleEpisodes)


def _tvSeriesFromFolder(showDir: Path, identity) -> TvSeriesCatalogueRecord:
    """Build a series row from MCM and the metadata library."""

    from .showFolders import restoreLeadingThe

    folderHints = {"type": "tv", "showName": restoreLeadingThe(showDir.name)}
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

    # Normalise TVDB aliases within each source before merging priorities.
    mcm = _providerAliasesNormalise(mcm)
    library = _providerAliasesNormalise(library)
    resolved = dict(folder or {})
    resolved = identity._mergeMetadata(filename, resolved)
    resolved = identity._mergeMetadata(library, resolved)
    resolved = identity._mergeMetadata(mcm, resolved)
    return resolved or {}


def _providerAliasesNormalise(metadata: Optional[dict]) -> Optional[dict]:
    """Map organiser TVDB aliases without confusing local database keys."""
    if metadata is None:
        return None
    result = dict(metadata)
    for field, alias in (("tvdbId", "seriesId"), ("tvdbEpisodeId", "episodeId")):
        result[field] = result.get(field) or result.get(alias)
        result[alias] = result.get(field)
    return result


def _providerIdsPreserve(
    connection: sqlite3.Connection,
    table: str,
    localKey: str,
    records: list,
    fields: tuple[str, ...],
) -> list:
    """Carry durable IDs forward by stable path, never stale descriptions."""
    # Read before writing the snapshot. SQL identifiers are internal constants;
    # filesystem values never enter SQL text.
    existing = {
        row[localKey]: dict(row)
        for row in connection.execute(
            f"SELECT {localKey}, {', '.join(fields)} FROM {table}"
        )
    }
    return [
        replace(
            item,
            **{
                field: getattr(item, field)
                or existing.get(getattr(item, localKey), {}).get(field)
                for field in fields
            },
        )
        for item in records
    ]


## locations


def catalogueRecordMove(source: Path, destination: Path, *, dryRun: bool) -> None:
    """Remember a confirmed media move. Dry-run leaves the catalogue unchanged."""

    if dryRun:
        return
    MediaCatalogue().catalogueRetargetPath(source, destination)


def _authoritativeRoots(coverage: list[CatalogueRootCoverage]) -> list[Path]:
    """Return roots whose directories were listed successfully."""

    return [Path(item.rootPath) for item in coverage if item.outcome == "authoritative"]


def _coverageStore(
    connection: sqlite3.Connection,
    coverage: list[CatalogueRootCoverage],
    scannedAt: str,
) -> None:
    """Record the latest outcome for each reconciled root."""

    connection.executemany(
        """
        INSERT INTO catalogueScanRoot (rootPath, kind, scannedAt, outcome)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(rootPath, kind) DO UPDATE SET
            scannedAt = excluded.scannedAt,
            outcome = excluded.outcome
        """,
        [(item.rootPath, item.kind, scannedAt, item.outcome) for item in coverage],
    )


def _episodePathsRetarget(
    connection: sqlite3.Connection,
    source: Path,
    destination: Path,
    scannedAt: str,
) -> None:
    """Copy episode identity onto paths moved with *source* and mark the old rows stale."""

    rows = connection.execute("""
        SELECT seriesFolderPath, showName, season, episode, episodeTitle, filePath,
               tvdbEpisodeId, tmdbEpisodeId, imdbId
        FROM tvEpisode
        """).fetchall()
    for row in rows:
        newFile = _pathWithNewPrefix(row["filePath"], source, destination)
        if newFile is None or newFile == row["filePath"]:
            continue
        newSeries = _pathWithNewPrefix(row["seriesFolderPath"], source, destination)
        if newSeries is None:
            newSeries = row["seriesFolderPath"]
        containing = _seriesFolderContaining(connection, newFile)
        if containing is not None:
            newSeries = containing
        _episodeIdentityMove(connection, row, newFile, newSeries, scannedAt)


def _episodeIdentityMove(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    newFile: str,
    newSeries: str,
    scannedAt: str,
) -> None:
    """Insert the moved episode as current and retain the old path as stale."""

    connection.execute(
        """
        INSERT INTO tvEpisode (
            seriesFolderPath, showName, season, episode, episodeTitle, filePath,
            tvdbEpisodeId, tmdbEpisodeId, imdbId, scannedAt, locationState
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(filePath) DO UPDATE SET
            tvdbEpisodeId = COALESCE(tvEpisode.tvdbEpisodeId, excluded.tvdbEpisodeId),
            tmdbEpisodeId = COALESCE(tvEpisode.tmdbEpisodeId, excluded.tmdbEpisodeId),
            imdbId = COALESCE(tvEpisode.imdbId, excluded.imdbId),
            scannedAt = excluded.scannedAt,
            locationState = excluded.locationState
        """,
        (
            newSeries,
            row["showName"],
            row["season"],
            row["episode"],
            row["episodeTitle"],
            newFile,
            row["tvdbEpisodeId"],
            row["tmdbEpisodeId"],
            row["imdbId"],
            scannedAt,
            LOCATION_CURRENT,
        ),
    )
    connection.execute(
        """
        UPDATE tvEpisode
        SET locationState = ?, scannedAt = ?
        WHERE filePath = ?
        """,
        (LOCATION_STALE, scannedAt, row["filePath"]),
    )


def _episodeUpsert(
    connection: sqlite3.Connection,
    episodes: list[TvEpisodeCatalogueRecord],
    scannedAt: str,
) -> None:
    """Insert or refresh episode rows found by the current scan."""

    connection.executemany(
        """
        INSERT INTO tvEpisode (
            seriesFolderPath, showName, season, episode, episodeTitle, filePath,
            tvdbEpisodeId, tmdbEpisodeId, imdbId, scannedAt, locationState
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(filePath) DO UPDATE SET
            seriesFolderPath = excluded.seriesFolderPath,
            showName = excluded.showName,
            season = excluded.season,
            episode = excluded.episode,
            episodeTitle = excluded.episodeTitle,
            tvdbEpisodeId = excluded.tvdbEpisodeId,
            tmdbEpisodeId = excluded.tmdbEpisodeId,
            imdbId = excluded.imdbId,
            scannedAt = excluded.scannedAt,
            locationState = excluded.locationState
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
                LOCATION_CURRENT,
            )
            for item in episodes
        ],
    )


def _locationStateClause(
    states: Optional[tuple[str, ...]],
) -> tuple[str, tuple[str, ...]]:
    """Return a parameterised filter for catalogue location states."""

    selected = VISIBLE_LOCATION_STATES if states is None else states
    if any(state not in LOCATION_STATES for state in selected):
        raise ValueError(f"unknown location state: {selected}")
    if not selected:
        return "1 = 0", ()
    marks = ", ".join("?" for _ in selected)
    return f"locationState IN ({marks})", tuple(selected)


def _markAbsentStale(
    connection: sqlite3.Connection,
    table: str,
    pathColumn: str,
    freshPaths: set[str],
    roots: list[Path],
    scannedAt: str,
    *,
    extraPathColumn: Optional[str] = None,
    withheldRoots: Optional[list[Path]] = None,
) -> int:
    """Mark rows under listed roots stale when the scan did not see them.

    *withheldRoots* are directories the scan could not read. Rows inside them
    stay as they were, because their absence was not observed.
    """

    if not roots:
        return 0
    protected = withheldRoots or []
    columns = (
        pathColumn if extraPathColumn is None else f"{pathColumn}, {extraPathColumn}"
    )
    rows = connection.execute(f"SELECT {columns} FROM {table}").fetchall()
    stalePaths = []
    for row in rows:
        path = row[pathColumn]
        if path in freshPaths:
            continue
        if _pathWithinRoots(path, protected):
            continue
        if extraPathColumn is not None and _pathWithinRoots(
            row[extraPathColumn], protected
        ):
            continue
        governed = _pathWithinRoots(path, roots)
        if not governed and extraPathColumn is not None:
            governed = _pathWithinRoots(row[extraPathColumn], roots)
        if governed:
            stalePaths.append(path)
    connection.executemany(
        f"""
        UPDATE {table}
        SET locationState = ?, scannedAt = ?
        WHERE {pathColumn} = ?
        """,
        [(LOCATION_STALE, scannedAt, path) for path in stalePaths],
    )
    return len(stalePaths)


def _moviePathRetarget(
    connection: sqlite3.Connection,
    source: Path,
    destination: Path,
    scannedAt: str,
) -> None:
    """Carry a moved movie folder's identity onto its new path."""

    row = connection.execute(
        """
        SELECT title, year, folderPath, videoPath, xmlPath, imdbId, tmdbId
        FROM movieItem
        WHERE folderPath = ?
        """,
        (str(source),),
    ).fetchone()
    if row is None:
        return
    newFolder = _pathWithNewPrefix(row["folderPath"], source, destination)
    if newFolder is None:
        return
    connection.execute(
        """
        INSERT INTO movieItem (
            title, year, folderPath, videoPath, xmlPath, imdbId, tmdbId, scannedAt,
            locationState
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folderPath) DO UPDATE SET
            imdbId = COALESCE(movieItem.imdbId, excluded.imdbId),
            tmdbId = COALESCE(movieItem.tmdbId, excluded.tmdbId),
            scannedAt = excluded.scannedAt,
            locationState = excluded.locationState
        """,
        (
            row["title"],
            row["year"],
            newFolder,
            (
                _pathWithNewPrefix(row["videoPath"], source, destination)
                if row["videoPath"]
                else None
            ),
            (
                _pathWithNewPrefix(row["xmlPath"], source, destination)
                if row["xmlPath"]
                else None
            ),
            row["imdbId"],
            row["tmdbId"],
            scannedAt,
            LOCATION_CURRENT,
        ),
    )
    connection.execute(
        """
        UPDATE movieItem
        SET locationState = ?, scannedAt = ?
        WHERE folderPath = ?
        """,
        (LOCATION_STALE, scannedAt, row["folderPath"]),
    )


def _pathIsInside(path: Path, parent: Path) -> bool:
    """Return True when *path* is strictly beneath *parent*."""

    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return path != parent


def _pathWithNewPrefix(
    path: Optional[str], source: Path, destination: Path
) -> Optional[str]:
    """Return *path* rewritten under *destination* when it lives under *source*."""

    if path is None:
        return None
    try:
        relative = Path(path).relative_to(source)
    except ValueError:
        return None
    return str(destination / relative)


def _pathWithinRoots(path: Optional[str], roots: list[Path]) -> bool:
    """Return True when *path* is a root or one of its descendants."""

    if path is None:
        return False
    candidate = Path(path)
    for root in roots:
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        return True
    return False


def _seriesFolderContaining(connection: sqlite3.Connection, path: str) -> Optional[str]:
    """Return the longest catalogued show folder that contains *path*."""

    matches = []
    for row in connection.execute("SELECT folderPath FROM tvSeries"):
        folder = row["folderPath"]
        try:
            Path(path).relative_to(folder)
        except ValueError:
            continue
        matches.append(folder)
    if not matches:
        return None
    return max(matches, key=len)


def _seriesPathRetarget(
    connection: sqlite3.Connection,
    source: Path,
    destination: Path,
    scannedAt: str,
) -> None:
    """Carry a moved show folder's identity onto its new path."""

    row = connection.execute(
        """
        SELECT showName, folderPath, tvdbId, tmdbId, imdbId
        FROM tvSeries
        WHERE folderPath = ?
        """,
        (str(source),),
    ).fetchone()
    if row is None:
        return
    newFolder = _pathWithNewPrefix(row["folderPath"], source, destination)
    if newFolder is None:
        return
    connection.execute(
        """
        INSERT INTO tvSeries (
            showName, folderPath, tvdbId, tmdbId, imdbId, scannedAt, locationState
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folderPath) DO UPDATE SET
            tvdbId = COALESCE(tvSeries.tvdbId, excluded.tvdbId),
            tmdbId = COALESCE(tvSeries.tmdbId, excluded.tmdbId),
            imdbId = COALESCE(tvSeries.imdbId, excluded.imdbId),
            scannedAt = excluded.scannedAt,
            locationState = excluded.locationState
        """,
        (
            row["showName"],
            newFolder,
            row["tvdbId"],
            row["tmdbId"],
            row["imdbId"],
            scannedAt,
            LOCATION_CURRENT,
        ),
    )
    connection.execute(
        """
        UPDATE tvSeries
        SET locationState = ?, scannedAt = ?
        WHERE folderPath = ?
        """,
        (LOCATION_STALE, scannedAt, row["folderPath"]),
    )


def _seriesUpsert(
    connection: sqlite3.Connection,
    series: list[TvSeriesCatalogueRecord],
    scannedAt: str,
) -> None:
    """Insert or refresh series rows found by the current scan."""

    connection.executemany(
        """
        INSERT INTO tvSeries (
            showName, folderPath, tvdbId, tmdbId, imdbId, scannedAt, locationState
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folderPath) DO UPDATE SET
            showName = excluded.showName,
            tvdbId = excluded.tvdbId,
            tmdbId = excluded.tmdbId,
            imdbId = excluded.imdbId,
            scannedAt = excluded.scannedAt,
            locationState = excluded.locationState
        """,
        [
            (
                item.showName,
                item.folderPath,
                item.tvdbId,
                item.tmdbId,
                item.imdbId,
                scannedAt,
                LOCATION_CURRENT,
            )
            for item in series
        ],
    )


def _storageRootChildren(
    root: Path, kind: str
) -> tuple[Optional[list[Path]], CatalogueRootCoverage]:
    """List child directories, or record why this root is not authoritative."""

    coverage = CatalogueRootCoverage(str(root), kind, "authoritative")
    if not root.is_dir():
        coverage = CatalogueRootCoverage(str(root), kind, "unavailable")
        logger.value("storage root skipped", f"{root} ({coverage.outcome})")
        return None, coverage
    try:
        children = [path for path in sorted(root.iterdir()) if path.is_dir()]
    except OSError:
        coverage = CatalogueRootCoverage(str(root), kind, "error")
        logger.value("storage root skipped", f"{root} ({coverage.outcome})")
        return None, coverage
    return children, coverage


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
