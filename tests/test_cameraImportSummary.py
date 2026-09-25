"""Focused terminal-summary tests for camera import outcomes."""

from datetime import datetime
from pathlib import Path

import pytest

from organiseMyVideo import cameraImport as cameraImportModule
from organiseMyVideo.cameraImport import CameraImporter, cameraImportSummary
from organiseMyVideo.cameraPlan import CameraImportPlanner


def _sourceCreate(tmp_path: Path) -> Path:
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")
    timestamp = datetime(2024, 4, 20, 12, 0, 0).timestamp()
    media.touch()
    media.chmod(0o644)
    import os

    os.utime(media, (timestamp, timestamp))
    return source


def _importerCreate(tmp_path: Path) -> CameraImporter:
    return CameraImporter(
        planner=CameraImportPlanner(
            goproDestination=tmp_path / "archive" / "GoPro",
            droneDestination=tmp_path / "archive" / "Drone",
            dashcamDestination=tmp_path / "archive" / "Dashcam",
        ),
        manifestDirectory=tmp_path / "state" / "camera-imports",
        dryRun=False,
    )


def testCameraImportSummaryHighlightsSuccess(tmp_path: Path):
    result = _importerCreate(tmp_path).importMedia(_sourceCreate(tmp_path))

    summary = cameraImportSummary(result)

    assert "CAMERA IMPORT COMPLETE" in summary
    assert "OK: import complete" in summary
    assert "Copied              1" in summary
    assert "Failed" not in summary
    assert "Manifest" in summary


def testCameraImportSummaryGroupsFailureReasons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = _sourceCreate(tmp_path)

    def verificationFail(self, sourcePath, destinationPath):
        del self, sourcePath, destinationPath
        raise OSError("verification failed")

    monkeypatch.setattr(
        cameraImportModule.FilesystemOperations,
        "_verifyFiles",
        verificationFail,
    )

    result = _importerCreate(tmp_path).importMedia(source)
    summary = cameraImportSummary(result)

    assert result.failed == 1
    assert "WARNING: import incomplete" in summary
    assert "Failure reasons" in summary
    assert "1 × OSError: verification failed" in summary
    assert "GH010111.MP4" in summary
    assert "See the manifest for the complete failed-file list." in summary
