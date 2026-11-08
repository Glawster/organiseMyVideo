"""REQ-035 regression tests for suspect MCM movie identity evidence."""

from pathlib import Path

import pytest

from organiseMyVideo.movieIdentity import (
    MovieIdentityDecision,
    movieIdentityMetadataSuspectReasons,
    movieIdentityReport,
)
from organiseMyVideo.movieIdentityReview import MovieIdentityReviewMixin


def testPathLikeMcmTitleIsSuspectIdentityEvidence():
    reasons = movieIdentityMetadataSuspectReasons(
        r"Q:\Movies\Entangled (2019)",
    )

    assert reasons == ("metadata title contains a filesystem path",)


def testMaterialRuntimeMismatchIsSuspectIdentityEvidence():
    reasons = movieIdentityMetadataSuspectReasons(
        "Entangled",
        metadataRuntime="3",
        mediaRuntime="91",
    )

    assert reasons == ("metadata runtime conflicts materially with media runtime",)


def testSmallRuntimeDifferenceIsNotEnoughToDistrustMetadata():
    assert not movieIdentityMetadataSuspectReasons(
        "Entangled",
        metadataRuntime="88",
        mediaRuntime="91",
    )


@pytest.mark.parametrize(
    ("metadataRuntime", "mediaRuntime"),
    [
        ("1h", "91"),
        ("1h", "118.2"),
        ("2h", "135.8"),
        ("3h", "167.7"),
        ("2h", "119.6"),
        ("1h", "121.4"),
        ("1h 31m", "91"),
        ("1h31", "95"),
        ("91 min", "91"),
        ("30min", "32"),
    ],
)
def testRuntimeFormatsThatAgreeWithMediaAreNotSuspect(metadataRuntime, mediaRuntime):
    assert not movieIdentityMetadataSuspectReasons(
        "Fist Fight",
        metadataRuntime=metadataRuntime,
        mediaRuntime=mediaRuntime,
    )


@pytest.mark.parametrize(
    ("metadataRuntime", "mediaRuntime"),
    [
        ("1h", "200"),
        ("3h", "95"),
        ("1h 31m", "150"),
        ("30min", "95"),
        ("6", "201.1"),
    ],
)
def testRuntimeFormatsThatContradictMediaAreSuspect(metadataRuntime, mediaRuntime):
    assert movieIdentityMetadataSuspectReasons(
        "Fist Fight",
        metadataRuntime=metadataRuntime,
        mediaRuntime=mediaRuntime,
    ) == ("metadata runtime conflicts materially with media runtime",)


def testUnrecognisedRuntimeFormatIsNotCompared():
    assert not movieIdentityMetadataSuspectReasons(
        "Fist Fight",
        metadataRuntime="1:31:00",
        mediaRuntime="91",
    )


def _writeVideo(path: Path, size: int) -> Path:
    """Create a video file of *size* bytes."""

    path.write_bytes(b"x" * size)
    return path


def testFeatureFileIsLargestSameNamedVideo(tmp_path: Path):
    trailer = _writeVideo(tmp_path / "Made in Dagenham (2010).mov", 10)
    feature = _writeVideo(tmp_path / "Made in Dagenham (2010).mkv", 100)

    assert MovieIdentityReviewMixin()._movieFeatureFile(tmp_path, trailer) == feature


def testFeatureFileIgnoresUnrelatedFilmsInStagingFolder(tmp_path: Path):
    wanted = _writeVideo(tmp_path / "Wanted (2010).mkv", 10)
    _writeVideo(tmp_path / "Other (2011).mkv", 100)

    assert MovieIdentityReviewMixin()._movieFeatureFile(tmp_path, wanted) == wanted


def testFeatureFileChoosesLargestOfSuppliedVideos(tmp_path: Path):
    first = _writeVideo(tmp_path / "Part (2010) cd1.mkv", 10)
    second = _writeVideo(tmp_path / "Part (2010) cd2.mkv", 100)

    assert (
        MovieIdentityReviewMixin()._movieFeatureFile(tmp_path, first, second) == second
    )


def testFeatureFileIsNoneWithoutVideo(tmp_path: Path):
    assert MovieIdentityReviewMixin()._movieFeatureFile(tmp_path) is None


def testEntangledConflictReportDoesNotDuplicateYearAndFlagsSuspectTitle():
    decision = MovieIdentityDecision(
        "conflict",
        currentTitle="Q - Movies - Entangled (2019)",
        currentYear="2019",
        proposedTitle=r"Q:\Movies\Entangled (2019)",
        proposedYear="2019",
    )

    report = movieIdentityReport(
        decision,
        evidence="movie.xml",
        tmdbId="641556",
        runtime="3",
        mediaRuntime="91",
    )

    assert report.startswith("movie metadata identity suspect\n")
    assert "current: Q - Movies - Entangled (2019)" in report
    assert r"proposed: Q:\Movies\Entangled (2019)" in report
    assert "(2019) (2019)" not in report
    assert "reason: metadata title contains a filesystem path" in report
    assert "reason: metadata runtime conflicts materially with media runtime" in report
    assert "tmdb: 641556" in report
    assert "metadata runtime: 3" in report
    assert "media runtime: 91" in report
