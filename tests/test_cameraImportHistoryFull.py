import json
from pathlib import Path

import pytest

import organiseMyVideo.__main__ as applicationMain
from organiseMyVideo import constants
from organiseMyVideo.cameraImport import CameraImportHistoryRecord
from organiseMyVideo.cameraImportHistoryView import cameraImportHistoryFullSummary


def _manifestWrite(path: Path, *, cardId: int = 4) -> None:
    path.parent.mkdir(parents=True)
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
                        "destinationPath": "/mnt/myVideo/Video/GoPro/2026/09-Sep/15/A.MP4",
                        "outcome": "copied",
                    },
                    {
                        "sourcePath": "/media/card/DCIM/B.MP4",
                        "destinationPath": "/mnt/myVideo/Video/GoPro/2026/09-Sep/15/B.MP4",
                        "outcome": "alreadyPresent",
                    },
                    {
                        "sourcePath": "/media/card/DCIM/C.MP4",
                        "destinationPath": "/mnt/myVideo/Video/GoPro/2026/09-Sep/15/C.MP4",
                        "outcome": "failed",
                        "error": "OSError: verification failed",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def testCameraImportHistoryFullSummaryShowsPerFileDestinations(tmp_path: Path):
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

    assert "CAMERA IMPORT HISTORY — CARD 004 — FULL" in summary
    assert "copied" in summary
    assert "/mnt/myVideo/Video/GoPro/2026/09-Sep/15/A.MP4" in summary
    assert "already present" in summary
    assert "/mnt/myVideo/Video/GoPro/2026/09-Sep/15/B.MP4" in summary
    assert "failed" in summary
    assert "OSError: verification failed" in summary
    assert "2 archived files" in summary
    assert "1 failed file" in summary


def testCameraImportHistoryFullCliForOneCard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    state = tmp_path / "state" / "organiseMyVideo"
    manifest = state / "cameraImports" / "camera-import-1.json"
    _manifestWrite(manifest, cardId=4)
    monkeypatch.setattr(constants, "applicationStateDirectory", lambda: state)

    result = applicationMain.main(
        ["camera", "import", "--list", "--card", "4", "--full"]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "CAMERA IMPORT HISTORY — CARD 004 — FULL" in output
    assert "A.MP4" in output
    assert "B.MP4" in output


def testCameraImportHistoryFullRequiresCard(capsys):
    with pytest.raises(SystemExit):
        applicationMain.main(["camera", "import", "--list", "--full"])
    assert "--full requires --card" in capsys.readouterr().err
