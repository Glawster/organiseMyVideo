"""Tests for JPEG EXIF and MP4 movie-header capture-time readers."""

from datetime import datetime, timezone
from pathlib import Path

from cameraFixtures import jpegWithExif, jpegWithoutExif, mp4WithCreation
from organiseMyVideo.cameraMetadata import (
    metadataCaptureRead,
    metadataFilenameCaptureRead,
    metadataJpegCaptureRead,
    metadataMp4CaptureRead,
)


def testJpegExifDateTimeOriginalIsPreferred(tmp_path: Path):
    path = tmp_path / "clip.THM"
    path.write_bytes(jpegWithExif(datetime(2024, 4, 20, 12, 0, 0)))

    captured = metadataJpegCaptureRead(path)

    assert captured == datetime(2024, 4, 20, 12, 0, 0)


def testJpegWithoutExifReturnsNone(tmp_path: Path):
    path = tmp_path / "empty.jpg"
    path.write_bytes(jpegWithoutExif())

    assert metadataJpegCaptureRead(path) is None


def testMp4MovieHeaderCreationTimeIsRead(tmp_path: Path):
    path = tmp_path / "GH010111.MP4"
    capture = datetime(2024, 4, 18, 9, 0, 0, tzinfo=timezone.utc)
    path.write_bytes(mp4WithCreation(capture))

    captured = metadataMp4CaptureRead(path)

    assert captured == capture


def testCaptureReadDispatchesBySuffix(tmp_path: Path):
    jpegPath = tmp_path / "still.jpg"
    mp4Path = tmp_path / "movie.mp4"
    otherPath = tmp_path / "notes.txt"
    jpegPath.write_bytes(jpegWithExif(datetime(2024, 1, 2, 3, 4, 5)))
    mp4Path.write_bytes(
        mp4WithCreation(datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
    )
    otherPath.write_text("nope", encoding="utf-8")

    assert metadataCaptureRead(jpegPath) == datetime(2024, 1, 2, 3, 4, 5)
    assert metadataCaptureRead(mp4Path) == datetime(
        2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    )
    assert metadataCaptureRead(otherPath) is None


def testFilenameCaptureReadsBlackvueAndViofoNames(tmp_path: Path):
    blackvue = tmp_path / "20250722_110221_NF.mp4"
    viofo = tmp_path / "2024_0418_090000_0001F.MP4"
    nextbase = tmp_path / "240915_143027_001_FH.MP4"
    blackvue.write_bytes(b"x")
    viofo.write_bytes(b"x")
    nextbase.write_bytes(b"x")

    assert metadataFilenameCaptureRead(blackvue) == datetime(2025, 7, 22, 11, 2, 21)
    assert metadataFilenameCaptureRead(viofo) == datetime(2024, 4, 18, 9, 0, 0)
    assert metadataFilenameCaptureRead(nextbase) == datetime(2024, 9, 15, 14, 30, 27)
    transcend = tmp_path / "2026_0513_120237_012.mp4"
    transcend.write_bytes(b"x")
    assert metadataFilenameCaptureRead(transcend) == datetime(2026, 5, 13, 12, 2, 37)
    compact = tmp_path / "20151110123000.MOV"
    prefixed = tmp_path / "TS20151110124500.MOV"
    compact.write_bytes(b"x")
    prefixed.write_bytes(b"x")
    assert metadataFilenameCaptureRead(compact) == datetime(2015, 11, 10, 12, 30, 0)
    assert metadataFilenameCaptureRead(prefixed) == datetime(2015, 11, 10, 12, 45, 0)


def testCaptureReadFallsBackToDashcamFilename(tmp_path: Path):
    path = tmp_path / "20250722_110221_NF.mp4"
    path.write_bytes(b"not-an-mp4")

    assert metadataCaptureRead(path) == datetime(2025, 7, 22, 11, 2, 21)
