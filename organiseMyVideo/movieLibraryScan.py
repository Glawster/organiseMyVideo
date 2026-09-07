"""Live, in-memory movie library scanning for maintenance workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .mediaCatalogue import (
    MovieCatalogueRecord,
    _catalogueIdentitySource,
    _moviesCollect,
)
from .video import VideoMixin


@dataclass(frozen=True)
class MovieLibrarySnapshot:
    """One read-only in-memory view of the current movie storage roots."""

    movies: tuple[MovieCatalogueRecord, ...]

    def catalogueMoviesList(self) -> list[MovieCatalogueRecord]:
        """Return movie rows using the catalogue-compatible interface."""

        return list(self.movies)


def discoverMovieStorageLocations() -> list[Path]:
    """Return current movie roots using the application's storage discovery."""

    scanner = VideoMixin.__new__(VideoMixin)
    movieDirs, _videoDirs = scanner.scanStorageLocations()
    return list(movieDirs)


def scanMovieLibrary(
    movieDirs: Iterable[Path] | None = None,
) -> MovieLibrarySnapshot:
    """Scan current movie storage into records without writing SQLite state."""

    roots = (
        discoverMovieStorageLocations()
        if movieDirs is None
        else [Path(path) for path in movieDirs]
    )
    movies = _moviesCollect(roots, _catalogueIdentitySource())
    return MovieLibrarySnapshot(movies=tuple(movies))
