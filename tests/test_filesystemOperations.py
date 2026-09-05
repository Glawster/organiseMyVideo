"""Tests for the central filesystem mutation boundary."""

import errno
from pathlib import Path
from unittest.mock import patch

import pytest

from organiseMyVideo.filesystemOperations import FilesystemOperations


def testDryRunRecordsMoveWithoutMutation(tmp_path: Path):
    source = tmp_path / "source.mp4"
    destination = tmp_path / "archive" / "source.mp4"
    source.write_bytes(b"video")
    filesystem = FilesystemOperations(dryRun=True)

    filesystem.move(source, destination)

    assert source.exists()
    assert not destination.exists()
    assert filesystem.operations[0].action == "move"
    assert filesystem.operations[0].destination == destination


def testMoveRejectsMissingSourceAndDestinationCollision(tmp_path: Path):
    filesystem = FilesystemOperations(dryRun=True)
    source = tmp_path / "source.mp4"
    destination = tmp_path / "destination.mp4"

    with pytest.raises(FileNotFoundError):
        filesystem.move(source, destination)

    source.write_bytes(b"source")
    destination.write_bytes(b"destination")
    with pytest.raises(FileExistsError):
        filesystem.move(source, destination)


def testWriteBytesAtomicallyReplacesContent(tmp_path: Path):
    destination = tmp_path / "state" / "catalog.json"
    destination.parent.mkdir()
    destination.write_bytes(b"old")

    FilesystemOperations(dryRun=False).writeBytes(
        destination, b"new", stateKind="application-state"
    )

    assert destination.read_bytes() == b"new"
    assert list(destination.parent.glob(".*.tmp")) == []


def testCopyFileVerifiesAndPreservesSource(tmp_path: Path):
    source = tmp_path / "source.mp4"
    destination = tmp_path / "archive" / "source.mp4"
    source.write_bytes(b"video")

    FilesystemOperations(dryRun=False).copyFile(source, destination)

    assert source.read_bytes() == b"video"
    assert destination.read_bytes() == b"video"


def testCrossFilesystemMoveVerifiesBeforeRemovingSource(tmp_path: Path):
    source = tmp_path / "source.mp4"
    destination = tmp_path / "archive" / "source.mp4"
    source.write_bytes(b"video")
    filesystem = FilesystemOperations(dryRun=False)
    originalRename = Path.rename

    def raiseExdevForSource(path: Path, target: Path):
        if path == source:
            raise OSError(errno.EXDEV, "cross-device link")
        return originalRename(path, target)

    with patch.object(Path, "rename", autospec=True, side_effect=raiseExdevForSource):
        filesystem.move(source, destination)

    assert not source.exists()
    assert destination.read_bytes() == b"video"


def testCrossFilesystemVerificationFailureKeepsSource(tmp_path: Path):
    source = tmp_path / "source.mp4"
    destination = tmp_path / "archive" / "source.mp4"
    source.write_bytes(b"video")
    filesystem = FilesystemOperations(dryRun=False)
    originalRename = Path.rename

    def raiseExdevForSource(path: Path, target: Path):
        if path == source:
            raise OSError(errno.EXDEV, "cross-device link")
        return originalRename(path, target)

    with patch.object(Path, "rename", autospec=True, side_effect=raiseExdevForSource):
        with patch.object(
            filesystem, "_verifyFiles", side_effect=OSError("verification failed")
        ):
            with pytest.raises(OSError, match="verification failed"):
                filesystem.move(source, destination)

    assert source.exists()
    assert not destination.exists()


def testQuarantineMovesContentToRecoverableLocation(tmp_path: Path):
    source = tmp_path / "downloads" / "obsolete.torrent"
    source.parent.mkdir()
    source.write_bytes(b"torrent")
    filesystem = FilesystemOperations(dryRun=False)

    quarantinePath = filesystem.quarantine(source, sourceRoot=source.parent)

    assert not source.exists()
    assert quarantinePath.read_bytes() == b"torrent"
    assert ".organiseMyVideo-quarantine" in quarantinePath.parts
    assert filesystem.operations[0].action == "quarantine"
