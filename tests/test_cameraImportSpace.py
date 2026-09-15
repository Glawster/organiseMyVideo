"""Preflight destination-space checks for confirmed camera imports."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from organiseMyVideo import cameraImport as cameraImportModule
from organiseMyVideo.cameraImport import CameraImporter
from organiseMyVideo.cameraPlan import CameraImportPlanner


def testConfirmedImportRefusesInsufficientDestinationSpace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")

    importer = CameraImporter(
        planner=CameraImportPlanner(
            goproDestination=tmp_path / "archive" / "GoPro",
            droneDestination=tmp_path / "archive" / "Drone",
            dashcamDestination=tmp_path / "archive" / "Dashcam",
        ),
        manifestDirectory=tmp_path / "state" / "camera-imports",
        dryRun=False,
    )
    monkeypatch.setattr(
        cameraImportModule.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=1),
    )

    with pytest.raises(RuntimeError, match="insufficient destination disk space"):
        importer.importMedia(source)

    assert not (tmp_path / "archive").exists()
    assert not (tmp_path / "state").exists()
