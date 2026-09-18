import json
from pathlib import Path

import pytest

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo import constants
from organiseMyVideo.cameraImport import CameraImportHistoryRecord
from organiseMyVideo.cameraImportHistoryView import cameraImportHistoryFullSummary


def _manifestWrite(path: Path, *, cardId: int = 4) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 3,
                "importId": "import-1",
                "snapshotId": "snapshot-1",
                "createdAt": "2026-09-15T12:34:56+00:00",
                "source": {"cardId": cardId, "path": "/media/card"},
                "assets": [
                    {
                        "sourcePath": "/media/card/DCIM/A.MP4",
                        "destinationPath": "/mnt/myVideo/Video/GoPro/2026/09/15/A.MP4",
                        "outcome": "copied",
                    },
                    {
                        "sourcePath": "/media/card/DCIM/B.MP4",
                        "destinationPath": "/mnt/myVideo/Video/GoPro/2026/09/15/B.MP4",
                        "outcome": "alreadyPresent",
                    },
                    {
                        "sourcePath": "/media/card/DCIM/C.MP4",
                        "destinationPath": "/mnt/myVideo/Video/GoPro/2026/09/15/C.MP4",
                        "outcome": "failed",
                        "error": "OSError: verification failed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def testCameraImportHistoryFullSummaryUsesDestinationOutputRows(tmp_path: Path):
    manifest = tmp_path / "camera-import-1.json"
    _manifestWrite(manifest)
    record = CameraImportHistoryRecord(
        manifestPath=manifest,
        importId="import-1",
        createdAt="2026-09-15T12:34:56+00:00",
        cardId=4,
        snapshotId="snapshot-1",
        sourcePath="/media/card",
        copied=1,
        alreadyPresent=1,
        failed=1,
    )
    summary = cameraImportHistoryFullSummary((record,), cardId=4)
    assert "CAMERA IMPORT HISTORY — CARD 004" in summary
    assert "IMPORT 2026/09/15 12:34" in summary
    assert "Source root:   /media/card" in summary
    assert "Archive root:  /mnt/myVideo/Video/GoPro/2026/09-Sep/15" in summary
    assert "Result:        1 copied, 1 already present, 1 failed" in summary
    assert "Result" in summary and "Output" in summary
    assert "Source" not in next(line for line in summary.splitlines() if "Output" in line)

    copiedLine = next(line for line in summary.splitlines() if line.endswith("A.MP4"))
    presentLine = next(line for line in summary.splitlines() if "B.MP4" in line)
    failedLine = next(line for line in summary.splitlines() if "C.MP4" in line)
    assert "/mnt/myVideo/Video/GoPro/2026/09/15/A.MP4" in copiedLine
    assert "already present" in presentLine
    assert "OSError: verification failed" in failedLine
    assert "2 archived files" in summary
    assert "1 failed file" in summary


def testCameraHistoryShowsLongDestinationWithoutTruncation(tmp_path: Path):
    manifest = tmp_path / "camera-import-long.json"
    longDestination = "/mnt/myVideo/Video/GoPro/2026/09/15/very/long/destination/folder/GOPR4171.MP4"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 3,
                "assets": [
                    {
                        "sourcePath": "/media/card/DCIM/GOPR4171.MP4",
                        "destinationPath": longDestination,
                        "outcome": "copied",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    record = CameraImportHistoryRecord(
        manifestPath=manifest,
        importId="import-long",
        createdAt="2026-09-15T12:34:56+00:00",
        cardId=4,
        snapshotId="snapshot-long",
        sourcePath="/media/card",
        copied=1,
        alreadyPresent=0,
        failed=0,
    )

    summary = cameraImportHistoryFullSummary((record,), cardId=4)
    outputLine = next(line for line in summary.splitlines() if "GOPR4171.MP4" in line)
    assert longDestination in outputLine
    assert "…" not in outputLine



def testCameraHistoryShowsManifestDetail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    state = tmp_path / "state" / "organiseMyVideo"
    manifest = state / "cameraImports" / "camera-import-1.json"
    _manifestWrite(manifest, cardId=4)
    monkeypatch.setattr(constants, "applicationStateDirectory", lambda: state)

    result = applicationMain.main(["camera", "history", "--card", "4"])
    assert result == 0
    output = capsys.readouterr().out
    assert "CAMERA IMPORT HISTORY — CARD 004" in output
    assert "Source root:" in output
    assert "Archive root:" in output
    assert "/mnt/myVideo/Video/GoPro/2026/09/15/A.MP4" in output
    assert "/mnt/myVideo/Video/GoPro/2026/09/15/B.MP4" in output
