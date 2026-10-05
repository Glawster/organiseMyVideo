"""REQ-035 regression tests for same-identity movie reconciliation evidence."""

from pathlib import Path

from organiseMyVideo.incomingNames import mediaNameIsDisposableJunk
from organiseMyVideo.showFolders import (
    movieFolderCollisionReport,
    movieFolderContentDescribe,
)


def testDownloadedFromTextFilesAreDisposableJunk():
    for name in (
        "Downloaded From glodls.to.txt",
        "Downloaded From The Pirate Bay.txt",
        "Downloaded From torrentgalaxy.to.txt",
        "downloaded from example.txt",
    ):
        assert mediaNameIsDisposableJunk(name)

    assert not mediaNameIsDisposableJunk("Downloaded From Notes.nfo")
    assert not mediaNameIsDisposableJunk("downloaded movie.txt")
    assert not mediaNameIsDisposableJunk("Inside Out 2 (2024).txt")


def testNestedFeatureFolderIsReportedAsComplementaryReconciliation(tmp_path: Path):
    canonical = tmp_path / "Inside Out 2 (2024)"
    canonical.mkdir()
    (canonical / "movie.xml").write_text("<Title />", encoding="utf-8")
    (canonical / "folder.jpg").write_bytes(b"artwork")

    duplicate = tmp_path / "Inside Out 2 (2024)_"
    nested = duplicate / "Inside Out 2 (2024)"
    nested.mkdir(parents=True)
    (duplicate / "movie.xml").write_text("<Title />", encoding="utf-8")
    (duplicate / "Downloaded From glodls.to.txt").write_text(
        "release marker", encoding="utf-8"
    )
    (duplicate / "Downloaded From The Pirate Bay.txt").write_text(
        "release marker", encoding="utf-8"
    )
    (nested / "Inside Out 2 (2024).mkv").write_bytes(b"feature")
    (nested / "movie.xml").write_text("<Title />", encoding="utf-8")

    relation, evidence = movieFolderContentDescribe(duplicate, canonical)

    assert relation == "complementary"
    assert "source contains: nested feature file, metadata, 2 disposable junk file(s)" in evidence
    assert "target contains: metadata, artwork" in evidence
    assert "source nested feature folder: Inside Out 2 (2024)" in evidence
    assert "Downloaded From glodls.to.txt" in evidence
    assert "Downloaded From The Pirate Bay.txt" in evidence

    report = movieFolderCollisionReport(duplicate, canonical, sameIdentity=True)
    assert "classification: same-identity merge candidate" in report
    assert "content: complementary" in report
    assert "action: reconcile complementary contents" in report


def testDisposableJunkDoesNotMakeSubstantiveContentsDistinct(tmp_path: Path):
    source = tmp_path / "Movie (2024)_"
    target = tmp_path / "Movie (2024)"
    source.mkdir()
    target.mkdir()
    for folder in (source, target):
        (folder / "Movie (2024).mkv").write_bytes(b"same feature")
        (folder / "movie.xml").write_text("<Title />", encoding="utf-8")
    (source / "Downloaded From torrentgalaxy.to.txt").write_text(
        "release marker", encoding="utf-8"
    )

    relation, evidence = movieFolderContentDescribe(source, target)

    assert relation == "identical"
    assert "source disposable junk: Downloaded From torrentgalaxy.to.txt" in evidence
