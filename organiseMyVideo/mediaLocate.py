"""Locate canonical media folders from the persisted media catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .mediaCatalogue import (
    LOCATION_CURRENT,
    LOCATION_STALE,
    LOCATION_STATES,
    LOCATION_UNVERIFIED,
    MediaCatalogue,
)

_STATE_ORDER = {
    LOCATION_CURRENT: 0,
    LOCATION_UNVERIFIED: 1,
    LOCATION_STALE: 2,
}


@dataclass(frozen=True)
class MediaLocation:
    """One catalogue location returned by a media lookup."""

    name: str
    folderPath: str
    state: str = LOCATION_CURRENT


def locateMovie(
    movieName: str, *, catalogue: MediaCatalogue | None = None
) -> list[MediaLocation]:
    """Return movie folders matching a case-insensitive title or title and year.

    Include all recorded location states and check each folder's presence.
    Exact title matches precede partial matches; years distinguish remakes.
    """
    requested = movieName.strip().casefold()
    if not requested:
        return []
    mediaCatalogue = catalogue or MediaCatalogue()
    matches = []
    exactNames = set()
    for row in mediaCatalogue.catalogueMoviesList(states=LOCATION_STATES):
        name = f"{row.title} ({row.year})" if row.year else row.title
        title = row.title.strip().casefold()
        if requested not in name.strip().casefold():
            continue
        if requested in (title, name.strip().casefold()):
            exactNames.add(name)
        matches.append(
            MediaLocation(
                name=name,
                folderPath=row.folderPath,
                state=_locationVisibility(row.locationState, row.folderPath),
            )
        )
    return sorted(
        matches,
        key=lambda item: (
            item.name not in exactNames,
            item.name.casefold(),
            _STATE_ORDER.get(item.state, 9),
            item.folderPath.casefold(),
        ),
    )


def locateTvShow(
    showName: str | None = None, *, catalogue: MediaCatalogue | None = None
) -> list[MediaLocation]:
    """Return catalogued TV folders, optionally matching *showName*.

    Matching is case-insensitive and ignores leading/trailing whitespace.
    Exact matches and names containing the requested text are returned so
    similarly named shows are shown together. Omit *showName* to return every
    catalogued show. A stored path is not reported as current unless the
    catalogue marks it current and the folder is present.
    """

    requested = None if showName is None else showName.strip().casefold()
    if showName is not None and not requested:
        return []

    mediaCatalogue = catalogue or MediaCatalogue()
    matches = []
    for row in mediaCatalogue.catalogueTvSeriesList(states=LOCATION_STATES):
        if requested is not None and requested not in row.showName.strip().casefold():
            continue
        matches.append(
            MediaLocation(
                name=row.showName,
                folderPath=row.folderPath,
                state=_locationVisibility(row.locationState, row.folderPath),
            )
        )
    return sorted(
        matches,
        key=lambda item: (
            requested is not None and item.name.strip().casefold() != requested,
            item.name.casefold(),
            _STATE_ORDER.get(item.state, 9),
            item.folderPath.casefold(),
        ),
    )


def _locationVisibility(locationState: str, folderPath: str) -> str:
    """Return the state locate should display for one stored folder."""

    exists = Path(folderPath).is_dir()
    if locationState == LOCATION_STALE and not exists:
        return LOCATION_STALE
    if locationState == LOCATION_CURRENT and exists:
        return LOCATION_CURRENT
    return LOCATION_UNVERIFIED
