"""Integration checks for organiseMediaStudio REQ-002 adoption in organiseMyVideo."""

import hashlib
from datetime import datetime
from pathlib import Path

from organiseMyVideo.cameraMetadata import metadataFilenameCaptureRead
from organiseMyVideo.cameraPlan import _sha256


def testCameraPlanPreservesSha256Identity(tmp_path: Path):
    path = tmp_path / "clip.mp4"
    content = b"organiseMyVideo shared media identity"
    path.write_bytes(content)

    assert _sha256(path) == hashlib.sha256(content).hexdigest()


def testStandardPreciseFilenameDateUsesSharedBehaviour(tmp_path: Path):
    path = tmp_path / "20250722_110221_NF.mp4"
    path.write_bytes(b"media")

    assert metadataFilenameCaptureRead(path) == datetime(2025, 7, 22, 11, 2, 21)


def testDashcamSpecificFilenameBehaviourRemainsAvailable(tmp_path: Path):
    path = tmp_path / "2024_0418_090000_0001F.MP4"
    path.write_bytes(b"media")

    assert metadataFilenameCaptureRead(path) == datetime(2024, 4, 18, 9, 0, 0)
