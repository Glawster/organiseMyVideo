"""Regression tests for Transcend DrivePro TEMP/E_TEMP proxy exclusions."""

from pathlib import Path

from organiseMyVideo.cameraPlan import CameraImportPlanner


def _planner(tmpPath: Path) -> CameraImportPlanner:
    return CameraImportPlanner(
        goproDestination=tmpPath / "archive" / "GoPro",
        droneDestination=tmpPath / "archive" / "Drone",
        dashcamDestination=tmpPath / "archive" / "Dashcam",
    )


def testTranscendTempAndEventTempAreExcluded(tmp_path: Path):
    card = tmp_path / "card"
    normal = card / "DP10" / "N_VIDEO"
    temp = card / "DP10" / "TEMP"
    event = card / "DP10" / "E_VIDEO"
    eventTemp = card / "DP10" / "E_TEMP"
    for directory in (normal, temp, event, eventTemp):
        directory.mkdir(parents=True)

    normalName = "2023_0824_140949_001.MP4"
    eventName = "2023_0828_102734_001.MP4"
    (normal / normalName).write_bytes(b"full-normal")
    (temp / normalName).write_bytes(b"proxy-normal")
    (event / eventName).write_bytes(b"full-event")
    (eventTemp / eventName).write_bytes(b"proxy-event")

    plan = _planner(tmp_path).importPlan(card)

    assert {operation.asset.relativePath for operation in plan.operations} == {
        f"DP10/N_VIDEO/{normalName}",
        f"DP10/E_VIDEO/{eventName}",
    }
    assert set(plan.excludedPaths) == {
        f"DP10/TEMP/{normalName}",
        f"DP10/E_TEMP/{eventName}",
    }


def testDistinctTranscendModelRootsRemainEligible(tmp_path: Path):
    card = tmp_path / "card"
    dp10 = card / "DP10" / "N_VIDEO"
    dp250 = card / "DP250" / "N_VIDEO"
    dp10.mkdir(parents=True)
    dp250.mkdir(parents=True)

    firstName = "2023_0824_140949_001.MP4"
    secondName = "2026_0915_111141_005.MP4"
    (dp10 / firstName).write_bytes(b"dp10")
    (dp250 / secondName).write_bytes(b"dp250")

    plan = _planner(tmp_path).importPlan(card)

    assert {operation.asset.relativePath for operation in plan.operations} == {
        f"DP10/N_VIDEO/{firstName}",
        f"DP250/N_VIDEO/{secondName}",
    }
    assert plan.excludedPaths == ()


def testGenericDashcamTempDirectoryIsNotExcludedWithoutTranscendModelRoot(tmp_path: Path):
    card = tmp_path / "card"
    temp = card / "TEMP"
    temp.mkdir(parents=True)
    filename = "2026_0915_111141_005.MP4"
    (temp / filename).write_bytes(b"generic-dashcam")

    plan = _planner(tmp_path).importPlan(card)

    assert [operation.asset.relativePath for operation in plan.operations] == [filename]
    assert plan.excludedPaths == ()
