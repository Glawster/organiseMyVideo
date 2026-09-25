import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from organiseMyVideo.cameraFormat import (
    cameraFormatPlan,
    cameraFormatRun,
    cameraFormatSummary,
    cameraFormatTargetId,
)
from organiseMyVideo.cameraInventory import CameraInventory
from organiseMyVideo.cameraInventoryList import cameraInventoryList, cameraInventoryListSummary


def _inventoryCreate(
    tmpPath: Path,
    cardId: int,
    *,
    empty: bool = False,
    review: bool = False,
) -> Path:
    databasePath = tmpPath / "state" / "mediaCatalogue.sqlite"
    card = tmpPath / f"source-{cardId}"
    (card / "DCIM").mkdir(parents=True)
    if review:
        (card / "important.csv").write_text("keep,this,data", encoding="utf-8")
    elif not empty:
        (card / "DCIM" / "clip.mp4").write_bytes(b"content")
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    service.inventoryPersist(service.inventoryScan(card, cardId))
    return databasePath


def _archiveLatest(databasePath: Path, manifestDirectory: Path, cardId: int) -> None:
    snapshotId = f"snapshot-{cardId}"
    with sqlite3.connect(databasePath) as connection:
        inventoryId = connection.execute(
            "SELECT MAX(inventoryId) FROM cardInventory WHERE cardId = ?",
            (cardId,),
        ).fetchone()[0]
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cardInventorySnapshotIdentity (
                inventoryId INTEGER PRIMARY KEY,
                snapshotId TEXT NOT NULL UNIQUE
            )
            """
        )
        connection.execute(
            "INSERT INTO cardInventorySnapshotIdentity (inventoryId, snapshotId) VALUES (?, ?)",
            (inventoryId, snapshotId),
        )
        connection.commit()
    manifestDirectory.mkdir(parents=True, exist_ok=True)
    (manifestDirectory / "camera-import-test.json").write_text(
        json.dumps({"snapshotId": snapshotId, "assets": [{"outcome": "copied"}]}),
        encoding="utf-8",
    )


def _runner(command):
    values = list(command)
    if values[:5] == ["findmnt", "-n", "-o", "SOURCE", "--target"]:
        return subprocess.CompletedProcess(values, 0, "/dev/sdz1\n", "")
    if values[:5] == ["findmnt", "-n", "-o", "FSTYPE", "--target"]:
        return subprocess.CompletedProcess(values, 0, "exfat\n", "")
    if values[:3] == ["lsblk", "-no", "PKNAME"]:
        return subprocess.CompletedProcess(values, 0, "sdz\n", "")
    if values[:5] == ["lsblk", "-dn", "-o", "RM", "/dev/sdz"]:
        return subprocess.CompletedProcess(values, 0, "1\n", "")
    raise AssertionError(f"unexpected command: {values}")


def testCameraFormatTargetAcceptsCardNameAndNumber():
    assert cameraFormatTargetId("card18") == 18
    assert cameraFormatTargetId("Card018") == 18
    assert cameraFormatTargetId("18") == 18


def testCameraFormatPlanAllowsLatestArchivedContent(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 18)
    manifests = tmp_path / "manifests"
    _archiveLatest(databasePath, manifests, 18)
    mount = tmp_path / "media" / "1E2D-4694"
    mount.mkdir(parents=True)
    (mount / "organiseMyVideo.018").write_text('{"cardId": 18}', encoding="utf-8")

    plan = cameraFormatPlan(
        "card18",
        databasePath=databasePath,
        manifestDirectory=manifests,
        mountRoots=[mount.parent],
        commandRunner=_runner,
    )

    assert plan.cardId == 18
    assert plan.mountPath == mount.resolve()
    assert plan.devicePath == Path("/dev/sdz1")
    assert plan.filesystemType == "exfat"
    assert plan.volumeLabel == "Card18"
    assert plan.reviewFiles == ()


def testCameraFormatPlanRefusesUnarchivedCameraMedia(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 18)
    mount = tmp_path / "media" / "1E2D-4694"
    mount.mkdir(parents=True)
    (mount / "organiseMyVideo.018").write_text('{"cardId": 18}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="camera media is not archived"):
        cameraFormatPlan(
            "card18",
            databasePath=databasePath,
            manifestDirectory=tmp_path / "manifests",
            mountRoots=[mount.parent],
            commandRunner=_runner,
        )


def testCameraFormatPlanAllowsUserReviewOfOtherFilesystemContent(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 1, review=True)
    mount = tmp_path / "media" / "7000-8000"
    mount.mkdir(parents=True)
    (mount / "organiseMyVideo.001").write_text('{"cardId": 1}', encoding="utf-8")

    plan = cameraFormatPlan(
        "card1",
        databasePath=databasePath,
        manifestDirectory=tmp_path / "manifests",
        mountRoots=[mount.parent],
        commandRunner=_runner,
    )
    summary = cameraFormatSummary(plan, dryRun=True)

    assert plan.reviewFiles == ("important.csv",)
    assert "non-camera file(s) will be erased" in summary
    assert "important.csv" in summary
    assert "Confirm with -y" in summary


def testConfirmedFormatRepairsAndVerifiesStaleVolumeLabel(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 7)
    manifests = tmp_path / "manifests"
    _archiveLatest(databasePath, manifests, 7)
    mount = tmp_path / "media" / "Card7"
    mount.mkdir(parents=True)
    (mount / "organiseMyVideo.007").write_text('{"cardId": 7}', encoding="utf-8")

    state = {"label": "Card18"}
    commands: list[list[str]] = []

    def runner(command):
        values = list(command)
        commands.append(values)
        if values[:5] == ["findmnt", "-n", "-o", "SOURCE", "--target"]:
            return subprocess.CompletedProcess(values, 0, "/dev/sdz1\n", "")
        if values[:5] == ["findmnt", "-n", "-o", "FSTYPE", "--target"]:
            return subprocess.CompletedProcess(values, 0, "exfat\n", "")
        if values[:3] == ["lsblk", "-no", "PKNAME"]:
            return subprocess.CompletedProcess(values, 0, "sdz\n", "")
        if values[:5] == ["lsblk", "-dn", "-o", "RM", "/dev/sdz"]:
            return subprocess.CompletedProcess(values, 0, "1\n", "")
        if values == ["lsblk", "-no", "LABEL", "/dev/sdz1"]:
            return subprocess.CompletedProcess(values, 0, state["label"] + "\n", "")
        if values[:2] == ["sudo", "exfatlabel"]:
            state["label"] = values[-1]
            return subprocess.CompletedProcess(values, 0, "", "")
        if values == ["udisksctl", "mount", "-b", "/dev/sdz1"]:
            return subprocess.CompletedProcess(
                values,
                0,
                f"Mounted /dev/sdz1 at {mount}.\n",
                "",
            )
        if values[:2] in (["udisksctl", "unmount"], ["sudo", "mkfs.exfat"], ["sudo", "udevadm"]):
            return subprocess.CompletedProcess(values, 0, "", "")
        raise AssertionError(f"unexpected command: {values}")

    result = cameraFormatRun(
        "card7",
        dryRun=False,
        databasePath=databasePath,
        manifestDirectory=manifests,
        mountRoots=[mount.parent],
        commandRunner=runner,
    )

    assert result.volumeLabel == "Card7"
    assert result.mountPath == mount.resolve()
    assert ["sudo", "exfatlabel", "/dev/sdz1", "Card7"] in commands


def testConfirmedFormatRefusesFalseSuccessWhenLabelDoesNotChange(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 7)
    manifests = tmp_path / "manifests"
    _archiveLatest(databasePath, manifests, 7)
    mount = tmp_path / "media" / "Card18"
    mount.mkdir(parents=True)
    (mount / "organiseMyVideo.007").write_text('{"cardId": 7}', encoding="utf-8")

    def runner(command):
        values = list(command)
        if values[:5] == ["findmnt", "-n", "-o", "SOURCE", "--target"]:
            return subprocess.CompletedProcess(values, 0, "/dev/sdz1\n", "")
        if values[:5] == ["findmnt", "-n", "-o", "FSTYPE", "--target"]:
            return subprocess.CompletedProcess(values, 0, "exfat\n", "")
        if values[:3] == ["lsblk", "-no", "PKNAME"]:
            return subprocess.CompletedProcess(values, 0, "sdz\n", "")
        if values[:5] == ["lsblk", "-dn", "-o", "RM", "/dev/sdz"]:
            return subprocess.CompletedProcess(values, 0, "1\n", "")
        if values == ["lsblk", "-no", "LABEL", "/dev/sdz1"]:
            return subprocess.CompletedProcess(values, 0, "Card18\n", "")
        if values[:2] in (
            ["udisksctl", "unmount"],
            ["sudo", "mkfs.exfat"],
            ["sudo", "udevadm"],
            ["sudo", "exfatlabel"],
        ):
            return subprocess.CompletedProcess(values, 0, "", "")
        raise AssertionError(f"unexpected command: {values}")

    with pytest.raises(RuntimeError, match="volume label verification failed"):
        cameraFormatRun(
            "card7",
            dryRun=False,
            databasePath=databasePath,
            manifestDirectory=manifests,
            mountRoots=[mount.parent],
            commandRunner=runner,
        )


def testNewEmptyInventoryRevokesArchivedFlag(tmp_path: Path):
    databasePath = _inventoryCreate(tmp_path, 18)
    manifests = tmp_path / "manifests"
    _archiveLatest(databasePath, manifests, 18)

    archived = cameraInventoryList(
        databasePath=databasePath,
        cardId=18,
        manifestDirectory=manifests,
    )[0]
    assert archived.archived is True

    emptyCard = tmp_path / "Card18"
    emptyCard.mkdir()
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    service.inventoryPersist(service.inventoryScan(emptyCard, 18))

    current = cameraInventoryList(
        databasePath=databasePath,
        cardId=18,
        manifestDirectory=manifests,
    )[0]
    summary = cameraInventoryListSummary((current,))
    assert current.archived is False
    assert "018" in summary
    assert "empty" in summary
    assert "no" in summary
