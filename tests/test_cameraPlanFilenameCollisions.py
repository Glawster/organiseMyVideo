"""Regression tests for duplicate camera filenames in one import plan."""

from pathlib import Path

from organiseMyVideo.cameraPlan import CameraImportPlanner


def _planner(tmpPath: Path) -> CameraImportPlanner:
    return CameraImportPlanner(
        goproDestination=tmpPath / "archive" / "GoPro",
        droneDestination=tmpPath / "archive" / "Drone",
        dashcamDestination=tmpPath / "archive" / "Dashcam",
    )


def _dashcamPair(tmpPath: Path, first: bytes, second: bytes) -> Path:
    card = tmpPath / "card"
    front = card / "DP250" / "N_VIDEO"
    rear = card / "DP250" / "P_VIDEO"
    front.mkdir(parents=True)
    rear.mkdir(parents=True)
    filename = "2026_0909_113441_010.MOV"
    (front / filename).write_bytes(first)
    (rear / filename).write_bytes(second)
    return card


def testIdenticalSameNameInOnePlanIsAlreadyPresent(tmp_path: Path):
    plan = _planner(tmp_path).importPlan(
        _dashcamPair(tmp_path, b"same-camera-content", b"same-camera-content")
    )

    assert len(plan.operations) == 2
    assert [operation.outcome for operation in plan.operations] == [
        "copy",
        "alreadyPresent",
    ]
    assert plan.operations[0].asset.destinationPath == plan.operations[1].asset.destinationPath
    assert "identical content" in plan.operations[1].reason


def testDifferentSameNameInOnePlanGetsIncrementedFilename(tmp_path: Path):
    plan = _planner(tmp_path).importPlan(
        _dashcamPair(tmp_path, b"front-camera-content", b"rear-camera-content")
    )

    assert len(plan.operations) == 2
    assert [operation.outcome for operation in plan.operations] == ["copy", "copy"]
    destinations = [operation.asset.destinationPath.name for operation in plan.operations]
    assert destinations == [
        "2026_0909_113441_010.MOV",
        "2026_0909_113441_010 (2).MOV",
    ]
    assert "incremented filename" in plan.operations[1].reason


def testExistingDifferentNameThenExistingIdenticalIncrementIsReused(tmp_path: Path):
    card = _dashcamPair(tmp_path, b"new-content", b"other-new-content")
    archive = tmp_path / "archive" / "Dashcam" / "2026" / "09-Sep" / "09"
    archive.mkdir(parents=True)
    (archive / "2026_0909_113441_010.MOV").write_bytes(b"older-different-content")
    (archive / "2026_0909_113441_010 (2).MOV").write_bytes(b"new-content")

    plan = _planner(tmp_path).importPlan(card)

    first = plan.operations[0]
    second = plan.operations[1]
    assert first.outcome == "alreadyPresent"
    assert first.asset.destinationPath.name == "2026_0909_113441_010 (2).MOV"
    assert second.outcome == "copy"
    assert second.asset.destinationPath.name == "2026_0909_113441_010 (3).MOV"
