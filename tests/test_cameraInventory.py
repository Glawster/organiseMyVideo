"""Service tests for numeric camera-card inventory snapshots."""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cameraFixtures import (
    cardTreeBuild,
    cardVolumeFake,
    dashcamTreeBuild,
    jpegWithoutExif,
)
from organiseMyVideo.cameraInventory import (
    CameraInventory,
    _cidDecode,
    _marketedGigabytes,
    cameraInventoryRun,
    cameraInventorySummary,
)
from organiseMyVideo.constants import cameraCardLabelFilename


@pytest.fixture
def databasePath(tmp_path: Path) -> Path:
    return tmp_path / "state" / "cameraInventory.sqlite"


@pytest.fixture
def cardRoot(tmp_path: Path) -> Path:
    return cardTreeBuild(tmp_path / "card")


def testInventoryScanReportsDatesSizeAndCountsWithoutWriting(
    cardRoot: Path, databasePath: Path
):
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    record = service.inventoryScan(cardRoot, 12)

    assert record.cardId == 12
    assert record.dateSource == "capture-metadata"
    assert record.dateStart.startswith("2024-04-18")
    assert record.dateEnd.startswith("2024-04-20")
    assert record.capacity.contentBytes > 0
    assert record.capacity.totalBytes is not None
    assert record.fileCounts["video"] == 2
    assert record.fileCounts["thumbnail"] == 1
    assert record.fileCounts["preview"] == 1
    assert record.fileCounts["sidecar"] == 1
    assert record.fileCounts["photo"] == 1
    assert record.cameraKinds == ("dji", "gopro")
    assert record.manufacturer == "GoPro"
    assert record.cameraModel == "HERO"
    assert record.cameraSerial == "C3544225115979"
    assert record.firmwareVersion == "H24.03.02.30.00"
    assert record.visionStatus == "dry-run"
    assert record.contentSummary == ""
    assert record.thumbnailSampled == 1
    assert not databasePath.exists()
    relativePaths = {item.relativePath for item in record.files}
    assert "DCIM/100GOPRO/GH010111.MP4" in relativePaths
    assert "DCIM/100GOPRO/._GH010111.MP4" not in relativePaths
    assert not any(path.startswith("MISC/") for path in relativePaths)


def testInventoryConfirmPersistsSnapshotAndVisionSummary(
    cardRoot: Path, databasePath: Path
):
    described = []

    def visionDescribe(paths):
        described.extend(paths)
        return "Harbour and coastal walking on one outing."

    service = CameraInventory(
        dryRun=False,
        databasePath=databasePath,
        visionDescribe=visionDescribe,
    )

    scanned = service.inventoryScan(cardRoot, 12)
    service.inventoryPersist(scanned)
    stored = service.inventoryShow(12)

    assert stored is not None
    assert stored.cardId == 12
    assert stored.contentSummary == "Harbour and coastal walking on one outing."
    assert stored.visionStatus == "described"
    assert described and described[0].name.endswith(".THM")
    assert databasePath.is_file()
    connection = sqlite3.connect(databasePath)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(cardInventory)")}
    connection.close()
    assert "cardId" in columns
    assert "contentSummary" in columns
    assert "dateStart" in columns


def testRepeatInventoryKeepsHistoryAndShowReturnsLatest(
    cardRoot: Path, databasePath: Path
):
    first = CameraInventory(
        dryRun=False,
        databasePath=databasePath,
        visionDescribe=lambda paths: "first outing",
    )
    second = CameraInventory(
        dryRun=False,
        databasePath=databasePath,
        visionDescribe=lambda paths: "second outing",
    )

    first.inventoryPersist(first.inventoryScan(cardRoot, 7))
    second.inventoryPersist(second.inventoryScan(cardRoot, 7))
    shown = second.inventoryShow(7)

    assert shown is not None
    assert shown.contentSummary == "second outing"
    connection = sqlite3.connect(databasePath)
    count = connection.execute(
        "SELECT COUNT(*) FROM cardInventory WHERE cardId = 7"
    ).fetchone()[0]
    connection.close()
    assert count == 2


def testFilesystemMtimeUsedWhenCaptureMetadataIsMissing(
    tmp_path: Path, databasePath: Path
):
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    photo = source / "G0010111.JPG"
    photo.write_bytes(jpegWithoutExif())
    stamp = datetime(2023, 5, 1, 8, 0, 0).timestamp()
    os.utime(photo, (stamp, stamp))
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    record = service.inventoryScan(tmp_path / "card", 3)

    assert record.dateSource == "filesystem-mtime"
    assert record.dateStart is not None
    assert record.dateStart.startswith("2023-05-01") or record.dateStart.startswith(
        "2023-04-30"
    )


def testJpegStillsAreSampledWhenThmFilesAreAbsent(tmp_path: Path, databasePath: Path):
    card = cardTreeBuild(tmp_path / "card", withThm=False, withDji=False)
    sampled = []
    service = CameraInventory(
        dryRun=False,
        databasePath=databasePath,
        visionDescribe=lambda paths: sampled.extend(paths) or "stills only",
    )

    record = service.inventoryScan(card, 4)

    assert record.fileCounts["thumbnail"] == 0
    assert record.fileCounts["photo"] == 1
    assert sampled and sampled[0].suffix.lower() == ".jpg"
    assert record.visionStatus == "described"


def testMissingApiKeyStillPersistsMetadata(
    cardRoot: Path, databasePath: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    service = CameraInventory(dryRun=False, databasePath=databasePath)

    record = service.inventoryScan(cardRoot, 9)
    service.inventoryPersist(record)
    stored = service.inventoryShow(9)

    assert stored is not None
    assert stored.dateStart is not None
    assert stored.contentSummary == ""
    assert stored.visionStatus == "unavailable"


def testInvalidCardIdIsRejected(cardRoot: Path, databasePath: Path):
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    with pytest.raises(ValueError, match="positive integer"):
        service.inventoryScan(cardRoot, 0)
    with pytest.raises(ValueError, match="positive integer"):
        service.inventoryScan(cardRoot, -2)
    with pytest.raises(ValueError, match="positive integer"):
        service.inventoryShow(True)  # type: ignore[arg-type]


def testShowWithoutSnapshotFailsWithoutCreatingRows(databasePath: Path):
    with pytest.raises(RuntimeError, match="no inventory stored"):
        cameraInventoryRun(cardId=15, dryRun=True, databasePath=databasePath)

    assert not databasePath.exists()


def testDryRunRunnerDoesNotPersist(cardRoot: Path, databasePath: Path):
    record = cameraInventoryRun(
        cardId=12,
        source=cardRoot,
        dryRun=True,
        databasePath=databasePath,
        visionDescribe=lambda paths: "should not run",
    )

    assert record.visionStatus == "dry-run"
    assert not databasePath.exists()


def testDashcamViofoTreeIsClassifiedAndDatedFromFilename(
    tmp_path: Path, databasePath: Path
):
    card = dashcamTreeBuild(tmp_path / "card", layout="viofo")
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    record = service.inventoryScan(card, 21)

    assert record.cameraKinds == ("dashcam",)
    assert record.fileCounts["video"] == 3
    assert record.dateSource == "capture-metadata"
    assert record.dateStart.startswith("2024-04-18")
    assert {item.cameraKind for item in record.files} == {"dashcam"}


def testDashcamBlackvueAndGarminLayoutsAreDashcam(tmp_path: Path, databasePath: Path):
    service = CameraInventory(dryRun=True, databasePath=databasePath)
    blackvue = service.inventoryScan(
        dashcamTreeBuild(tmp_path / "blackvue", layout="blackvue"), 22
    )
    garmin = service.inventoryScan(
        dashcamTreeBuild(tmp_path / "garmin", layout="garmin"), 23
    )

    assert blackvue.cameraKinds == ("dashcam",)
    assert blackvue.dateStart.startswith("2025-07-22")
    assert garmin.cameraKinds == ("dashcam",)
    assert garmin.fileCounts["video"] == 2


def testDashcamConfirmPersistsDashcamKind(tmp_path: Path, databasePath: Path):
    card = dashcamTreeBuild(tmp_path / "card", layout="blackvue")
    service = CameraInventory(dryRun=False, databasePath=databasePath)

    service.inventoryPersist(service.inventoryScan(card, 24))
    stored = service.inventoryShow(24)

    assert stored is not None
    assert stored.cameraKinds == ("dashcam",)


def testDashcamTranscendDriveProLayoutIsRecognised(tmp_path: Path, databasePath: Path):
    card = dashcamTreeBuild(tmp_path / "card", layout="transcend")
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    record = service.inventoryScan(card, 31)

    kinds = {item.cameraKind for item in record.files}
    relativePaths = {item.relativePath for item in record.files}
    assert record.cameraKinds == ("dashcam",)
    assert record.fileCounts["video"] == 4
    assert kinds == {"dashcam"}
    assert record.dateStart.startswith("2026-05-13T12:02:37")
    assert record.dateEnd.startswith("2026-05-13T13:00:00")
    assert "DP250/N_VIDEO/2026_0513_120237_012.mp4" in relativePaths
    assert not any("/SYSTEM/" in path for path in relativePaths)
    assert record.manufacturer == "Transcend"
    assert record.cameraModel == "DrivePro 250"


def testConfirmWritesCardLabelFile(
    cardRoot: Path, databasePath: Path, monkeypatch: pytest.MonkeyPatch
):
    cardVolumeFake(monkeypatch, 32_000_000_000, 4_000_000_000)
    service = CameraInventory(dryRun=False, databasePath=databasePath)
    label = cardRoot / cameraCardLabelFilename(1)

    service.inventoryPersist(service.inventoryScan(cardRoot, 1))

    assert label.is_file()
    payload = json.loads(label.read_text(encoding="utf-8"))
    assert payload["cardId"] == 1
    assert payload["application"] == "organiseMyVideo"
    assert payload["cardRatedGigabytes"] == 32
    assert payload["freeBytes"] == 4_000_000_000
    assert "Card size:" in payload["summary"]
    assert "32 GB" in payload["summary"]
    assert "Free space:" in payload["summary"]
    relativePaths = {
        item.relativePath for item in service.inventoryScan(cardRoot, 1).files
    }
    assert cameraCardLabelFilename(1) not in relativePaths


def testDryRunDoesNotWriteCardLabelFile(cardRoot: Path, databasePath: Path):
    service = CameraInventory(dryRun=True, databasePath=databasePath)
    record = service.inventoryScan(cardRoot, 1)
    service.inventoryPersist(record)

    assert not (cardRoot / cameraCardLabelFilename(1)).exists()


def testScanWithoutCardUsesOnCardLabel(cardRoot: Path, databasePath: Path):
    writer = CameraInventory(dryRun=False, databasePath=databasePath)
    writer.inventoryPersist(writer.inventoryScan(cardRoot, 7))
    reader = CameraInventory(dryRun=True, databasePath=databasePath)

    record = reader.inventoryScan(cardRoot)

    assert record.cardId == 7


def testMismatchedCardIdIsRefused(cardRoot: Path, databasePath: Path):
    writer = CameraInventory(dryRun=False, databasePath=databasePath)
    writer.inventoryPersist(writer.inventoryScan(cardRoot, 1))
    original = (cardRoot / cameraCardLabelFilename(1)).read_text(encoding="utf-8")
    attacker = CameraInventory(dryRun=False, databasePath=databasePath)

    with pytest.raises(ValueError, match="pass --reassign"):
        attacker.inventoryScan(cardRoot, 2)

    assert (cardRoot / cameraCardLabelFilename(1)).read_text(
        encoding="utf-8"
    ) == original
    assert attacker.inventoryShow(2) is None


def testReassignChangesOnCardId(cardRoot: Path, databasePath: Path):
    writer = CameraInventory(dryRun=False, databasePath=databasePath)
    writer.inventoryPersist(writer.inventoryScan(cardRoot, 1))
    dry = CameraInventory(dryRun=True, databasePath=databasePath)
    dry.inventoryPersist(dry.inventoryScan(cardRoot, 5, reassign=True))
    assert (
        json.loads((cardRoot / cameraCardLabelFilename(1)).read_text())["cardId"] == 1
    )
    assert not (cardRoot / cameraCardLabelFilename(5)).exists()

    writer.inventoryPersist(writer.inventoryScan(cardRoot, 5, reassign=True))
    payload = json.loads((cardRoot / cameraCardLabelFilename(5)).read_text())
    stored = writer.inventoryShow(5)

    assert payload["cardId"] == 5
    assert not (cardRoot / cameraCardLabelFilename(1)).exists()
    assert stored is not None
    assert stored.cardId == 5
    assert writer.inventoryShow(1) is not None


def testReassignWithoutExistingLabelIsRejected(cardRoot: Path, databasePath: Path):
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    with pytest.raises(ValueError, match="no card label to reassign"):
        service.inventoryScan(cardRoot, 2, reassign=True)


def testFirstScanRequiresCardId(cardRoot: Path, databasePath: Path):
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    with pytest.raises(ValueError, match="card ID is required"):
        service.inventoryScan(cardRoot)


def testMarketedGigabytesRecognisesOperatorCardSizes():
    assert _marketedGigabytes(31_000_000_000) == 32
    assert _marketedGigabytes(62_000_000_000) == 64
    assert _marketedGigabytes(127831900160) == 128
    assert _marketedGigabytes(250_000_000_000) == 256
    assert _marketedGigabytes(1000) is None
    assert _marketedGigabytes(1_000_000_000_000) is None


def testRatedSizeFallsBackToOnCardLabel(
    cardRoot: Path, databasePath: Path, monkeypatch: pytest.MonkeyPatch
):
    cardVolumeFake(monkeypatch, 64_000_000_000, 8_000_000_000)
    writer = CameraInventory(dryRun=False, databasePath=databasePath)
    writer.inventoryPersist(writer.inventoryScan(cardRoot, 1))
    cardVolumeFake(monkeypatch, 1_000_000_000_000, 500_000_000_000)
    record = CameraInventory(dryRun=True, databasePath=databasePath).inventoryScan(
        cardRoot
    )

    assert record.cardRatedGigabytes == 64


def testCidDecodeReadsSandiskManufacturer():
    decoded = _cidDecode("03534453553132388000000000000000")

    assert decoded["brand"] == "SanDisk"
    assert decoded["product"] == "SU128"


def testBrandOptionIsStoredOnCardLabel(cardRoot: Path, databasePath: Path):
    writer = CameraInventory(dryRun=False, databasePath=databasePath)
    writer.inventoryPersist(writer.inventoryScan(cardRoot, 1, brand="SanDisk"))
    payload = json.loads((cardRoot / cameraCardLabelFilename(1)).read_text())
    reader = CameraInventory(dryRun=True, databasePath=databasePath)
    record = reader.inventoryScan(cardRoot)

    assert payload["cardBrand"] == "SanDisk"
    assert record.cardBrand == "SanDisk"
    stored = reader.inventoryShow(1)
    assert stored.cardBrand == "SanDisk"
    summary = cameraInventorySummary(stored, persisted=True, databasePath=databasePath)
    assert "Brand:            SanDisk" in summary
    assert "Cameras:" not in summary
    assert f"Camera:           {record.manufacturer} {record.cameraModel}" in summary
    assert "Manufacturer:" not in summary
    assert stored.cameraModel == record.cameraModel


def testGoproCardIsNotClassifiedAsDashcam(cardRoot: Path, databasePath: Path):
    service = CameraInventory(dryRun=True, databasePath=databasePath)

    record = service.inventoryScan(cardRoot, 12)

    assert "dashcam" not in record.cameraKinds
    assert "gopro" in record.cameraKinds


@pytest.mark.parametrize("dryRun", [True, False])
def testInventoryRejectsMountContainerBeforeScanning(tmp_path, monkeypatch, dryRun):
    mount = tmp_path / "disk"
    mount.mkdir()
    monkeypatch.setattr(os.path, "ismount", lambda path: Path(path) == mount)
    database = tmp_path / "catalogue.sqlite"
    service = CameraInventory(dryRun=dryRun, databasePath=database)

    with pytest.raises(ValueError, match="select the card mount itself") as error:
        service.inventoryScan(tmp_path, 2)

    assert str(mount) in str(error.value)
    assert not database.exists()
    assert not (tmp_path / cameraCardLabelFilename(2)).exists()


def testLegacyGoproMiscMetadataSurvivesPersistence(tmp_path, databasePath):
    card = cardTreeBuild(tmp_path / "card")
    (card / "MISC" / "version.txt").write_text(
        '{"camera type":"HERO4 Silver", "camera serial number":"example-serial",'
        '"firmware version":"HD4.01.05.00.00", "wifi mac":"001122334455",\n}'
    )
    (card / "MISC" / "card").write_text("0012345678901234567\n")
    service = CameraInventory(dryRun=False, databasePath=databasePath)

    record = service.inventoryScan(card, 2)
    service.inventoryPersist(record)
    stored = service.inventoryShow(2)
    payload = json.loads((card / cameraCardLabelFilename(2)).read_text())

    expected = dict(
        manufacturer="GoPro",
        cameraModel="HERO4 Silver",
        cameraSerial="example-serial",
        firmwareVersion="HD4.01.05.00.00",
        cameraWifiMac="001122334455",
        goproCardId="0012345678901234567",
    )
    for name, value in expected.items():
        assert getattr(record, name) == value
        assert getattr(stored, name) == value
        assert payload[name] == value
    assert stored.cardId == 2


@pytest.mark.parametrize("contents", [None, b"not json", b"\xff", b"[]"])
def testOptionalMiscMetadataDoesNotPreventInventory(tmp_path, contents):
    card = cardTreeBuild(tmp_path / "card")
    version = card / "MISC" / "version.txt"
    if contents is None:
        version.unlink()
    else:
        version.write_bytes(contents)
    (card / "MISC" / "card").write_bytes(b"\xff")

    record = CameraInventory(dryRun=True).inventoryScan(card, 2)

    assert record.cameraModel is None
    assert record.cameraWifiMac is None
    assert record.goproCardId is None
