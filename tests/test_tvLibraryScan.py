"""Tests for live, non-persistent TV library scanning used by merge."""

from pathlib import Path
from unittest.mock import patch

from organiseMyVideo.mediaCatalogue import (
    MediaCatalogue,
    TvSeriesCatalogueRecord,
)
from organiseMyVideo.mediaMerge import mergeDuplicateTvShows
from organiseMyVideo.tvLibraryScan import (
    _resolveMissingSeriesIdentities,
    _seriesLookupName,
    _tvdbExactSeriesId,
    scanTvLibrary,
)


def _seriesWrite(showDir: Path, name: str, seriesId: str) -> None:
    showDir.mkdir(parents=True, exist_ok=True)
    (showDir / "series.xml").write_text(
        f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Series>
    <SeriesName>{name}</SeriesName>
    <SeriesID>{seriesId}</SeriesID>
</Series>
""",
        encoding="utf-8",
    )


def testScanTvLibraryBuildsLiveRecordsWithoutSqlite(tmp_path: Path):
    tvRoot = tmp_path / "video1" / "TV"
    show = tvRoot / "Grimm"
    season = show / "Season 1"
    season.mkdir(parents=True)
    _seriesWrite(show, "Grimm", "248736")
    episode = season / "Grimm.S01E01.Pilot.mkv"
    episode.write_bytes(b"episode")

    snapshot = scanTvLibrary([tvRoot])

    series = snapshot.catalogueTvSeriesList()
    episodes = snapshot.catalogueTvEpisodesList()
    assert len(series) == 1
    assert series[0].showName == "Grimm"
    assert series[0].tvdbId == "248736"
    assert series[0].folderPath == str(show)
    assert len(episodes) == 1
    assert episodes[0].season == 1
    assert episodes[0].episode == 1


def testMergeUsesLiveStorageWhenPersistedCatalogueIsEmpty(tmp_path: Path):
    firstRoot = tmp_path / "video1" / "TV"
    secondRoot = tmp_path / "video2" / "TV"
    fuller = firstRoot / "Grimm"
    smaller = secondRoot / "Grimm (2011) -"
    fullerSeason = fuller / "Season 1"
    smallerSeason = smaller / "Season 1"
    fullerSeason.mkdir(parents=True)
    smallerSeason.mkdir(parents=True)
    _seriesWrite(fuller, "Grimm", "248736")
    _seriesWrite(smaller, "Grimm", "248736")
    (fullerSeason / "Grimm.S01E01.Pilot.mkv").write_bytes(b"one")
    (fullerSeason / "Grimm.S01E02.Bears.Will.Be.Bears.mkv").write_bytes(b"two")
    incoming = smallerSeason / "Grimm.S01E03.BeeWare.mkv"
    incoming.write_bytes(b"three")

    persisted = MediaCatalogue(tmp_path / "empty-catalogue.sqlite")
    with patch(
        "organiseMyVideo.tvLibraryScan.discoverTvStorageLocations",
        return_value=[firstRoot, secondRoot],
    ):
        stats = mergeDuplicateTvShows(catalogue=persisted, dryRun=True)

    assert stats.groupsFound == 1
    assert stats.groupsMerged == 1
    assert stats.filesMoved == 1
    assert incoming.exists()
    assert not (fullerSeason / incoming.name).exists()
    assert not persisted.databasePath.exists()


class _IdentityStub:
    """Minimal identity surface for missing-series resolution tests."""

    def __init__(self, results=None):
        self.results = list(results or [])
        self.requestCount = 0

    def _stripResetTvShowDuplicateSuffixes(self, value):
        import re

        return re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", value).strip()

    def _normaliseLookupText(self, value):
        if not value:
            return None
        return "".join(character.lower() for character in value if character.isalnum())

    def _tvdbSearchResultNames(self, result):
        return [result.get("name")] if result.get("name") else []

    def _requestJson(self, url, *, headers=None):
        del url, headers
        self.requestCount += 1
        return {"data": list(self.results)}

    def _getTvdbToken(self):
        return "token"


def testSeriesLookupNameRepairsYearAndTrailingSeparator():
    identity = _IdentityStub()

    assert _seriesLookupName("Grimm (2011) -", identity) == "Grimm"


def testTvdbExactSeriesIdRequiresOneExactNameMatch():
    identity = _IdentityStub(
        [
            {"name": "Grimm", "tvdb_id": "248736"},
            {"name": "Grimm Tales", "tvdb_id": "999999"},
        ]
    )

    assert _tvdbExactSeriesId(identity, "Grimm", "token") == "248736"


def testTvdbExactSeriesIdRejectsAmbiguousExactMatches():
    identity = _IdentityStub(
        [
            {"name": "Grimm", "tvdb_id": "248736"},
            {"name": "Grimm", "tvdb_id": "999999"},
        ]
    )

    assert _tvdbExactSeriesId(identity, "Grimm", "token") is None


def testMissingIdentityResolvedOnlyInsideDuplicateNameGroup(tmp_path: Path):
    known = TvSeriesCatalogueRecord(
        showName="Grimm",
        folderPath=str(tmp_path / "video1" / "TV" / "Grimm"),
        tvdbId="248736",
    )
    missing = TvSeriesCatalogueRecord(
        showName="Grimm (2011) -",
        folderPath=str(tmp_path / "video2" / "TV" / "Grimm (2011) -"),
    )
    unrelated = TvSeriesCatalogueRecord(
        showName="Unrelated Show",
        folderPath=str(tmp_path / "video3" / "TV" / "Unrelated Show"),
    )
    identity = _IdentityStub([{"name": "Grimm", "tvdb_id": "248736"}])

    resolved = _resolveMissingSeriesIdentities([known, missing, unrelated], identity)

    assert resolved[1].tvdbId == "248736"
    assert resolved[2].tvdbId is None
    assert identity.requestCount == 1
