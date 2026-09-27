"""REQ-028 camera history reconciliation tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from organiseMyVideo.cameraHistory import cameraHistoryCheck


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifestWrite(
    directory: Path,
    destination: Path,
    data: bytes,
    *,
    cardId: int = 18,
    digest: str | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "camera-import-20260925T120000000000Z.json"
    payload = {
        "schemaVersion": 3,
        "importId": "import-1",
        "createdAt": "2026-09-25T12:00:00+00:00",
        "source": {"cardId": cardId, "path": "/media/card"},
        "assets": [
            {
                "destinationPath": str(destination),
                "cameraKind": "gopro",
                "sizeBytes": len(data),
                "destinationDigest": digest or _digest(data),
                "outcome": "copied",
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def testCameraHistoryCheckReportsOk(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    destination = root / "2026" / "09" / "25" / "clip.MP4"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"camera-data")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, destination, b"camera-data")

    results = cameraHistoryCheck(manifests, cardId=18, archiveRoots=(root,))

    assert [(item.status, item.currentPath) for item in results] == [
        ("ok", destination)
    ]


def testCameraHistoryCheckReportsMoved(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    recorded = root / "2026" / "05-May" / "13" / "clip.MP4"
    current = root / "2026" / "05" / "13" / "clip.MP4"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"same-media")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"same-media")

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "moved"
    assert result.recordedPath == recorded
    assert result.currentPath == current


def testCameraHistoryCheckReportsMissing(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    root.mkdir()
    recorded = root / "2024" / "09" / "09" / "missing.MP4"
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"missing-media")

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "missing"
    assert result.currentPath is None


def testCameraHistoryCheckReportsAmbiguousWithoutChoosing(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    data = b"duplicate-media"
    for directory in ("a", "b"):
        path = root / directory / "clip.MP4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    recorded = root / "old" / "clip.MP4"
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, data)

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "ambiguous"
    assert result.currentPath is None
    assert len(result.matches) == 2


def testCameraHistoryCheckReportsChangedWithoutSubstitute(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    original = b"original"
    recorded = root / "2025" / "02" / "21" / "clip.MP4"
    recorded.parent.mkdir(parents=True)
    recorded.write_bytes(b"changed!")
    elsewhere = root / "elsewhere" / "clip.MP4"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_bytes(original)
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, original)

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "changed"
    assert result.currentPath == recorded


def testDigestIdentityBeatsFilenameSimilarity(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    recorded = root / "old" / "clip.MP4"
    wrong = root / "new" / "clip.MP4"
    wrong.parent.mkdir(parents=True)
    wrong.write_bytes(b"wrong")
    right = root / "other" / "renamed.MP4"
    right.parent.mkdir(parents=True)
    right.write_bytes(b"right")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"right")

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "moved"
    assert result.currentPath == right


def testCameraHistoryCheckIsNonMutating(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    root.mkdir()
    manifests = tmp_path / "manifests"
    manifest = _manifestWrite(manifests, root / "old.MP4", b"data")
    before = manifest.read_bytes()

    cameraHistoryCheck(manifests, archiveRoots=(root,))

    assert manifest.read_bytes() == before


def testLegacyManifestSourceDigestRemainsReadable(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    current = root / "2026" / "09" / "25" / "clip.MP4"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"legacy")
    manifests = tmp_path / "manifests"
    _manifestWrite(
        manifests,
        root / "legacy" / "clip.MP4",
        b"legacy",
        digest=_digest(b"legacy"),
    )
    payload = json.loads(next(manifests.iterdir()).read_text(encoding="utf-8"))
    payload["assets"][0]["sourceDigest"] = payload["assets"][0].pop("destinationDigest")
    next(manifests.iterdir()).write_text(json.dumps(payload), encoding="utf-8")

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "moved"
    assert result.currentPath == current


def testLegacyDigestWithoutSize(tmp_path):
    root = tmp_path / "GoPro"
    root.mkdir()
    current = root / "renamed.mp4"
    current.write_bytes(b"legacy")
    manifests = tmp_path / "manifests"
    manifest = _manifestWrite(manifests, root / "old.mp4", b"legacy")
    payload = json.loads(manifest.read_text())
    del payload["assets"][0]["sizeBytes"]
    manifest.write_text(json.dumps(payload))
    result = cameraHistoryCheck(manifests)[0]
    assert (result.status, result.currentPath) == ("moved", current)


def testUnreadableRecordedFile(tmp_path, monkeypatch):
    from organiseMyVideo import cameraHistory

    root = tmp_path / "GoPro"
    root.mkdir()
    recorded = root / "clip.mp4"
    recorded.write_bytes(b"data")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"data")

    def fail(path):
        raise PermissionError("unreadable media")

    monkeypatch.setattr(cameraHistory, "_fileSha256", fail)
    assert cameraHistoryCheck(manifests)[0].status == "unreadable"


def testRecordedFileDisappearsDuringRead(tmp_path, monkeypatch):
    from organiseMyVideo import cameraHistory

    root = tmp_path / "GoPro"
    root.mkdir()
    recorded = root / "clip.mp4"
    recorded.write_bytes(b"data")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"data")

    def disappear(path):
        path.unlink()
        raise FileNotFoundError(str(path))

    monkeypatch.setattr(cameraHistory, "_fileSha256", disappear)
    assert cameraHistoryCheck(manifests)[0].status == "missing"


def testIncompleteArchiveDoesNotClaimUniqueMatch(tmp_path, monkeypatch):
    from organiseMyVideo import cameraHistory

    root = tmp_path / "GoPro"
    root.mkdir()
    (root / "good.mp4").write_bytes(b"data")
    (root / "bad.mp4").write_bytes(b"data")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, root / "old.mp4", b"data")
    original = cameraHistory._fileSha256

    def read(path):
        if path.name == "bad.mp4":
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(cameraHistory, "_fileSha256", read)
    result = cameraHistoryCheck(manifests)[0]
    assert result.status == "unreadable"
    assert result.currentPath is None
    assert cameraHistory._archiveFileCountRead((root,)) == 0


def testDirectoryScanFailureContinues(tmp_path, monkeypatch):
    from organiseMyVideo import cameraHistory

    def walk(root, onerror):
        onerror(PermissionError("directory denied"))
        return iter(())

    monkeypatch.setattr(cameraHistory.os, "walk", walk)
    assert cameraHistory._digestIndexBuild((tmp_path,)) == ({}, False)


def testProgressCacheCorruptAndUnwritable(tmp_path, monkeypatch):
    from organiseMyVideo import cameraHistory

    state = cameraHistory.applicationStateDirectory()
    state.mkdir(parents=True)
    cache = state / "cameraHistoryProgress.json"
    cache.write_bytes(b"\xff")
    assert cameraHistory._archiveFileCountRead((tmp_path,)) == 0
    cameraHistory._archiveFileCountWrite((tmp_path,), 7)
    assert cameraHistory._archiveFileCountRead((tmp_path,)) == 7

    def fail(self, target):
        raise PermissionError("cache replacement denied")

    monkeypatch.setattr(Path, "replace", fail)
    cameraHistory._archiveFileCountWrite((tmp_path,), 9)
    assert cameraHistory._archiveFileCountRead((tmp_path,)) == 7
    assert list(state.glob("*.tmp")) == []


def testHistoryCheckSurvivesUnavailableState(tmp_path, monkeypatch):
    root = tmp_path / "GoPro"
    root.mkdir()
    current = root / "clip.mp4"
    current.write_bytes(b"data")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, root / "old.mp4", b"data")
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    monkeypatch.setenv("XDG_STATE_HOME", str(blocked))
    assert cameraHistoryCheck(manifests)[0].status == "moved"


def testHistoryCheckCliExecution(tmp_path, capsys):
    from organiseMyVideo import __main__ as applicationMain
    from organiseMyVideo.constants import applicationStateDirectory

    root = tmp_path / "GoPro"
    root.mkdir()
    current = root / "renamed.mp4"
    current.write_bytes(b"data")
    manifest = _manifestWrite(
        applicationStateDirectory() / "cameraImports", root / "old.mp4", b"data"
    )
    before = manifest.read_bytes()
    assert applicationMain.main(["camera", "history", "--check", "--card", "18"]) == 0
    output = capsys.readouterr().out
    assert "CAMERA HISTORY CHECK — CARD 018" in output
    assert "moved" in output
    assert str(current) in output
    assert manifest.read_bytes() == before
    assert current.read_bytes() == b"data"


def testRecordedStatFailureIsUnreadable(tmp_path, monkeypatch):
    root = tmp_path / "GoPro"
    root.mkdir()
    recorded = root / "clip.mp4"
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"data")
    original = Path.stat

    def stat(path, *args, **kwargs):
        if path == recorded:
            raise PermissionError("stat denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    assert cameraHistoryCheck(manifests)[0].status == "unreadable"


def testArchiveFileDisappearsDuringStat(tmp_path, monkeypatch):
    from organiseMyVideo import cameraHistory

    root = tmp_path / "GoPro"
    root.mkdir()
    candidate = root / "clip.mp4"
    candidate.write_bytes(b"data")
    original = Path.stat

    def stat(path, *args, **kwargs):
        if path == candidate:
            raise FileNotFoundError(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    assert cameraHistory._digestIndexBuild((root,)) == ({}, False)


def testHashRejectsReplacementDuringRead(tmp_path, monkeypatch):
    import pytest
    from organiseMyVideo import cameraHistory

    path = tmp_path / "clip.mp4"
    path.write_bytes(b"data")
    original = cameraHistory.os.fstat
    calls = 0

    def stat(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            path.unlink()
            path.write_bytes(b"different")
        return original(descriptor)

    monkeypatch.setattr(cameraHistory.os, "fstat", stat)
    with pytest.raises(OSError, match="changed while hashing"):
        cameraHistory._fileSha256(path)
