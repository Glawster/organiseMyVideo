"""Locate canonical media folders from the persisted media catalogue."""

from __future__ import annotations

from dataclasses import dataclass

from .mediaCatalogue import MediaCatalogue


@dataclass(frozen=True)
class MediaLocation:
    """One catalogue location returned by a media lookup."""

    name: str
    folderPath: str


def locateTvShow(
    showName: str, *, catalogue: MediaCatalogue | None = None
) -> list[MediaLocation]:
    """Return catalogue folders whose show names match *showName*.

    Matching is case-insensitive and ignores leading/trailing whitespace.
    Exact matches and names containing the requested text are returned so
    similarly named shows are shown together. The catalogue is authoritative:
    this function does not scan the filesystem.
    """

    requested = showName.strip().casefold()
    if not requested:
        return []

    mediaCatalogue = catalogue or MediaCatalogue()
    matches = [
        MediaLocation(name=row.showName, folderPath=row.folderPath)
        for row in mediaCatalogue.catalogueTvSeriesList()
        if requested in row.showName.strip().casefold()
    ]
    return sorted(
        matches,
        key=lambda item: (
            item.name.strip().casefold() != requested,
            item.name.casefold(),
            item.folderPath.casefold(),
        ),
    )
