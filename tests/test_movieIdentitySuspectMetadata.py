"""REQ-035 regression tests for suspect MCM movie identity evidence."""

from organiseMyVideo.movieIdentity import (
    MovieIdentityDecision,
    movieIdentityMetadataSuspectReasons,
    movieIdentityReport,
)


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

    assert reasons == (
        "metadata runtime conflicts materially with media runtime",
    )


def testSmallRuntimeDifferenceIsNotEnoughToDistrustMetadata():
    assert not movieIdentityMetadataSuspectReasons(
        "Entangled",
        metadataRuntime="88",
        mediaRuntime="91",
    )


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
