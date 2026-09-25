"""Tests for catalogue-backed media location queries."""

from pathlib import Path

from organiseMyVideo.mediaCatalogue import MediaCatalogue
from organiseMyVideo.mediaLocate import locateTvShow


def _catalogueWithShows(tmp_path: Path) -> MediaCatalogue:
    """Return a catalogue populated from a small TV library."""

    firstRoot = tmp_path / "TV1"
    secondRoot = tmp_path / "TV2"

    lanterns = firstRoot / "Lanterns"
    lanterns.mkdir(parents=True)
    (lanterns / "Lanterns.S01E01.mkv").touch()

    lanterns2026 = secondRoot / "Lanterns 2026"
    lanterns2026.mkdir(parents=True)
    (lanterns2026 / "Lanterns.2026.S01E01.mkv").touch()

    catalogue = MediaCatalogue(tmp_path / "mediaCatalogue.sqlite")
    catalogue.catalogueReplaceFromStorage([], [firstRoot, secondRoot])
    return catalogue


def testLocateTvShowReturnsCanonicalFolder(tmp_path: Path):
    catalogue = _catalogueWithShows(tmp_path)

    matches = locateTvShow("Lanterns", catalogue=catalogue)

    assert [match.name for match in matches] == ["Lanterns", "Lanterns 2026"]
    assert matches[0].folderPath == str(tmp_path / "TV1" / "Lanterns")
    assert matches[1].folderPath == str(tmp_path / "TV2" / "Lanterns 2026")


def testLocateTvShowIsCaseInsensitive(tmp_path: Path):
    catalogue = _catalogueWithShows(tmp_path)

    matches = locateTvShow("  lAnTeRnS  ", catalogue=catalogue)

    assert [match.name for match in matches] == ["Lanterns", "Lanterns 2026"]


def testLocateTvShowReturnsPartialNameMatches(tmp_path: Path):
    catalogue = _catalogueWithShows(tmp_path)

    matches = locateTvShow("2026", catalogue=catalogue)

    assert [match.name for match in matches] == ["Lanterns 2026"]


def testLocateTvShowReturnsNoMatchForUnknownShow(tmp_path: Path):
    catalogue = _catalogueWithShows(tmp_path)

    assert locateTvShow("The Pitt", catalogue=catalogue) == []
