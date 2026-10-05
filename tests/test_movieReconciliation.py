"""REQ-035 regression tests for same-identity movie reconciliation evidence."""

import io
import os
from pathlib import Path
from unittest.mock import patch

from organiseMyVideo.incomingNames import mediaNameIsDisposableJunk
from organiseMyVideo.seasonFolders import _filesIdentical
from organiseMyVideo.showFolders import (
    _movieFilesIdentical,
    movieFolderCollisionReport,
    movieFolderContentDescribe,
)


class _TtyBuffer(io.StringIO):
    """String buffer that behaves like an interactive terminal."""

    def isatty(self) -> bool:
        return True


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
    assert (
        "source contains: nested feature file, metadata, 2 disposable junk file(s)"
        in evidence
    )
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


def testSameDeviceAndInodeBypassContentRead(tmp_path: Path):
    original = tmp_path / "Movie (2024).mkv"
    linked = tmp_path / "Movie (2024)-linked.mkv"
    original.write_bytes(b"feature content")
    os.link(original, linked)
    progress = []

    assert _filesIdentical(original, linked, progress=lambda done, total: progress.append((done, total)))
    assert progress == []


def testDifferentSizeBypassesContentRead(tmp_path: Path):
    left = tmp_path / "left.mkv"
    right = tmp_path / "right.mkv"
    left.write_bytes(b"short")
    right.write_bytes(b"a different length")
    progress = []

    assert not _filesIdentical(left, right, progress=lambda done, total: progress.append((done, total)))
    assert progress == []


def testLargeMovieComparisonDisplaysProgress(tmp_path: Path):
    left = tmp_path / "Sonic the Hedgehog 3 (2024).mkv"
    right = tmp_path / "Sonic the Hedgehog 3 (2024)-copy.mkv"
    payload = b"same feature content" * 1024
    left.write_bytes(payload)
    right.write_bytes(payload)
    stream = _TtyBuffer()

    with (
        patch("organiseMyVideo.showFolders.sys.stderr", stream),
        patch("organiseMyVideo.showFolders._LARGE_COMPARISON_BYTES", 1),
    ):
        assert _movieFilesIdentical(left, right)

    output = stream.getvalue()
    assert "Comparing duplicate content:" in output
    assert "Sonic the Hedgehog 3 (2024).mkv" in output
    assert "100%" in output
