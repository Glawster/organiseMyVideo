"""REQ-026 mixed Canon SLR card detection, planning, import, and inventory."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

import organiseMyVideo.__main__ as applicationMain
from cameraFixtures import (
    cr3WithExif,
    jpegWithExif,
    jpegWithoutExif,
    slrTreeBuild,
)
from organiseMyVideo import constants
from organiseMyVideo.cameraDetect import cameraDetect
from organiseMyVideo.cameraImport import (
    CameraImporter,
    cameraImportRun,
    cameraImportSummary,
)
from organiseMyVideo.cameraInventory import CameraInventory, cameraInventorySummary
from organiseMyVideo.cameraPlan import CameraImportPlanner
from organiseMyVideo.constants import cameraCardLabelFilename


def fileMtimeSet(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def slrPlanner(tmpPath: Path) -> CameraImportPlanner:
    return CameraImportPlanner(
        goproDestination=tmpPath / "archive" / "GoPro",
        droneDestination=tmpPath / "archive" / "Drone",
        dashcamDestination=tmpPath / "archive" / "Dashcam",
        photoDestination=tmpPath / "pictures",
        videoDestination=tmpPath / "video",
    )


def slrImporter(tmpPath: Path, *, dryRun: bool, progress=None) -> CameraImporter:
    return CameraImporter(
        planner=slrPlanner(tmpPath),
        manifestDirectory=tmpPath / "state" / "camera-imports",
        dryRun=dryRun,
        progressCallback=progress,
    )


def slrDestinations(tmpPath: Path) -> dict:
    return {
        "goproDestination": tmpPath / "archive" / "GoPro",
        "droneDestination": tmpPath / "archive" / "Drone",
        "dashcamDestination": tmpPath / "archive" / "Dashcam",
        "photoDestination": tmpPath / "pictures",
        "videoDestination": tmpPath / "video",
        "manifestDirectory": tmpPath / "state" / "camera-imports",
    }


def photoDateDir(tmpPath: Path, year: int, month: int, day: int) -> Path:
    return (
        tmpPath / "pictures" / "By Date" / f"{year:04d}" / f"{month:02d}" / f"{day:02d}"
    )


def videoDateDir(tmpPath: Path, year: int, month: int, day: int) -> Path:
    return tmpPath / "video" / "By Date" / f"{year:04d}" / f"{month:02d}" / f"{day:02d}"


def testSlrDetectionClassifiesAssetsWithoutCardLevelType(tmp_path: Path):
    card = slrTreeBuild(tmp_path / "card")

    detection = cameraDetect(card)

    kinds = {
        (item.path.name, item.cameraKind, item.fileKind) for item in detection.files
    }
    assert kinds == {
        ("IMG_0154.CR3", "slr", "photo"),
        ("IMG_0154.JPG", "slr", "photo"),
        ("MVI_0204.MP4", "slr", "video"),
    }
    assert {item.cameraKind for item in detection.files} == {"slr"}
    relative = {item.relativePath for item in detection.files}
    unknown = set(detection.unknownPaths)
    assert "CANONMSC/DCIM.CTG" not in relative
    assert "comstate.to3" not in relative
    assert "CANONMSC/DCIM.CTG" not in unknown
    assert "comstate.to3" not in unknown


def testSlrPlanRoutesPairsAndVideoToNumericByDate(tmp_path: Path):
    card = slrTreeBuild(tmp_path / "card")

    plan = slrPlanner(tmp_path).importPlan(card)
    byName = {
        operation.asset.sourcePath.name: operation for operation in plan.operations
    }

    photoDir = photoDateDir(tmp_path, 2026, 9, 17)
    videoDir = videoDateDir(tmp_path, 2026, 9, 17)
    assert byName["IMG_0154.CR3"].asset.destinationPath == photoDir / "IMG_0154.CR3"
    assert byName["IMG_0154.JPG"].asset.destinationPath == photoDir / "IMG_0154.JPG"
    assert byName["MVI_0204.MP4"].asset.destinationPath == videoDir / "MVI_0204.MP4"
    assert byName["IMG_0154.CR3"].asset.dateSource == "metadata"
    assert byName["IMG_0154.JPG"].asset.dateSource == "metadata"
    assert byName["MVI_0204.MP4"].asset.dateSource == "metadata"
    assert "09-Sep" not in str(byName["IMG_0154.CR3"].asset.destinationPath)


def testSlrSameStemPairStaysTogetherWhenJpegLacksMetadata(tmp_path: Path):
    card = tmp_path / "card"
    canon = card / "DCIM" / "100CANON"
    canon.mkdir(parents=True)
    raw = canon / "IMG_0154.CR3"
    jpeg = canon / "IMG_0154.JPG"
    raw.write_bytes(cr3WithExif(datetime(2026, 9, 17, 10, 15, 0)))
    jpeg.write_bytes(jpegWithoutExif())
    fileMtimeSet(jpeg, datetime(2020, 1, 1, 0, 0, 0))

    plan = slrPlanner(tmp_path).importPlan(card)
    byName = {
        operation.asset.sourcePath.name: operation for operation in plan.operations
    }

    photoDir = photoDateDir(tmp_path, 2026, 9, 17)
    assert byName["IMG_0154.CR3"].asset.destinationPath.parent == photoDir
    assert byName["IMG_0154.JPG"].asset.destinationPath.parent == photoDir
    assert byName["IMG_0154.JPG"].asset.dateSource == "metadata"


def testSlrFallbackDateProvenanceIsReported(tmp_path: Path):
    card = tmp_path / "card"
    canon = card / "DCIM" / "100CANON"
    canon.mkdir(parents=True)
    jpeg = canon / "IMG_0999.JPG"
    jpeg.write_bytes(jpegWithoutExif())
    fileMtimeSet(jpeg, datetime(2026, 8, 2, 9, 0, 0))

    plan = slrPlanner(tmp_path).importPlan(card)

    assert len(plan.operations) == 1
    operation = plan.operations[0]
    assert operation.asset.dateSource == "filesystem"
    assert (
        operation.asset.destinationPath
        == photoDateDir(tmp_path, 2026, 8, 2) / "IMG_0999.JPG"
    )
    summary = cameraImportSummary(slrImporter(tmp_path, dryRun=True).importMedia(card))
    assert "Fallback dates" in summary
    assert "filesystem" in summary


def testSlrIgnoresCanonControlFiles(tmp_path: Path):
    card = slrTreeBuild(tmp_path / "card")

    plan = slrPlanner(tmp_path).importPlan(card)
    names = {operation.asset.sourcePath.name for operation in plan.operations}

    assert "DCIM.CTG" not in names
    assert "comstate.to3" not in names
    assert (card / "CANONMSC" / "DCIM.CTG").is_file()
    assert (card / "comstate.to3").is_file()


def testSlrIdenticalDestinationIsAlreadyPresent(tmp_path: Path):
    card = tmp_path / "card"
    canon = card / "DCIM" / "100CANON"
    canon.mkdir(parents=True)
    jpeg = canon / "IMG_0154.JPG"
    jpeg.write_bytes(jpegWithExif(datetime(2026, 9, 17, 10, 15, 0)))
    destination = photoDateDir(tmp_path, 2026, 9, 17)
    destination.mkdir(parents=True)
    (destination / "IMG_0154.JPG").write_bytes(jpeg.read_bytes())

    plan = slrPlanner(tmp_path).importPlan(card)

    assert plan.operations[0].outcome == "alreadyPresent"
    assert plan.operations[0].asset.destinationPath.name == "IMG_0154.JPG"


def testSlrSameNameDifferentContentIsConflictWithoutRenaming(tmp_path: Path):
    card = tmp_path / "card"
    canon = card / "DCIM" / "100CANON"
    canon.mkdir(parents=True)
    jpeg = canon / "IMG_0154.JPG"
    jpeg.write_bytes(jpegWithExif(datetime(2026, 9, 17, 10, 15, 0)))
    destination = photoDateDir(tmp_path, 2026, 9, 17)
    destination.mkdir(parents=True)
    (destination / "IMG_0154.JPG").write_bytes(b"different-archive-bytes")

    plan = slrPlanner(tmp_path).importPlan(card)
    operation = plan.operations[0]

    assert operation.outcome == "conflict"
    assert operation.asset.destinationPath.name == "IMG_0154.JPG"
    assert " (2)" not in operation.asset.destinationPath.name
    result = slrImporter(tmp_path, dryRun=True).importMedia(card)
    assert "Conflicts" in cameraImportSummary(result)
    with pytest.raises(RuntimeError, match="destination conflicts"):
        slrImporter(tmp_path, dryRun=False).importMedia(card)
    assert jpeg.read_bytes() == jpegWithExif(datetime(2026, 9, 17, 10, 15, 0))
    assert (destination / "IMG_0154.JPG").read_bytes() == b"different-archive-bytes"
    assert not (destination / "IMG_0154 (2).JPG").exists()


def testSlrDryRunDoesNotMutateSourceOrDestinations(tmp_path: Path):
    card = slrTreeBuild(tmp_path / "card")
    before = {
        path.relative_to(card).as_posix(): path.read_bytes()
        for path in card.rglob("*")
        if path.is_file()
    }

    result = slrImporter(tmp_path, dryRun=True).importMedia(card)

    assert result.confirmed is False
    assert result.copied == 0
    assert result.manifestPath is None
    assert not (tmp_path / "pictures").exists()
    assert not (tmp_path / "video").exists()
    after = {
        path.relative_to(card).as_posix(): path.read_bytes()
        for path in card.rglob("*")
        if path.is_file()
    }
    assert after == before


def testSlrConfirmedImportCopiesToPhotoAndVideoRoots(tmp_path: Path):
    card = slrTreeBuild(tmp_path / "card")
    label = card / cameraCardLabelFilename(26)
    label.write_text(json.dumps({"cardId": 26}), encoding="utf-8")
    sourceBytes = {
        path.name: path.read_bytes()
        for path in (card / "DCIM" / "100CANON").iterdir()
        if path.is_file()
    }

    result = cameraImportRun(source=card, dryRun=False, **slrDestinations(tmp_path))

    photoDir = photoDateDir(tmp_path, 2026, 9, 17)
    videoDir = videoDateDir(tmp_path, 2026, 9, 17)
    assert result.confirmed is True
    assert result.copied == 3
    assert result.failed == 0
    assert result.cardId == 26
    assert result.importId
    assert (photoDir / "IMG_0154.CR3").read_bytes() == sourceBytes["IMG_0154.CR3"]
    assert (photoDir / "IMG_0154.JPG").read_bytes() == sourceBytes["IMG_0154.JPG"]
    assert (videoDir / "MVI_0204.MP4").read_bytes() == sourceBytes["MVI_0204.MP4"]
    assert (card / "DCIM" / "100CANON" / "IMG_0154.CR3").read_bytes() == sourceBytes[
        "IMG_0154.CR3"
    ]
    assert (card / "comstate.to3").is_file()
    assert not (photoDir / "DCIM.CTG").exists()
    manifest = json.loads(result.manifestPath.read_text(encoding="utf-8"))
    assert manifest["source"]["cardId"] == 26
    assert manifest["importId"] == result.importId
    summary = cameraImportSummary(result)
    assert "  CR3                 1" in summary
    assert "  JPEG                1" in summary
    assert "  MP4                 1" in summary
    assert "Date range          2026-09-17" in summary
    assert "09-Sep" not in summary


def testSlrMultipleCaptureDatesRouteSeparately(tmp_path: Path):
    card = slrTreeBuild(
        tmp_path / "card",
        extraPair=True,
        extraPairCapture=datetime(2026, 9, 16, 8, 0, 0),
    )

    plan = slrPlanner(tmp_path).importPlan(card)
    byName = {
        operation.asset.sourcePath.name: operation for operation in plan.operations
    }

    assert byName["IMG_0154.CR3"].asset.destinationPath.parent == photoDateDir(
        tmp_path, 2026, 9, 17
    )
    assert byName["IMG_0155.CR3"].asset.destinationPath.parent == photoDateDir(
        tmp_path, 2026, 9, 16
    )
    assert byName["IMG_0155.JPG"].asset.destinationPath.parent == photoDateDir(
        tmp_path, 2026, 9, 16
    )


def testSlrConfirmedImportReportsByteProgress(tmp_path: Path):
    card = tmp_path / "card"
    canon = card / "DCIM" / "100CANON"
    canon.mkdir(parents=True)
    files = []
    for index in range(8):
        jpeg = canon / f"IMG_{index:04d}.JPG"
        jpeg.write_bytes(jpegWithExif(datetime(2026, 9, 17, 10, index, 0)))
        files.append(jpeg)
    progress = []
    importer = slrImporter(
        tmp_path,
        dryRun=False,
        progress=lambda copied, total, name: progress.append((copied, total, name)),
    )

    result = importer.importMedia(card)

    totalBytes = sum(path.stat().st_size for path in files)
    assert result.copied == 8
    assert progress[0] == (0, totalBytes, "")
    assert progress[-1][0] == totalBytes
    assert progress[-1][1] == totalBytes
    assert any(name.endswith(".JPG") for _, _, name in progress)


def testSlrInventoryCountsAndDateRangeIgnoreControlFiles(tmp_path: Path):
    databasePath = tmp_path / "state" / "cameraInventory.sqlite"
    card = slrTreeBuild(tmp_path / "card", extraPair=True)
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    record = service.inventoryScan(card, 26)
    summary = cameraInventorySummary(record, persisted=False, databasePath=databasePath)

    assert record.cameraKinds == ("slr",)
    assert record.manufacturer == "Canon"
    assert record.fileCounts["photo"] == 4
    assert record.fileCounts["video"] == 1
    assert record.dateSource == "capture-metadata"
    assert record.dateStart.startswith("2026-09-16")
    assert record.dateEnd.startswith("2026-09-17")
    relativePaths = {item.relativePath for item in record.files}
    assert "CANONMSC/DCIM.CTG" in relativePaths
    assert "comstate.to3" in relativePaths
    mediaKinds = {
        item.kind
        for item in record.files
        if item.relativePath in {"CANONMSC/DCIM.CTG", "comstate.to3"}
    }
    assert mediaKinds == {"other"}
    assert "CR3:              2" in summary
    assert "JPEG:             2" in summary
    assert "MP4:              1" in summary
    assert "2026-09-16" in summary
    assert not databasePath.exists()


def testSlrVisionSamplesJpegNotCr3(tmp_path: Path):
    databasePath = tmp_path / "state" / "cameraInventory.sqlite"
    card = slrTreeBuild(tmp_path / "card")
    sampled = []
    service = CameraInventory(
        dryRun=False,
        databasePath=databasePath,
        visionDescribe=lambda paths: sampled.extend(paths) or "still photographs",
    )

    record = service.inventoryScan(card, 26)

    assert sampled
    assert all(path.suffix.lower() == ".jpg" for path in sampled)
    assert record.visionStatus == "described"


def testCameraImportProgressClearsPreviousTtyLine(
    capsys, monkeypatch: pytest.MonkeyPatch
):
    import sys

    renderer = applicationMain._cameraImportProgressRenderer()
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)
    monkeypatch.setattr(
        applicationMain.shutil,
        "get_terminal_size",
        lambda fallback: os.terminal_size((120, 24)),
    )

    renderer(40, 100, "IMG_0154.CR3.JPG")
    renderer(50, 100, "IMG_0154.CR3")

    err = capsys.readouterr().err
    assert "\r\x1b[2KImporting [" in err
    assert err.count("\x1b[2K") == 2


def testCameraImportProgressIsVisibleWhenNotATty(
    capsys, monkeypatch: pytest.MonkeyPatch
):
    import sys

    renderer = applicationMain._cameraImportProgressRenderer()
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)

    renderer(0, 100, "")
    renderer(40, 100, "IMG_0154.CR3")
    renderer(100, 100, "IMG_0154.JPG")

    err = capsys.readouterr().err
    assert "Importing camera media" in err
    assert "IMG_0154.CR3" in err
    assert "complete" in err


def testCameraScanAndArchiveCliForSlrCard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    databasePath = tmp_path / "state" / "mediaCatalogue.sqlite"
    configPath = tmp_path / "config.json"
    configPath.write_text(
        json.dumps(
            {
                "storage_locations": {
                    "gopro": str(tmp_path / "archive" / "GoPro"),
                    "drone": str(tmp_path / "archive" / "Drone"),
                    "dashcam": str(tmp_path / "archive" / "Dashcam"),
                    "photos": str(tmp_path / "pictures"),
                    "homeVideo": str(tmp_path / "video"),
                }
            }
        ),
        encoding="utf-8",
    )
    card = slrTreeBuild(tmp_path / "card")
    monkeypatch.setattr(
        CameraInventory,
        "_contentDescribeLive",
        lambda self, paths: "still photographs",
    )
    monkeypatch.setattr(constants, "CAMERA_INVENTORY_DATABASE", databasePath)
    monkeypatch.setattr(
        constants, "applicationStateDirectory", lambda: tmp_path / "state"
    )
    monkeypatch.setattr(applicationMain, "APP_CONFIG_FILE", configPath)
    monkeypatch.setattr("organiseMyVideo.mainLegacy.APP_CONFIG_FILE", configPath)

    scanStatus = applicationMain.main(
        ["camera", "scan", "-s", str(card), "--card", "26"]
    )
    scanOutput = capsys.readouterr().out

    assert scanStatus == 0
    assert "CR3:" in scanOutput
    assert "JPEG:" in scanOutput
    assert "MP4:" in scanOutput
    assert "Canon" in scanOutput
    assert not databasePath.exists()

    persistStatus = applicationMain.main(
        ["camera", "scan", "-s", str(card), "--card", "26", "--confirm"]
    )
    capsys.readouterr()
    assert persistStatus == 0
    assert databasePath.is_file()

    dryStatus = applicationMain.main(
        ["camera", "archive", "-s", str(card), "--card", "26"]
    )
    dryOutput = capsys.readouterr().out
    assert dryStatus == 0
    assert "CAMERA IMPORT PLAN" in dryOutput
    assert "Planned" in dryOutput
    assert "  CR3                 1" in dryOutput
    assert not (tmp_path / "pictures").exists()
    assert not (tmp_path / "video").exists()

    confirmStatus = applicationMain.main(
        ["camera", "archive", "-s", str(card), "--card", "26", "--confirm"]
    )
    confirmErr = capsys.readouterr().err
    assert confirmStatus == 0
    assert (photoDateDir(tmp_path, 2026, 9, 17) / "IMG_0154.CR3").is_file()
    assert (photoDateDir(tmp_path, 2026, 9, 17) / "IMG_0154.JPG").is_file()
    assert (videoDateDir(tmp_path, 2026, 9, 17) / "MVI_0204.MP4").is_file()
    assert (card / "DCIM" / "100CANON" / "IMG_0154.CR3").is_file()
    assert "Importing" in confirmErr
