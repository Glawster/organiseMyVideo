"""Tests for live, non-persistent movie library scanning used by merge."""

from pathlib import Path
from unittest.mock import patch

from organiseMyVideo.mediaCatalogue import MediaCatalogue
from organiseMyVideo.mediaMerge import mergeDuplicateMovies
from organiseMyVideo.movieLibraryScan import scanMovieLibrary


def testScanMovieLibraryBuildsLiveRecordsWithoutSqlite(tmp_path: Path):
    movieRoot = tmp_path / "movie1"
    folder = movieRoot / "Inception (2010)"
    folder.mkdir(parents=True)
    (folder / "Inception (2010).mkv").write_bytes(b"feature")
    (folder / "movie.xml").write_text(
        "<Title><LocalTitle>Inception</LocalTitle>"
        "<ProductionYear>2010</ProductionYear>"
        "<IMDbId>tt1375666</IMDbId></Title>",
        encoding="utf-8",
    )

    snapshot = scanMovieLibrary([movieRoot])
    movies = snapshot.catalogueMoviesList()

    assert len(movies) == 1
    assert movies[0].title == "Inception"
    assert movies[0].imdbId == "tt1375666"
    assert movies[0].folderPath == str(folder)


def testMovieMergeUsesLiveStorageWhenPersistedCatalogueIsEmpty(tmp_path: Path):
    firstRoot = tmp_path / "movie1"
    secondRoot = tmp_path / "movie2"
    fuller = firstRoot / "Inception (2010)"
    smaller = secondRoot / "Inception (2010)"
    extras = smaller / "Featurettes"
    fuller.mkdir(parents=True)
    extras.mkdir(parents=True)
    (fuller / "Inception (2010).mkv").write_bytes(b"feature")
    (fuller / "movie.xml").write_text(
        "<Title><LocalTitle>Inception</LocalTitle><IMDbId>tt1375666</IMDbId></Title>",
        encoding="utf-8",
    )
    (smaller / "movie.xml").write_text(
        "<Title><LocalTitle>Inception</LocalTitle><IMDbId>tt1375666</IMDbId></Title>",
        encoding="utf-8",
    )
    incoming = extras / "making-of.mkv"
    incoming.write_bytes(b"extra")

    persisted = MediaCatalogue(tmp_path / "empty-catalogue.sqlite")
    with patch(
        "organiseMyVideo.movieLibraryScan.discoverMovieStorageLocations",
        return_value=[firstRoot, secondRoot],
    ):
        stats = mergeDuplicateMovies(catalogue=persisted, dryRun=True)

    assert stats.groupsFound == 1
    assert stats.groupsMerged == 1
    assert incoming.exists()
    assert not persisted.databasePath.exists()
