"""REQ-028 camera history reconciliation tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from organiseMyVideo.cameraHistory import cameraHistoryCheck


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifestWrite(directory: Path, destination: Path, data: bytes, *, cardId: int = 18, digest: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "camera-import-20260925T120000000000Z.json"
    payload = {
        "schemaVersion": 3,
        "importId": "import-1",
        "createdAt": "2026-09-25T12:00:00+00:00",
        "source": {"cardId": cardId, "path": "/media/card"},
        "assets": [{
            "destinationPath": str(destination),
            "cameraKind": "gopro",
            "sizeBytes": len(data),
            "destinationDigest": digest or _digest(data),
            "outcome": "copied",
        }],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_history_check_reports_ok(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    destination = root / "2026" / "09" / "25" / "clip.MP4"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"camera-data")
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, destination, b"camera-data")

    results = cameraHistoryCheck(manifests, cardId=18, archiveRoots=(root,))

    assert [(item.status, item.currentPath) for item in results] == [("ok", destination)]


def test_history_check_reports_moved(tmp_path: Path) -> None:
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


def test_history_check_reports_missing(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    root.mkdir()
    recorded = root / "2024" / "09" / "09" / "missing.MP4"
    manifests = tmp_path / "manifests"
    _manifestWrite(manifests, recorded, b"missing-media")

    result = cameraHistoryCheck(manifests, archiveRoots=(root,))[0]

    assert result.status == "missing"
    assert result.currentPath is None


def test_history_check_reports_ambiguous_without_choosing(tmp_path: Path) -> None:
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


def test_history_check_reports_changed_and_does_not_substitute_match(tmp_path: Path) -> None:
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


def test_digest_identity_beats_filename_similarity(tmp_path: Path) -> None:
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


def test_history_check_is_non_mutating(tmp_path: Path) -> None:
    root = tmp_path / "GoPro"
    root.mkdir()
    manifests = tmp_path / "manifests"
    manifest = _manifestWrite(manifests, root / "old.MP4", b"data")
    before = manifest.read_bytes()

    cameraHistoryCheck(manifests, archiveRoots=(root,))

    assert manifest.read_bytes() == before


def test_legacy_manifest_source_digest_remains_readable(tmp_path: Path) -> None:
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
