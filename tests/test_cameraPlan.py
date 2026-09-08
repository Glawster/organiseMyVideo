import os
from datetime import datetime
from pathlib import Path

from organiseMyVideo.cameraDetect import cameraDetect
from organiseMyVideo.cameraPlan import CameraImportPlanner


def fileMtimeSet(path: Path, value: datetime) -> None:
    timestamp = value.timestamp()
    os.utime(path, (timestamp, timestamp))


def cameraPlannerCreate(tmp_path: Path, *, includeGoproCompanions: bool = False):
    return CameraImportPlanner(
        goproDestination=tmp_path / "archive" / "GoPro",
        droneDestination=tmp_path / "archive" / "Drone",
        dashcamDestination=tmp_path / "archive" / "Dashcam",
        includeGoproCompanions=includeGoproCompanions,
    )


def testCameraDetectMixedSourceAndUnknownContent(tmp_path: Path):
    source = tmp_path / "card"
    gopro = source / "DCIM" / "100GOPRO"
    dji = source / "DCIM" / "101MEDIA"
    dashcam = source / "Movie"
    ignored = source / "MISC"
    for directory in (gopro, dji, dashcam, ignored):
        directory.mkdir(parents=True, exist_ok=True)
    (gopro / "GH010111.MP4").write_bytes(b"gopro")
    (dji / "DJI_0021.MP4").write_bytes(b"dji")
    (dashcam / "2024_0418_090000_0001F.MP4").write_bytes(b"dashcam")
    (source / "notes.txt").write_text("unknown")
    (ignored / "settings.db").write_text("ignored")

    detection = cameraDetect(source)

    assert {item.cameraKind for item in detection.files} == {"gopro", "dji", "dashcam"}
    assert detection.unknownPaths == ("notes.txt",)


def testImportPlanRoutesCameraFamiliesAndReportsFallback(tmp_path: Path):
    source = tmp_path / "card"
    gopro = source / "DCIM" / "100GOPRO"
    dji = source / "DCIM" / "101MEDIA"
    dashcam = source / "Movie"
    for directory in (gopro, dji, dashcam):
        directory.mkdir(parents=True, exist_ok=True)
    goproFile = gopro / "GH010111.MP4"
    djiFile = dji / "DJI_0021.MP4"
    djiSrt = dji / "DJI_0021.SRT"
    dashcamFile = dashcam / "2024_0418_090000_0001F.MP4"
    for path in (goproFile, djiFile, djiSrt, dashcamFile):
        path.write_bytes(path.name.encode())
    fallback = datetime(2025, 5, 6, 7, 8, 9)
    fileMtimeSet(goproFile, fallback)
    fileMtimeSet(djiFile, fallback)
    fileMtimeSet(djiSrt, datetime(2020, 1, 1, 0, 0, 0))

    plan = cameraPlannerCreate(tmp_path).importPlan(source)
    byName = {operation.asset.sourcePath.name: operation for operation in plan.operations}

    assert byName["GH010111.MP4"].asset.destinationPath == (
        tmp_path / "archive" / "GoPro" / "2025" / "05" / "06" / "GH010111.MP4"
    )
    assert byName["GH010111.MP4"].asset.dateSource == "filesystem"
    assert byName["DJI_0021.MP4"].asset.destinationPath.parent == (
        tmp_path / "archive" / "Drone" / "2025" / "05" / "06"
    )
    assert byName["DJI_0021.SRT"].asset.destinationPath.parent == (
        tmp_path / "archive" / "Drone" / "2025" / "05" / "06"
    )
    assert byName["2024_0418_090000_0001F.MP4"].asset.destinationPath.parent == (
        tmp_path / "archive" / "Dashcam" / "2024" / "04" / "18"
    )
    assert byName["2024_0418_090000_0001F.MP4"].asset.dateSource == "filename"


def testGoproHelpersExcludedByDefaultAndOptional(tmp_path: Path):
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    video = source / "GH010111.MP4"
    preview = source / "GL010111.LRV"
    thumbnail = source / "GH010111.THM"
    for path in (video, preview, thumbnail):
        path.write_bytes(b"content")
        fileMtimeSet(path, datetime(2024, 4, 20, 12, 0, 0))

    defaultPlan = cameraPlannerCreate(tmp_path).importPlan(source)
    includedPlan = cameraPlannerCreate(
        tmp_path, includeGoproCompanions=True
    ).importPlan(source)

    assert set(defaultPlan.excludedPaths) == {"GH010111.THM", "GL010111.LRV"}
    assert {item.asset.sourcePath.name for item in includedPlan.operations} == {
        "GH010111.MP4",
        "GH010111.THM",
        "GL010111.LRV",
    }


def testPlannerClassifiesIdenticalAndConflictingDestinations(tmp_path: Path):
    source = tmp_path / "card" / "DCIM" / "101MEDIA"
    source.mkdir(parents=True)
    identical = source / "DJI_0001.MP4"
    conflict = source / "DJI_0002.MP4"
    identical.write_bytes(b"same")
    conflict.write_bytes(b"source")
    captured = datetime(2024, 4, 20, 12, 0, 0)
    fileMtimeSet(identical, captured)
    fileMtimeSet(conflict, captured)

    destination = tmp_path / "archive" / "Drone" / "2024" / "04" / "20"
    destination.mkdir(parents=True)
    (destination / identical.name).write_bytes(b"same")
    (destination / conflict.name).write_bytes(b"different")

    plan = cameraPlannerCreate(tmp_path).importPlan(source)
    outcomes = {operation.asset.sourcePath.name: operation.outcome for operation in plan.operations}

    assert outcomes == {
        "DJI_0001.MP4": "alreadyPresent",
        "DJI_0002.MP4": "conflict",
    }


def testPlanningDoesNotMutateSourceOrCreateDestinations(tmp_path: Path):
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    media = source / "GH010111.MP4"
    media.write_bytes(b"original")
    fileMtimeSet(media, datetime(2024, 4, 20, 12, 0, 0))
    before = media.read_bytes()

    plan = cameraPlannerCreate(tmp_path).importPlan(source)

    assert plan.operations[0].outcome == "copy"
    assert media.read_bytes() == before
    assert not (tmp_path / "archive").exists()
