import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from organiseMyVideo import cameraImport as cameraImportModule
from organiseMyVideo.cameraImport import CameraImporter
from organiseMyVideo.cameraPlan import CameraImportPlanner


def fileMtimeSet(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def importerCreate(tmp_path: Path, *, dryRun: bool) -> CameraImporter:
    planner = CameraImportPlanner(
        goproDestination=tmp_path / "archive" / "GoPro",
        droneDestination=tmp_path / "archive" / "Drone",
        dashcamDestination=tmp_path / "archive" / "Dashcam",
    )
    return CameraImporter(
        planner=planner,
        manifestDirectory=tmp_path / "state" / "camera-imports",
        dryRun=dryRun,
    )


def cameraSourceCreate(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")
    fileMtimeSet(media, datetime(2024, 4, 20, 12, 0, 0))
    return source, media


def testCameraImportDryRunDoesNotWriteArchiveOrManifest(tmp_path: Path):
    source, media = cameraSourceCreate(tmp_path)
    before = media.read_bytes()

    result = importerCreate(tmp_path, dryRun=True).importMedia(source)

    assert result.confirmed is False
    assert result.manifestPath is None
    assert result.copied == 0
    assert media.read_bytes() == before
    assert not (tmp_path / "archive").exists()
    assert not (tmp_path / "state").exists()


def testConfirmedCameraImportCopiesVerifiesAndWritesManifest(tmp_path: Path):
    source, media = cameraSourceCreate(tmp_path)

    result = importerCreate(tmp_path, dryRun=False).importMedia(source)

    destination = (
        tmp_path
        / "archive"
        / "GoPro"
        / "2024"
        / "04"
        / "20"
        / "GH010111.MP4"
    )
    assert result.confirmed is True
    assert result.copied == 1
    assert result.failed == 0
    assert media.exists()
    assert destination.read_bytes() == media.read_bytes()
    assert result.manifestPath is not None
    assert result.manifestPath.is_file()

    manifest = json.loads(result.manifestPath.read_text(encoding="utf-8"))
    assert manifest["source"]["path"] == str(source)
    assert manifest["excludedPaths"] == []
    assert manifest["unknownPaths"] == []
    assert len(manifest["assets"]) == 1
    asset = manifest["assets"][0]
    assert asset["cameraKind"] == "gopro"
    assert asset["fileKind"] == "video"
    assert asset["sourcePath"] == str(media)
    assert asset["destinationPath"] == str(destination)
    assert asset["sizeBytes"] == len(b"camera-original")
    assert asset["sourceDigest"] == asset["destinationDigest"]
    assert asset["outcome"] == "copied"


def testConfirmedCameraImportFailureLeavesNoFinalOrTemporaryFile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source, media = cameraSourceCreate(tmp_path)

    def verificationFail(self, sourcePath, destinationPath):
        del self, sourcePath, destinationPath
        raise OSError("verification failed")

    monkeypatch.setattr(
        cameraImportModule.FilesystemOperations,
        "_verifyFiles",
        verificationFail,
    )

    result = importerCreate(tmp_path, dryRun=False).importMedia(source)

    destinationDirectory = tmp_path / "archive" / "GoPro" / "2024" / "04" / "20"
    destination = destinationDirectory / "GH010111.MP4"
    assert result.copied == 0
    assert result.failed == 1
    assert media.exists()
    assert not destination.exists()
    assert list(destinationDirectory.glob(".*.tmp")) == []
    manifest = json.loads(result.manifestPath.read_text(encoding="utf-8"))
    assert manifest["assets"][0]["outcome"] == "failed"
    assert "verification failed" in manifest["assets"][0]["error"]


def testConfirmedCameraImportRejectsPlanWithConflict(tmp_path: Path):
    source, media = cameraSourceCreate(tmp_path)
    destination = (
        tmp_path
        / "archive"
        / "GoPro"
        / "2024"
        / "04"
        / "20"
        / media.name
    )
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"different")

    with pytest.raises(RuntimeError, match="destination conflicts"):
        importerCreate(tmp_path, dryRun=False).importMedia(source)

    assert media.read_bytes() == b"camera-original"
    assert destination.read_bytes() == b"different"
    assert not (tmp_path / "state").exists()
