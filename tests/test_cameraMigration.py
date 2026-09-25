"""Tests for safe legacy camera archive duplicate reconciliation."""

from pathlib import Path

import organiseMyVideo.cameraMigration as cameraMigration
from organiseMyVideo.cameraMigration import cameraMonthDuplicatesReconcile


def _write(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def testDryRunFindsDuplicateCandidateWithoutHashing(tmp_path: Path, monkeypatch) -> None:
    canonical = _write(tmp_path / "2015" / "01" / "04" / "GOPR4171.MP4", b"same")
    legacy = _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"same")

    monkeypatch.setattr(
        cameraMigration,
        "_sha256",
        lambda _path: (_ for _ in ()).throw(AssertionError("dry-run must not hash")),
    )

    result = cameraMonthDuplicatesReconcile(tmp_path)

    assert result.dryRun is True
    assert result.removedFiles == 0
    assert len(result.duplicates) == 1
    assert result.duplicates[0].legacyPath == legacy
    assert result.duplicates[0].canonicalPath == canonical
    assert result.duplicates[0].sha256 is None
    assert legacy.exists()
    assert canonical.exists()


def testDryRunTreatsSameSizeDifferentContentAsCandidate(tmp_path: Path) -> None:
    _write(tmp_path / "2015" / "01" / "04" / "GOPR4171.MP4", b"1234")
    _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"5678")

    result = cameraMonthDuplicatesReconcile(tmp_path)

    assert len(result.duplicates) == 1
    assert not result.conflicts


def testConfirmedRunRemovesOnlyShaVerifiedLegacyDuplicate(tmp_path: Path) -> None:
    canonical = _write(tmp_path / "2015" / "01" / "04" / "GOPR4171.MP4", b"same")
    legacy = _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"same")

    result = cameraMonthDuplicatesReconcile(tmp_path, dryRun=False)

    assert result.removedFiles == 1
    assert len(result.duplicates) == 1
    assert result.duplicates[0].sha256 is not None
    assert not legacy.exists()
    assert canonical.exists()
    assert not (tmp_path / "2015" / "01-Jan").exists()


def testDifferentContentIsRetainedAsConflictOnConfirm(tmp_path: Path) -> None:
    canonical = _write(tmp_path / "2015" / "01" / "04" / "GOPR4171.MP4", b"1234")
    legacy = _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"5678")

    result = cameraMonthDuplicatesReconcile(tmp_path, dryRun=False)

    assert result.removedFiles == 0
    assert not result.duplicates
    assert len(result.conflicts) == 1
    assert result.conflicts[0].reason == "SHA-256 differs"
    assert legacy.exists()
    assert canonical.exists()


def testDifferentSizeIsRetainedWithoutHashing(tmp_path: Path, monkeypatch) -> None:
    canonical = _write(tmp_path / "2015" / "01" / "04" / "GOPR4171.MP4", b"canonical")
    legacy = _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"legacy")

    monkeypatch.setattr(
        cameraMigration,
        "_sha256",
        lambda _path: (_ for _ in ()).throw(AssertionError("size conflict must not hash")),
    )

    result = cameraMonthDuplicatesReconcile(tmp_path, dryRun=False)

    assert result.removedFiles == 0
    assert not result.duplicates
    assert len(result.conflicts) == 1
    assert result.conflicts[0].reason == "size differs"
    assert legacy.exists()
    assert canonical.exists()


def testMissingCanonicalFileIsRetained(tmp_path: Path) -> None:
    legacy = _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"only copy")

    result = cameraMonthDuplicatesReconcile(tmp_path, dryRun=False)

    assert result.removedFiles == 0
    assert len(result.conflicts) == 1
    assert result.conflicts[0].reason == "canonical file missing"
    assert legacy.exists()


def testUnrelatedDirectoriesAreIgnored(tmp_path: Path) -> None:
    _write(tmp_path / "2015" / "January" / "04" / "GOPR4171.MP4", b"same")
    _write(tmp_path / "other" / "01-Jan" / "04" / "GOPR4171.MP4", b"same")

    result = cameraMonthDuplicatesReconcile(tmp_path)

    assert not result.duplicates
    assert not result.conflicts


def testProgressReportsStartAndEachInspectedLegacyFile(tmp_path: Path) -> None:
    _write(tmp_path / "2015" / "01" / "04" / "GOPR4171.MP4", b"same")
    _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4171.MP4", b"same")
    _write(tmp_path / "2015" / "01-Jan" / "04" / "GOPR4172.MP4", b"missing")
    progress: list[tuple[int, int, str]] = []

    cameraMonthDuplicatesReconcile(
        tmp_path,
        progressCallback=lambda completed, total, name: progress.append(
            (completed, total, name)
        ),
    )

    assert progress[0] == (0, 2, "")
    assert progress[-1][0:2] == (2, 2)
    assert {entry[2] for entry in progress[1:]} == {"GOPR4171.MP4", "GOPR4172.MP4"}
