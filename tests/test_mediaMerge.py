"""Tests for provider-identity TV library merging."""

from io import StringIO
from pathlib import Path

from organiseMyVideo.filesystemOperations import FilesystemOperations
from organiseMyVideo.mediaCatalogue import (
    TvEpisodeCatalogueRecord,
    TvSeriesCatalogueRecord,
)
from organiseMyVideo.mediaMerge import TvLibraryMerger


class _TtyStream(StringIO):
    """In-memory stream treated as a TTY so merge progress actually renders."""

    def isatty(self) -> bool:
        return True


class FakeCatalogue:
    """Small catalogue surface used by merge tests."""

    def __init__(self, series, episodes):
        self.series = list(series)
        self.episodes = list(episodes)

    def catalogueTvSeriesList(self):
        return list(self.series)

    def catalogueTvEpisodesList(self):
        return list(self.episodes)


def _series(path: Path, *, tvdb="123", tmdb=None, imdb=None):
    return TvSeriesCatalogueRecord(
        showName="Grimm",
        folderPath=str(path),
        tvdbId=tvdb,
        tmdbId=tmdb,
        imdbId=imdb,
    )


def _episode(path: Path, show: Path, season: int, episode: int, *, tvdb=None):
    return TvEpisodeCatalogueRecord(
        showName="Grimm",
        seriesFolderPath=str(show),
        season=season,
        episode=episode,
        episodeTitle=None,
        filePath=str(path),
        tvdbEpisodeId=tvdb,
    )


def testMergeChoosesMostCompleteFolderAndMovesUniqueEpisode(tmp_path: Path):
    fuller = tmp_path / "video1" / "TV" / "Grimm"
    smaller = tmp_path / "video2" / "TV" / "Grimm"
    fullerSeason = fuller / "Season 01"
    smallerSeason = smaller / "Season 01"
    fullerSeason.mkdir(parents=True)
    smallerSeason.mkdir(parents=True)
    first = fullerSeason / "Grimm S01E01.mkv"
    second = fullerSeason / "Grimm S01E02.mkv"
    third = smallerSeason / "Grimm S01E03.mkv"
    first.write_bytes(b"one")
    second.write_bytes(b"two")
    third.write_bytes(b"three")

    catalogue = FakeCatalogue(
        [_series(fuller), _series(smaller)],
        [
            _episode(first, fuller, 1, 1),
            _episode(second, fuller, 1, 2),
            _episode(third, smaller, 1, 3),
        ],
    )
    merger = TvLibraryMerger(
        catalogue=catalogue,
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    )

    stats = merger.merge()

    assert (fullerSeason / third.name).read_bytes() == b"three"
    assert not smaller.exists()
    assert stats.groupsFound == 1
    assert stats.groupsMerged == 1
    assert stats.filesMoved == 1
    assert stats.conflicts == 0


def testMergePreservesIdenticalDuplicateEpisodeWithDifferentFilename(tmp_path: Path):
    firstShow = tmp_path / "video1" / "TV" / "Grimm"
    secondShow = tmp_path / "video2" / "TV" / "Grimm"
    firstSeason = firstShow / "Season 01"
    secondSeason = secondShow / "Season 01"
    firstSeason.mkdir(parents=True)
    secondSeason.mkdir(parents=True)
    existing = firstSeason / "Grimm S01E01.mkv"
    duplicate = secondSeason / "episode-one.mkv"
    existing.write_bytes(b"same episode")
    duplicate.write_bytes(b"same episode")

    catalogue = FakeCatalogue(
        [_series(firstShow), _series(secondShow)],
        [
            _episode(existing, firstShow, 1, 1, tvdb="9001"),
            _episode(duplicate, secondShow, 1, 1, tvdb="9001"),
        ],
    )
    stats = TvLibraryMerger(
        catalogue=catalogue,
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    ).merge()

    assert existing.exists()
    assert duplicate.exists()
    assert stats.duplicates == 1
    assert stats.conflicts == 0
    assert stats.groupsMerged == 0


def testMergePreservesConflictingEpisode(tmp_path: Path):
    firstShow = tmp_path / "video1" / "TV" / "Grimm"
    secondShow = tmp_path / "video2" / "TV" / "Grimm"
    firstSeason = firstShow / "Season 01"
    secondSeason = secondShow / "Season 01"
    firstSeason.mkdir(parents=True)
    secondSeason.mkdir(parents=True)
    existing = firstSeason / "Grimm S01E01.mkv"
    conflict = secondSeason / "other-name.mkv"
    existing.write_bytes(b"first copy")
    conflict.write_bytes(b"different copy")

    catalogue = FakeCatalogue(
        [_series(firstShow), _series(secondShow)],
        [
            _episode(existing, firstShow, 1, 1),
            _episode(conflict, secondShow, 1, 1),
        ],
    )
    stats = TvLibraryMerger(
        catalogue=catalogue,
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    ).merge()

    assert existing.exists()
    assert conflict.exists()
    assert stats.duplicates == 0
    assert stats.conflicts == 1


def testMergeDoesNotUseMatchingShowNameWithoutProviderIdentity(tmp_path: Path):
    firstShow = tmp_path / "video1" / "TV" / "Grimm"
    secondShow = tmp_path / "video2" / "TV" / "Grimm"
    firstShow.mkdir(parents=True)
    secondShow.mkdir(parents=True)
    catalogue = FakeCatalogue(
        [_series(firstShow, tvdb=None), _series(secondShow, tvdb=None)],
        [],
    )

    stats = TvLibraryMerger(catalogue=catalogue, dryRun=True).merge()

    assert stats.groupsFound == 0
    assert firstShow.exists()
    assert secondShow.exists()


def testMergeSkipsLinkedGroupWithConflictingProviderIds(tmp_path: Path):
    firstShow = tmp_path / "video1" / "TV" / "Grimm"
    secondShow = tmp_path / "video2" / "TV" / "Grimm"
    firstShow.mkdir(parents=True)
    secondShow.mkdir(parents=True)
    catalogue = FakeCatalogue(
        [
            _series(firstShow, tvdb="123", tmdb="10"),
            _series(secondShow, tvdb="123", tmdb="11"),
        ],
        [],
    )

    stats = TvLibraryMerger(catalogue=catalogue, dryRun=True).merge()

    assert stats.groupsFound == 0
    assert stats.identityConflicts == 1


def testDryRunPlansMovesWithoutChangingStorage(tmp_path: Path):
    fuller = tmp_path / "video1" / "TV" / "Grimm"
    smaller = tmp_path / "video2" / "TV" / "Grimm"
    fullerSeason = fuller / "Season 01"
    smallerSeason = smaller / "Season 01"
    fullerSeason.mkdir(parents=True)
    smallerSeason.mkdir(parents=True)
    existing = fullerSeason / "Grimm S01E01.mkv"
    incoming = smallerSeason / "Grimm S01E02.mkv"
    existing.write_bytes(b"one")
    incoming.write_bytes(b"two")
    filesystem = FilesystemOperations(dryRun=True)
    catalogue = FakeCatalogue(
        [_series(fuller), _series(smaller)],
        [
            _episode(existing, fuller, 1, 1),
            _episode(incoming, smaller, 1, 2),
        ],
    )

    stats = TvLibraryMerger(
        catalogue=catalogue,
        filesystem=filesystem,
        dryRun=True,
    ).merge()

    assert incoming.exists()
    assert not (fullerSeason / incoming.name).exists()
    assert stats.groupsMerged == 1
    assert any(operation.action == "move" for operation in filesystem.operations)


def testMergeDiscardsSourceSeriesXmlWhenDestinationHasOne(tmp_path: Path):
    destinationShow = tmp_path / "video1" / "TV" / "Grimm"
    sourceShow = tmp_path / "video2" / "TV" / "Grimm old"
    destinationShow.mkdir(parents=True)
    sourceShow.mkdir(parents=True)
    destinationSeries = destinationShow / "series.xml"
    sourceSeries = sourceShow / "series.xml"
    destinationSeries.write_text(
        "<Series><SeriesID>123</SeriesID></Series>", encoding="utf-8"
    )
    sourceSeries.write_text(
        "<Series><SeriesID>123</SeriesID><Old>true</Old></Series>", encoding="utf-8"
    )
    (destinationShow / "Grimm S01E01.mkv").write_bytes(b"episode")

    stats = TvLibraryMerger(
        catalogue=FakeCatalogue(
            [_series(destinationShow), _series(sourceShow)],
            [],
        ),
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
    ).merge()

    assert (
        destinationSeries.read_text(encoding="utf-8")
        == "<Series><SeriesID>123</SeriesID></Series>"
    )
    assert not sourceSeries.exists()
    assert not sourceShow.exists()
    assert stats.groupsMerged == 1
    assert stats.conflicts == 0


def testDryRunPlansSourceSeriesXmlRemovalWithoutDeletingIt(tmp_path: Path):
    destinationShow = tmp_path / "video1" / "TV" / "Grimm"
    sourceShow = tmp_path / "video2" / "TV" / "Grimm old"
    destinationShow.mkdir(parents=True)
    sourceShow.mkdir(parents=True)
    (destinationShow / "series.xml").write_text("<Series />", encoding="utf-8")
    sourceSeries = sourceShow / "series.xml"
    sourceSeries.write_text("<Series><Old>true</Old></Series>", encoding="utf-8")
    (destinationShow / "Grimm S01E01.mkv").write_bytes(b"episode")
    filesystem = FilesystemOperations(dryRun=True)

    stats = TvLibraryMerger(
        catalogue=FakeCatalogue(
            [_series(destinationShow), _series(sourceShow)],
            [],
        ),
        filesystem=filesystem,
        dryRun=True,
    ).merge()

    assert sourceSeries.exists()
    assert stats.groupsMerged == 1
    assert stats.conflicts == 0
    assert any(
        operation.action == "remove-file" and operation.source == sourceSeries
        for operation in filesystem.operations
    )


def testMergeProgressShowsWorkBeforeMovingFiles(tmp_path: Path):
    fuller = tmp_path / "video1" / "TV" / "Grimm"
    smaller = tmp_path / "video2" / "TV" / "Grimm (2011) -"
    fullerSeason = fuller / "Season 1"
    smallerSeason = smaller / "Season 1"
    fullerSeason.mkdir(parents=True)
    smallerSeason.mkdir(parents=True)
    existing = fullerSeason / "Grimm S01E01.mkv"
    extra = fullerSeason / "Grimm S01E03.mkv"
    incoming = smallerSeason / "Grimm S01E02.mkv"
    existing.write_bytes(b"one")
    extra.write_bytes(b"three")
    incoming.write_bytes(b"two")
    stream = _TtyStream()

    TvLibraryMerger(
        catalogue=FakeCatalogue(
            [_series(fuller), _series(smaller)],
            [
                _episode(existing, fuller, 1, 1),
                _episode(extra, fuller, 1, 3),
                _episode(incoming, smaller, 1, 2),
            ],
        ),
        filesystem=FilesystemOperations(dryRun=False),
        dryRun=False,
        progressStream=stream,
    ).merge()

    output = stream.getvalue()
    assert "counting entries" in output
    assert "listing" in output
    assert "Grimm S01E02.mkv" in output
    assert "(0/" in output
    assert "(1/" in output or "(2/" in output or "(3/" in output
