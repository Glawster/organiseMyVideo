"""REQ-035: a different movie title or year is not applied as a rename."""

import logging
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from organiseMyVideo import VideoOrganizer
from organiseMyVideo.showFolders import movieFilesystemSafeTitle

from organiseMyVideo.movieIdentity import (
    MOVIE_IDENTITY_AGREE,
    MOVIE_IDENTITY_CONFLICT,
    MOVIE_IDENTITY_PRESERVE_CASE,
    movieIdentityClassify,
    movieTitleIdentity,
)

YEAR_CONFLICTS = (
    ("Call of the Wild, The (1972)", "Call of the Wild, The", "1975"),
    ("Carry On Matron (1972)", "Carry On Matron", "2007"),
    ("Boss Level (2021)", "Boss Level", "2020"),
    ("Chernobyl - Abyss (2021)", "Chernobyl - Abyss", "2022"),
)


def _movieXml(
    title: str,
    year: str,
    *,
    imdbId: str | None = None,
    tmdbId: str | None = None,
    runtimeTag: str | None = None,
    runtime: str | None = None,
) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<Title>",
        f"  <LocalTitle>{title}</LocalTitle>",
        f"  <ProductionYear>{year}</ProductionYear>",
    ]
    if imdbId:
        lines.append(f"  <IMDbId>{imdbId}</IMDbId>")
    if tmdbId:
        lines.append(f"  <TMDbId>{tmdbId}</TMDbId>")
    if runtimeTag and runtime:
        lines.append(f"  <{runtimeTag}>{runtime}</{runtimeTag}>")
    lines.append("</Title>")
    return "\n".join(lines) + "\n"


def _storedMovie(
    root: Path,
    folderName: str,
    xml: str,
    *,
    fileName: str | None = None,
) -> tuple[Path, Path, Path]:
    folder = root / folderName
    folder.mkdir(parents=True)
    video = folder / (fileName or f"{folderName}.mkv")
    video.write_bytes(b"movie")
    metadata = folder / "movie.xml"
    metadata.write_text(xml, encoding="utf-8")
    return folder, video, metadata


def testFilesystemSafeMovieTitlePreservesValidPunctuationSpacing():
    assert movieFilesystemSafeTitle("Battlestar Galactica - Blood & Chrome") == (
        "Battlestar Galactica - Blood & Chrome"
    )
    assert movieFilesystemSafeTitle("Black '47") == "Black '47"
    assert movieFilesystemSafeTitle("Highlander - The Source (Movie 2007)") == (
        "Highlander - The Source (Movie 2007)"
    )
    assert movieFilesystemSafeTitle("Mr. & Mrs. Smith") == "Mr. & Mrs. Smith"
    assert movieFilesystemSafeTitle("Planes, Trains & Automobiles") == (
        "Planes, Trains & Automobiles"
    )


def testFilesystemSafeMovieTitleRemovesOnlyUnsupportedCharacters():
    assert movieFilesystemSafeTitle("Why Him?") == "Why Him"
    assert movieFilesystemSafeTitle("Casual Sex?") == "Casual Sex"
    assert movieFilesystemSafeTitle("Thunderbolts*") == "Thunderbolts"
    assert movieFilesystemSafeTitle("Nativity 3 - Dude, Where's My Donkey?!") == (
        "Nativity 3 - Dude, Where's My Donkey!"
    )


def testMovieTitleIdentityIgnoresPunctuationArticlesAndCase():
    assert movieTitleIdentity("13 minutes") != movieTitleIdentity("One Second Forever")
    assert movieTitleIdentity("Call of the Wild, The") == movieTitleIdentity(
        "The Call of the Wild"
    )
    assert movieTitleIdentity("Call of the Wild") != movieTitleIdentity("Call of Wild")
    assert movieTitleIdentity("Chernobyl - Abyss") == movieTitleIdentity(
        "Chernobyl: Abyss"
    )
    assert movieTitleIdentity("6-45") == movieTitleIdentity("6:45")
    assert movieTitleIdentity("Ocean's Eleven") == movieTitleIdentity("Oceans Eleven")
    assert movieTitleIdentity("The Godfather") == movieTitleIdentity("Godfather, The")
    assert movieTitleIdentity("Fast & Furious") != movieTitleIdentity(
        "Fast and Furious"
    )


def testClassifierSeparatesConflictCaseAndSafeNormalisation():
    conflict = movieIdentityClassify("13 minutes", "2021", "One Second Forever", "2021")
    assert conflict.kind == MOVIE_IDENTITY_CONFLICT

    year = movieIdentityClassify(
        "Call of the Wild, The", "1972", "Call of the Wild, The", "1975"
    )
    assert year.kind == MOVIE_IDENTITY_CONFLICT
    assert year.currentYear == "1972"
    assert year.proposedYear == "1975"

    preserved = movieIdentityClassify(
        "Anyone But You", "2023", "Anyone but You", "2023"
    )
    assert preserved.kind == MOVIE_IDENTITY_PRESERVE_CASE
    assert preserved.retainedTitle == "Anyone But You"

    upgrade = movieIdentityClassify("inception", "2010", "Inception", "2010")
    assert upgrade.kind == MOVIE_IDENTITY_AGREE

    punctuation = movieIdentityClassify(
        "Example: Movie", "2002", "Example - Movie", "2002"
    )
    assert punctuation.kind == MOVIE_IDENTITY_AGREE

    missingYear = movieIdentityClassify("Inception", None, "Inception", "2010")
    assert missingYear.kind == MOVIE_IDENTITY_AGREE


@pytest.mark.parametrize("dryRun", [True, False])
def testThirteenMinutesIsNotRenamedToOneSecondForever(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, video, metadata = _storedMovie(
        storage,
        "13 minutes (2021)",
        _movieXml(
            "One Second Forever",
            "2021",
            imdbId="tt9990001",
            tmdbId="9990001",
            runtimeTag="RunningTime",
            runtime="100",
        ),
    )
    originalXml = metadata.read_bytes()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with (
        caplog.at_level(logging.INFO),
        patch.object(organizer, "_enrichMovieMetadata") as enrich,
    ):
        stats = organizer.resetMovieMetadata([storage])

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert folder.is_dir()
    assert video.is_file()
    assert not (storage / "One Second Forever (2021)").exists()
    assert metadata.read_bytes() == originalXml
    assert organizer._summaryRenames == []
    enrich.assert_not_called()
    assert "current: 13 minutes (2021)" in caplog.text
    assert "proposed: One Second Forever (2021)" in caplog.text
    assert "evidence: movie.xml" in caplog.text
    assert "imdb: tt9990001" in caplog.text
    assert "tmdb: 9990001" in caplog.text
    assert "runtime: 100" in caplog.text
    assert "renaming movie" not in caplog.text


@pytest.mark.parametrize(
    ("folderName", "title", "proposedYear"),
    YEAR_CONFLICTS,
)
@pytest.mark.parametrize("dryRun", [True, False])
def testReleaseYearChangeIsIdentityConflict(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    folderName: str,
    title: str,
    proposedYear: str,
    dryRun: bool,
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, video, metadata = _storedMovie(
        storage, folderName, _movieXml(title, proposedYear)
    )
    originalXml = metadata.read_bytes()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with (
        caplog.at_level(logging.INFO),
        patch.object(organizer, "_enrichMovieMetadata") as enrich,
    ):
        stats = organizer.resetMovieMetadata([storage])

    assert stats["renamed"] == 0
    assert stats["errors"] == 0
    assert folder.is_dir()
    assert video.is_file()
    assert metadata.read_bytes() == originalXml
    assert organizer._summaryRenames == []
    enrich.assert_not_called()
    assert f"current: {folderName}" in caplog.text
    assert f"proposed: {title} ({proposedYear})" in caplog.text
    assert "evidence: movie.xml" in caplog.text
    assert "renaming movie" not in caplog.text


@pytest.mark.parametrize("dryRun", [True, False])
def testCapitalisedTitleIsNotReplacedByLowerCaseMetadata(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, video, metadata = _storedMovie(
        storage,
        "Anyone But You (2023)",
        _movieXml("Anyone but You", "2023"),
    )
    originalXml = metadata.read_bytes()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with caplog.at_level(logging.INFO):
        stats = organizer.resetMovieMetadata([storage])

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert folder.is_dir()
    assert video.is_file()
    assert not (storage / "Anyone but You (2023)").exists()
    assert metadata.read_bytes() == originalXml
    assert organizer._summaryRenames == []
    assert "movie identity conflict" not in caplog.text
    assert "renaming movie" not in caplog.text


def testPunctuationNormalisationStillRenamesConfirmedMovie(tmp_path: Path):
    organizer = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    storage = tmp_path / "movie1"
    folder, video, _metadata = _storedMovie(
        storage,
        "Example: Movie (2002)",
        _movieXml("Example: Movie", "2002"),
    )

    with patch.object(organizer, "_fetchMovieArtwork"):
        stats = organizer.resetMovieMetadata([storage])

    canonical = storage / "Example - Movie (2002)"
    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert canonical.is_dir()
    assert (canonical / "Example - Movie (2002).mkv").is_file()
    assert not folder.exists()
    assert not video.exists()


def testLeadingTheFolderRenameStillHappensWhenIdentityAgrees(tmp_path: Path):
    organizer = VideoOrganizer(sourceDir=str(tmp_path / "source"), dryRun=False)
    storage = tmp_path / "movie1"
    folder, _video, _metadata = _storedMovie(
        storage,
        "The Godfather (1972)",
        _movieXml("The Godfather", "1972"),
    )

    with patch.object(organizer, "_fetchMovieArtwork"):
        organizer.resetMovieMetadata([storage])

    canonical = storage / "Godfather, The (1972)"
    assert canonical.is_dir()
    assert (canonical / "The Godfather (1972).mkv").is_file()
    assert not folder.exists()


@pytest.mark.parametrize("runtimeTag", ["RunningTime", "Runtime", "Duration"])
def testStoredRuntimeIsAvailableForConflictReport(
    tmp_path: Path, runtimeTag: str, caplog: pytest.LogCaptureFixture
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    _storedMovie(
        storage,
        "Boss Level (2021)",
        _movieXml("Boss Level", "2020", runtimeTag=runtimeTag, runtime="100 min"),
    )
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=True)

    with (
        caplog.at_level(logging.WARNING),
        patch.object(organizer, "_enrichMovieMetadata"),
    ):
        organizer.resetMovieMetadata([storage])

    assert "runtime: 100 min" in caplog.text


@pytest.mark.parametrize("dryRun", [True, False])
def testMoveRefusesUnresolvedMovieIdentity(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    folder, video, metadata = _storedMovie(
        source,
        "13 minutes (2021)",
        _movieXml("One Second Forever", "2021", imdbId="tt9990001"),
    )
    originalXml = metadata.read_bytes()
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)
    movieInfo = {
        "title": "One Second Forever",
        "year": "2021",
        "imdbId": "tt9990001",
        "metadataSource": "mcm",
        "extension": ".mkv",
        "type": "movie",
    }

    with (
        caplog.at_level(logging.INFO),
        patch.object(organizer, "_enrichMovieMetadata") as enrich,
    ):
        moved = organizer.moveMovie(video, movieInfo, [movieStorage], interactive=False)

    assert moved is False
    assert video.is_file()
    assert folder.is_dir()
    assert metadata.read_bytes() == originalXml
    assert not (movieStorage / "One Second Forever (2021)").exists()
    assert organizer._summaryTransfers == []
    enrich.assert_not_called()
    assert "current: 13 minutes (2021)" in caplog.text
    assert "proposed: One Second Forever (2021)" in caplog.text
    assert "evidence: movie.xml" in caplog.text


def testMoveRefusesIdentityChangedByMetadataEnrichment(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    sourceFile = source / "Boss Level (2021).mkv"
    sourceFile.write_bytes(b"movie")
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=False)
    movieInfo = {
        "title": "Boss Level",
        "year": "2021",
        "extension": ".mkv",
        "type": "movie",
    }

    def enrich(movieInfo):
        resolved = dict(movieInfo)
        resolved["year"] = "2020"
        resolved["metadataSource"] = "tmdb"
        return resolved

    with patch.object(organizer, "_enrichMovieMetadata", side_effect=enrich) as mocked:
        moved = organizer.moveMovie(
            sourceFile, movieInfo, [movieStorage], interactive=False
        )

    assert moved is False
    assert sourceFile.is_file()
    assert not (movieStorage / "Boss Level (2020)").exists()
    assert organizer._summaryTransfers == []
    mocked.assert_called_once()


def testMoveKeepsCapitalisedTitle(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    sourceFile = source / "Anyone But You (2023).mkv"
    sourceFile.write_bytes(b"movie")
    movieStorage = tmp_path / "movie1"
    movieStorage.mkdir()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=False)
    movieInfo = {
        "title": "Anyone but You",
        "year": "2023",
        "extension": ".mkv",
        "type": "movie",
    }

    with patch.object(organizer, "_fetchMovieArtwork"):
        moved = organizer.moveMovie(
            sourceFile, movieInfo, [movieStorage], interactive=False
        )

    destination = movieStorage / "Anyone But You (2023)" / "Anyone But You (2023).mkv"
    assert moved is True
    assert destination.is_file()
    assert not (movieStorage / "Anyone but You (2023)").exists()


@pytest.mark.parametrize("dryRun", [True, False])
def testScanRefusesYearIntroducedByMetadataEnrichment(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder = storage / "Example Movie (2002)"
    folder.mkdir(parents=True)
    video = folder / "Example Movie (2002).mkv"
    video.write_bytes(b"movie")
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    def enrich(movieInfo):
        resolved = dict(movieInfo)
        resolved["year"] = "2003"
        resolved["metadataSource"] = "tmdb"
        return resolved

    with (
        caplog.at_level(logging.INFO),
        patch.object(organizer, "_enrichMovieMetadata", side_effect=enrich),
    ):
        stats = organizer.resetMovieMetadata([storage])

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert folder.is_dir()
    assert video.is_file()
    assert not (storage / "Example Movie (2003)").exists()
    assert organizer._summaryRenames == []
    assert "current: Example Movie (2002)" in caplog.text
    assert "proposed: Example Movie (2003)" in caplog.text
    assert "evidence: tmdb" in caplog.text


_UNSAFE_FILENAME_CHARACTERS = set('\\/:*?"<>|')

FILESYSTEM_SAFE_TITLES = (
    (
        "Nativity 3 - Dude, Where's My Donkey?! (2014)",
        "Nativity 3 - Dude, Where's My Donkey?!",
        "2014",
        "Nativity 3 - Dude, Where's My Donkey! (2014)",
    ),
    (
        "TAYLOR SWIFT | THE ERAS TOUR (2023)",
        "TAYLOR SWIFT | THE ERAS TOUR",
        "2023",
        "TAYLOR SWIFT THE ERAS TOUR (2023)",
    ),
    (
        "Thunderbolts* (2025)",
        "Thunderbolts*",
        "2025",
        "Thunderbolts (2025)",
    ),
)


def _rejectUnsafeRename(original):
    """Return a rename spy that fails if a destination still has invalid characters."""

    def _rename(source, destination, **kwargs):
        name = Path(destination).name
        if any(character in name for character in _UNSAFE_FILENAME_CHARACTERS):
            raise OSError(22, "Invalid argument")
        return original(source, destination, **kwargs)

    return _rename


@contextmanager
def _quietMetadata(organizer: VideoOrganizer):
    """Keep a scan on the title already stored, with no artwork lookup."""
    with (
        patch.object(
            organizer, "_enrichMovieMetadata", side_effect=lambda value: dict(value)
        ),
        patch.object(organizer, "_fetchMovieArtwork"),
    ):
        yield


@pytest.mark.parametrize(
    ("folderName", "title", "year", "safeFolder"),
    FILESYSTEM_SAFE_TITLES,
)
@pytest.mark.parametrize("dryRun", [True, False])
def testFilesystemUnsafeTitlesAreSafeBeforeRename(
    tmp_path: Path,
    folderName: str,
    title: str,
    year: str,
    safeFolder: str,
    dryRun: bool,
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, video, _metadata = _storedMovie(storage, folderName, _movieXml(title, year))
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)
    organizer.filesystem.rename = _rejectUnsafeRename(organizer.filesystem.rename)

    with _quietMetadata(organizer):
        stats = organizer.resetMovieMetadata([storage])

    safeFile = f"{safeFolder}.mkv"
    assert stats == {"renamed": 1, "skipped": 0, "errors": 0}
    assert all(
        not any(
            character in Path(destination).name
            for character in _UNSAFE_FILENAME_CHARACTERS
        )
        for _sourcePath, destination in organizer._summaryRenames
    )
    if dryRun:
        assert len(organizer._summaryRenames) == 2
        assert folder.is_dir()
        assert video.is_file()
        assert video.read_bytes() == b"movie"
        return

    canonical = storage / safeFolder
    assert canonical.is_dir()
    assert (canonical / safeFile).is_file()
    assert (canonical / safeFile).read_bytes() == b"movie"
    assert not folder.exists()


@pytest.mark.parametrize("dryRun", [True, False])
def testRemovedCharactersDoNotHideADifferentFilm(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, video, metadata = _storedMovie(
        storage,
        "13 minutes (2021)",
        _movieXml("One Second Forever?", "2021"),
    )
    originalXml = metadata.read_bytes()
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with (
        caplog.at_level(logging.INFO),
        patch.object(organizer, "_enrichMovieMetadata") as enrich,
    ):
        stats = organizer.resetMovieMetadata([storage])

    assert stats == {"renamed": 0, "skipped": 1, "errors": 0}
    assert folder.is_dir()
    assert video.is_file()
    assert metadata.read_bytes() == originalXml
    assert not (storage / "One Second Forever (2021)").exists()
    assert organizer._summaryRenames == []
    enrich.assert_not_called()
    assert "current: 13 minutes (2021)" in caplog.text
    assert "proposed: One Second Forever? (2021)" in caplog.text


@pytest.mark.parametrize("dryRun", [True, False])
def testRemovedCharactersDoNotHideADifferentYear(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, video, _metadata = _storedMovie(
        storage, "Thunderbolts* (2024)", _movieXml("Thunderbolts*", "2025")
    )
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with (
        caplog.at_level(logging.INFO),
        patch.object(organizer, "_enrichMovieMetadata") as enrich,
    ):
        stats = organizer.resetMovieMetadata([storage])

    assert stats["renamed"] == 0
    assert stats["errors"] == 0
    assert folder.is_dir()
    assert video.is_file()
    assert not (storage / "Thunderbolts (2025)").exists()
    assert organizer._summaryRenames == []
    enrich.assert_not_called()
    assert "current: Thunderbolts* (2024)" in caplog.text
    assert "proposed: Thunderbolts* (2025)" in caplog.text


@pytest.mark.parametrize("dryRun", [True, False])
def testSampleIsNotRenamedToTheFeature(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, feature, _metadata = _storedMovie(
        storage,
        "Inside Out 2 (2024)",
        _movieXml("Inside Out 2", "2024"),
        fileName="inside.mkv",
    )
    sample = folder / "Sample.mkv"
    sample.write_bytes(b"sample")
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with caplog.at_level(logging.INFO), _quietMetadata(organizer):
        stats = organizer.resetMovieMetadata([storage])

    assert sample.is_file()
    assert sample.read_bytes() == b"sample"
    assert all(
        "Sample.mkv" not in sourcePath
        for sourcePath, _dest in organizer._summaryRenames
    )
    assert "Sample.mkv" not in caplog.text
    assert stats["errors"] == 0
    if dryRun:
        assert stats["errors"] == 0
        assert feature.is_file()
        return
    assert (folder / "Inside Out 2 (2024).mkv").is_file()
    assert (folder / "Inside Out 2 (2024).mkv").read_bytes() == b"movie"
    assert not feature.exists()


@pytest.mark.parametrize("dryRun", [True, False])
def testSameIdentityFolderCollisionIsAMergeCandidate(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    featureFolder = storage / "Inside Out 2 (2024)_"
    featureFolder.mkdir(parents=True)
    feature = featureFolder / "Inside Out 2 (2024).mkv"
    feature.write_bytes(b"movie")
    metadataFolder = storage / "Inside Out 2 (2024)"
    metadataFolder.mkdir()
    (metadataFolder / "movie.xml").write_text(
        _movieXml("Inside Out 2", "2024"), encoding="utf-8"
    )
    (metadataFolder / "folder.jpg").write_bytes(b"artwork")
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with caplog.at_level(logging.INFO), _quietMetadata(organizer):
        stats = organizer.resetMovieMetadata([storage])

    assert stats["renamed"] == 0
    assert stats["errors"] == 0
    assert feature.read_bytes() == b"movie"
    assert (metadataFolder / "movie.xml").is_file()
    assert (metadataFolder / "folder.jpg").read_bytes() == b"artwork"
    assert featureFolder.is_dir()
    assert metadataFolder.is_dir()
    assert organizer._summaryRenames == []
    assert "classification: same-identity merge candidate" in caplog.text
    assert "content: complementary" in caplog.text
    assert "feature file" in caplog.text
    assert "metadata" in caplog.text
    assert "artwork" in caplog.text
    assert str(featureFolder) in caplog.text
    assert str(metadataFolder) in caplog.text


@pytest.mark.parametrize("dryRun", [True, False])
def testExistingFeatureFileIsReportedAsAPossibleDuplicate(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    storage = tmp_path / "movie1"
    folder, feature, _metadata = _storedMovie(
        storage,
        "Inside Out 2 (2024)",
        _movieXml("Inside Out 2", "2024"),
    )
    other = folder / "part2.mkv"
    other.write_bytes(b"other")
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)

    with caplog.at_level(logging.INFO), _quietMetadata(organizer):
        stats = organizer.resetMovieMetadata([storage])

    assert feature.read_bytes() == b"movie"
    assert other.read_bytes() == b"other"
    assert stats["renamed"] == 0
    assert stats["errors"] == 1
    assert "classification: possible duplicate feature file" in caplog.text
    assert "part2.mkv" in caplog.text
    assert str(feature) in caplog.text
    assert organizer._summaryRenames == []


def testSampleCollisionIsIgnoredAncillaryMedia(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    source = tmp_path / "source"
    source.mkdir()
    folder = tmp_path / "Inside Out 2 (2024)"
    folder.mkdir()
    feature = folder / "Inside Out 2 (2024).mkv"
    feature.write_bytes(b"movie")
    sample = folder / "Sample.mkv"
    sample.write_bytes(b"sample")
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=False)
    movieInfo = {
        "title": "Inside Out 2",
        "year": "2024",
        "extension": ".mkv",
        "type": "movie",
    }

    with (
        caplog.at_level(logging.WARNING),
        patch.object(organizer, "_fetchMovieArtwork"),
    ):
        outcome = organizer._resetMovieMetadataForFile(
            sample, resolvedMovieInfo=movieInfo
        )

    assert outcome == "skipped"
    assert sample.read_bytes() == b"sample"
    assert feature.read_bytes() == b"movie"
    assert "classification: ignored ancillary media" in caplog.text
    assert "Sample.mkv" in caplog.text


@pytest.mark.parametrize("dryRun", [True, False])
def testMoveDoesNotOverwriteAnExistingFeatureFile(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, dryRun: bool
):
    source = tmp_path / "source"
    source.mkdir()
    incoming = source / "Inside Out 2 (2024).mkv"
    incoming.write_bytes(b"incoming")
    storage = tmp_path / "movie1"
    existingFolder = storage / "Inside Out 2 (2024)"
    existingFolder.mkdir(parents=True)
    existing = existingFolder / "Inside Out 2 (2024).mkv"
    existing.write_bytes(b"library")
    organizer = VideoOrganizer(sourceDir=str(source), dryRun=dryRun)
    movieInfo = {
        "title": "Inside Out 2",
        "year": "2024",
        "extension": ".mkv",
        "type": "movie",
    }

    with caplog.at_level(logging.INFO), _quietMetadata(organizer):
        moved = organizer.moveMovie(incoming, movieInfo, [storage], interactive=False)

    assert moved is False
    assert incoming.read_bytes() == b"incoming"
    assert existing.read_bytes() == b"library"
    assert organizer._summaryTransfers == []
    assert "classification: possible duplicate feature file" in caplog.text
