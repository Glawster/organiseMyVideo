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


def testLocateMovieThroughPublicCli(tmp_path, capsys):
    from organiseMyVideo.cli import main
    from organiseMyVideo.mediaLocate import locateMovie

    root = tmp_path / "Movies"
    for name in ("Zone 414 (2021)", "Zone 414 Returns (2026)"):
        folder = root / name
        folder.mkdir(parents=True)
        (folder / f"{name}.mkv").write_bytes(b"movie")
    catalogue = MediaCatalogue()
    catalogue.catalogueReplaceFromStorage([root], [])

    matches = locateMovie("  zOnE 414  ", catalogue=catalogue)
    assert [item.name for item in matches] == [
        "Zone 414 (2021)",
        "Zone 414 Returns (2026)",
    ]
    assert [item.state for item in matches] == ["current", "current"]
    assert main(["media", "locate", "--movie", "Zone 414 (2021)"]) == 0
    output = capsys.readouterr().out
    assert "Zone 414 (2021)" in output
    assert str(root / "Zone 414 (2021)") in output
    assert "current" in output
    assert "Returns" not in output

    missing = root / "Zone 414 (2021)"
    (missing / "Zone 414 (2021).mkv").unlink()
    missing.rmdir()
    assert locateMovie("Zone 414 (2021)")[0].state == "unverified"
    catalogue.catalogueReplaceFromStorage([root], [])
    assert main(["media", "locate", "--movie", "Zone 414 (2021)"]) == 0
    assert "stale" in capsys.readouterr().out
    assert main(["media", "locate", "--movie", "Unknown movie"]) == 1
    assert (
        "Movie not found in media catalogue: Unknown movie" in capsys.readouterr().err
    )
    assert locateMovie("   ") == []


def testLocateMovieAndShowAreMutuallyExclusive():
    import pytest
    from organiseMyVideo.cli import main

    with pytest.raises(SystemExit) as error:
        main(["media", "locate", "--movie", "Zone", "--show", "Lanterns"])
    assert error.value.code == 2
