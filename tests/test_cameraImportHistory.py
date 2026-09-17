"""Card identity and manifest-history coverage for camera archive/import services."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo import constants
from organiseMyVideo.cameraImport import (
    cameraCardIdResolve,
    cameraImportHistory,
    cameraImportHistorySummary,
    cameraImportRun,
    cameraImportSummary,
)


def cameraTreeBuild(tmp_path: Path, cardId: int = 1) -> tuple[Path, Path]:
    """Create a numbered synthetic GoPro card and return media directory/file."""

    card = tmp_path / "card"
    source = card / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    (card / f"organiseMyVideo.{cardId:03d}").write_text(
        json.dumps({"cardId": cardId}),
        encoding="utf-8",
    )
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")
    timestamp = datetime(2024, 4, 20, 12, 0, 0).timestamp()
    os.utime(media, (timestamp, timestamp))
    return source, media


def importRun(tmp_path: Path, source: Path, *, dryRun: bool):
    """Run the internal camera-import service against temporary archive roots."""

    return cameraImportRun(
        source=source,
        goproDestination=tmp_path / "archive" / "GoPro",
        droneDestination=tmp_path / "archive" / "Drone",
        dashcamDestination=tmp_path / "archive" / "Dashcam",
        manifestDirectory=tmp_path / "state" / "cameraImports",
        dryRun=dryRun,
    )


def manifestWrite(
    directory: Path,
    name: str,
    *,
    cardId,
    createdAt: str,
    source: str,
    outcomes: tuple[str, ...],
) -> Path:
    """Write one compact synthetic import manifest."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "importId": name.removesuffix(".json"),
                "createdAt": createdAt,
                "source": {"cardId": cardId, "path": source},
                "assets": [{"outcome": outcome} for outcome in outcomes],
            }
        ),
        encoding="utf-8",
    )
    return path


def testCameraImportDryRunResolvesCardIdentity(tmp_path: Path):
    source, _media = cameraTreeBuild(tmp_path, cardId=1)

    result = importRun(tmp_path, source, dryRun=True)

    assert cameraCardIdResolve(source) == 1
    assert result.cardId == 1
    assert "Card 001" in cameraImportSummary(result)
    assert result.manifestPath is None


def testConfirmedCameraImportPersistsCardAndImportIdentity(tmp_path: Path):
    source, _media = cameraTreeBuild(tmp_path, cardId=7)

    result = importRun(tmp_path, source, dryRun=False)

    assert result.cardId == 7
    assert result.importId
    assert result.snapshotId is None
    assert result.manifestPath is not None
    manifest = json.loads(result.manifestPath.read_text(encoding="utf-8"))
    assert manifest["source"]["cardId"] == 7
    assert manifest["importId"] == result.importId
    assert manifest["snapshotId"] is None
    assert manifest["schemaVersion"] == 3


def testConfirmedCameraImportRejectsUnnumberedSource(tmp_path: Path):
    source = tmp_path / "card" / "DCIM" / "100GOPRO"
    source.mkdir(parents=True)
    media = source / "GH010111.MP4"
    media.write_bytes(b"camera-original")

    with pytest.raises(RuntimeError, match="requires a numbered"):
        importRun(tmp_path, source, dryRun=False)

    assert not (tmp_path / "archive").exists()
    assert not (tmp_path / "state").exists()


def testCameraImportHistoryListsAndFiltersByCard(tmp_path: Path):
    manifests = tmp_path / "cameraImports"
    manifestWrite(
        manifests,
        "camera-import-20260913T140000000000Z.json",
        cardId=1,
        createdAt="2026-09-13T14:00:00+00:00",
        source="/media/card-one",
        outcomes=("copied", "alreadyPresent"),
    )
    manifestWrite(
        manifests,
        "camera-import-20260912T140000000000Z.json",
        cardId=2,
        createdAt="2026-09-12T14:00:00+00:00",
        source="/media/card-two",
        outcomes=("copied", "copied", "failed"),
    )

    allRecords = cameraImportHistory(manifests)
    cardRecords = cameraImportHistory(manifests, cardId=1)

    assert [item.cardId for item in allRecords] == [1, 2]
    assert len(cardRecords) == 1
    assert cardRecords[0].copied == 1
    assert cardRecords[0].alreadyPresent == 1
    summary = cameraImportHistorySummary(cardRecords, cardId=1)
    assert "CAMERA IMPORT HISTORY — CARD 001" in summary
    assert "/media/card-one" in summary
    assert "/media/card-two" not in summary


def testCameraHistoryCliShowsOnlyRequestedCard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    state = tmp_path / "state"
    manifests = state / "cameraImports"
    manifestWrite(
        manifests,
        "camera-import-20260913T140000000000Z.json",
        cardId=1,
        createdAt="2026-09-13T14:00:00+00:00",
        source="/media/card-one",
        outcomes=("copied",),
    )
    manifestWrite(
        manifests,
        "camera-import-20260912T140000000000Z.json",
        cardId=2,
        createdAt="2026-09-12T14:00:00+00:00",
        source="/media/card-two",
        outcomes=("copied",),
    )
    monkeypatch.setattr(constants, "applicationStateDirectory", lambda: state)

    assert applicationMain.main(["camera", "history", "--card", "1"]) == 0
    output = capsys.readouterr().out
    assert "CARD 001" in output
    assert "card-one" in output
    assert "card-two" not in output


def testCameraHistoryHelpShowsCard(capsys):
    with pytest.raises(SystemExit) as helpExit:
        applicationMain.main(["camera", "history", "--help"])

    assert helpExit.value.code == 0
    output = capsys.readouterr().out
    assert "--card" in output
    assert "--list" not in output
