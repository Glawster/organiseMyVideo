"""Tests for JPEG EXIF and shared video capture-time readers."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from cameraFixtures import cr3WithExif, cr3WithoutExif, jpegWithExif, jpegWithoutExif
from organiseMediaStudio.video.errors import VideoProcessingError
from organiseMyVideo.cameraMetadata import (
    metadataCaptureRead,
    metadataCr3CaptureRead,
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


def testMp4CreationTimeUsesSharedVideoProbe(tmp_path: Path, monkeypatch):
    path = tmp_path / "GH010111.MP4"
    capture = datetime(2024, 4, 18, 9, 0, 0, tzinfo=timezone.utc)
    path.write_bytes(b"video handled by shared probe")
    calls = []

    def probe(candidate):
        calls.append(candidate)
        return SimpleNamespace(creationAt=capture)

    monkeypatch.setattr("organiseMyVideo.cameraMetadata.videoProbe", probe)

    captured = metadataMp4CaptureRead(path)

    assert captured == capture
    assert calls == [path]


def testMp4ProbeFailureReturnsNone(tmp_path: Path, monkeypatch):
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"broken")

    def fail(candidate):
        raise VideoProcessingError(f"cannot probe {candidate}")

    monkeypatch.setattr("organiseMyVideo.cameraMetadata.videoProbe", fail)

    assert metadataMp4CaptureRead(path) is None


def testCr3ExifDateTimeOriginalIsRead(tmp_path: Path):
    path = tmp_path / "IMG_0154.CR3"
    path.write_bytes(cr3WithExif(datetime(2026, 9, 17, 10, 15, 0)))

    captured = metadataCr3CaptureRead(path)

    assert captured == datetime(2026, 9, 17, 10, 15, 0)


def testCr3WithoutExifReturnsNone(tmp_path: Path):
    path = tmp_path / "IMG_0154.CR3"
    path.write_bytes(cr3WithoutExif())

    assert metadataCr3CaptureRead(path) is None


def testCaptureReadDispatchesBySuffix(tmp_path: Path, monkeypatch):
    jpegPath = tmp_path / "still.jpg"
    mp4Path = tmp_path / "movie.mp4"
    cr3Path = tmp_path / "IMG_0154.CR3"
    otherPath = tmp_path / "notes.txt"
    capture = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    jpegPath.write_bytes(jpegWithExif(datetime(2024, 1, 2, 3, 4, 5)))
    mp4Path.write_bytes(b"video handled by shared probe")
    cr3Path.write_bytes(cr3WithExif(datetime(2026, 9, 17, 10, 15, 0)))
    otherPath.write_text("nope", encoding="utf-8")
    monkeypatch.setattr(
        "organiseMyVideo.cameraMetadata.videoProbe",
        lambda path: SimpleNamespace(creationAt=capture),
    )

    assert metadataCaptureRead(jpegPath) == datetime(2024, 1, 2, 3, 4, 5)
    assert metadataCaptureRead(mp4Path) == capture
    assert metadataCaptureRead(cr3Path) == datetime(2026, 9, 17, 10, 15, 0)
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


def testCaptureReadFallsBackToDashcamFilename(tmp_path: Path, monkeypatch):
    path = tmp_path / "20250722_110221_NF.mp4"
    path.write_bytes(b"not-an-mp4")

    def fail(candidate):
        raise VideoProcessingError(f"cannot probe {candidate}")

    monkeypatch.setattr("organiseMyVideo.cameraMetadata.videoProbe", fail)

    assert metadataCaptureRead(path) == datetime(2025, 7, 22, 11, 2, 21)
