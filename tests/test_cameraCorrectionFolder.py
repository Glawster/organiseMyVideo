"""Folder evidence through real metadata, correction, catalogue and CLI execution."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cameraFixtures import jpegWithExif, videoWithCreationWrite

from organiseMyVideo import constants
from organiseMyVideo.cameraCorrectionExecution import cameraCorrectionExecute
from organiseMyVideo.cameraCorrectionFolder import cameraCorrectionFolderPlan
from organiseMyVideo.cameraCorrectionStore import correctionTimestampRead
from organiseMyVideo.cameraImport import cameraImportHistory
from organiseMyVideo.cameraMetadata import metadataCaptureRead
from organiseMyVideo.cameraPlan import CameraImportPlanner
from organiseMyVideo.filesystemOperations import FilesystemOperations


@pytest.fixture
def folder(tmp_path):
    source = tmp_path / "incorrect-folder"
    source.mkdir()
    root = tmp_path / "GoPro"
    root.mkdir()
    for index, elapsed in enumerate((timedelta(), timedelta(days=2, minutes=30))):
        (source / f"G001000{index}.JPG").write_bytes(
            jpegWithExif(datetime(2015, 1, 1, 12, 34, 20) + elapsed)
        )
    return (
        source,
        root,
        tmp_path / "state" / "catalogue.sqlite",
        tmp_path / "state" / "cameraImports",
    )


def folderPlan(folder, **kwargs):
    source, root, database, _ = folder
    return cameraCorrectionFolderPlan(
        source,
        archiveRoot=root,
        referenceFile=kwargs.pop("referenceFile", "G0010000.JPG"),
        actualAt=kwargs.pop("actualAt", datetime(2018, 8, 25, 19)),
        reason="Known event date",
        databasePath=database,
        **kwargs,
    )


def folderExecute(folder, plan, **kwargs):
    return cameraCorrectionExecute(
        plan,
        databasePath=folder[2],
        manifestDirectory=folder[3],
        dryRun=False,
        **kwargs,
    )


def folderSnapshot(path):
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in path.rglob("*")
        if item.is_file()
    }


def testFolderPreviewAndExecutionWithoutInventedImports(folder, tmp_path):
    source, root, database, manifests = folder
    before = folderSnapshot(tmp_path)
    events = []
    plan = folderPlan(folder, progressCallback=lambda *args: events.append(args))
    assert not plan.blocked
    assert folderSnapshot(tmp_path) == before
    assert events[0][0] == 0 and events[-1][0] == 2
    assert plan.payload["importId"] is None
    assert plan.payload["importManifest"] is None
    assert plan.payload["scopeType"] == "folder"
    assert [asset["correctedCaptureAt"] for asset in plan.payload["assets"]] == [
        "2018-08-25T19:00:00",
        "2018-08-27T19:30:00",
    ]
    cameraCorrectionExecute(plan, databasePath=database, manifestDirectory=manifests)
    assert folderSnapshot(tmp_path) == before

    completed = folderExecute(folder, plan)
    assert all(asset["outcome"] == "applied" for asset in completed["assets"])
    assert source.is_dir() and not any(source.iterdir())
    for asset in completed["assets"]:
        path = Path(asset["destinationPath"])
        assert (
            path.read_bytes()
            != before[str(Path(asset["sourcePath"]).relative_to(tmp_path))]
        )
        assert metadataCaptureRead(path).isoformat() == asset["correctedCaptureAt"]
        assert (
            correctionTimestampRead(path, databasePath=database)["correctedCaptureAt"]
            == asset["correctedCaptureAt"]
        )
    assert cameraImportHistory(manifests) == ()
    manifest = json.loads(Path(completed["manifestPath"]).read_text())
    assert manifest["scopeType"] == "folder" and manifest["importId"] is None
    assert len(manifest["folderEvidence"]) == 2
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT count(*) FROM cardInventory").fetchone()[0] == 0
        )
    planner = CameraImportPlanner(
        goproDestination=root,
        droneDestination=root,
        dashcamDestination=root,
        databasePath=database,
    )
    assert all(
        op.asset.captureAt.year == 2018 for op in planner.importPlan(root).operations
    )
    repeatedBefore = folderSnapshot(tmp_path)
    folderExecute(folder, folderPlan(folder))
    assert folderSnapshot(tmp_path) == repeatedBefore


def testRequestedMp4CliAndCompanionProvenance(folder, monkeypatch, capsys):
    from organiseMyVideo.__main__ import main

    source, root, database, manifests = folder
    for path in source.iterdir():
        path.unlink()
    videoWithCreationWrite(source / "GH010001.MP4", datetime(2015, 1, 1, 12, 34, 20))
    (source / "GH010001.THM").write_bytes(
        jpegWithExif(datetime(2015, 1, 1, 12, 34, 21))
    )
    (source / "GH010001.SRT").write_text("telemetry")
    (source / "notes.txt").write_text("retain")
    monkeypatch.setattr(constants, "MEDIA_CATALOGUE_DATABASE", database)
    monkeypatch.setattr(
        constants, "applicationStateDirectory", lambda: manifests.parent
    )
    args = [
        "camera",
        "correct-time",
        "-s",
        str(source),
        "-r",
        str(root),
        "-R",
        "GH010001.MP4",
        "-a",
        "2018-08-25T19:00:00",
        "--reason",
        "Known event date",
    ]
    assert main(args) == 0
    output = capsys.readouterr().out
    assert (
        "Folder scope:" in output
        and "Affected files: 3" in output
        and "notes.txt" in output
    )
    assert not database.exists()
    assert main(args + ["-y"]) == 0
    assert (source / "notes.txt").exists()
    records = json.loads(next(manifests.glob("camera-correction-*.json")).read_text())
    thumbnail = next(
        asset for asset in records["assets"] if asset["relativePath"].endswith("THM")
    )
    assert thumbnail["dateSource"] == "companion"
    assert thumbnail["timestampEvidencePath"] == "GH010001.MP4"
    assert thumbnail["observedCaptureAt"] == "2015-01-01T12:34:21"
    assert thumbnail["rawCaptureAt"] == "2015-01-01T12:34:20"
    assert len(list((root / "2018/08/25").iterdir())) == 3
    assert main(args + ["-y"]) == 0


def testNestedSubsetIncludesCompanionsAndLeavesOthers(folder):
    source, root, _, _ = folder
    nested = source / "session"
    nested.mkdir()
    original = source / "G0010000.JPG"
    original.rename(nested / original.name)
    (nested / "G0010000.XML").write_text("sidecar")
    (nested / "G0010000.PNG").write_bytes(b"artwork")
    plan = folderPlan(
        folder,
        referenceFile="session/G0010000.JPG",
        selectedFiles=("session/G0010000.JPG",),
    )
    assert not plan.blocked and len(plan.payload["assets"]) == 3
    folderExecute(folder, plan)
    assert not nested.exists()
    assert (source / "G0010001.JPG").exists()
    assert (root / "2018/08/25/G0010000.XML").exists()
    assert (root / "2018/08/25/G0010000.PNG").read_bytes() == b"artwork"


@pytest.mark.parametrize("inside", [False, True])
def testNegativeOffsetAndSourceBoundary(folder, inside):
    source, root, database, manifests = folder
    if inside:
        newSource = root / "incorrect"
        source.rename(newSource)
        folder = newSource, root, database, manifests
    plan = folderPlan(folder, actualAt=datetime(2014, 12, 31, 23, 59))
    assert not plan.blocked
    folderExecute(folder, plan)
    assert (root / "2014/12/31/G0010000.JPG").exists()
    assert folder[0].is_dir()


@pytest.mark.parametrize("identical", [True, False])
def testFolderDestinationDuplicateOrConflict(folder, identical):
    plan = folderPlan(folder)
    asset = plan.payload["assets"][0]
    destination = Path(asset["destinationPath"])
    destination.parent.mkdir(parents=True)
    destination.write_bytes(
        Path(asset["sourcePath"]).read_bytes() if identical else b"other content"
    )
    plan = folderPlan(folder)
    assert plan.blocked is not identical
    folderExecute(folder, plan)
    assert Path(asset["sourcePath"]).exists() is not identical


def testNewFilesDoNotInheritSavedScope(folder):
    source, _, _, _ = folder
    plan = folderPlan(folder)
    folderExecute(folder, plan)
    new = source / "G0020000.JPG"
    new.write_bytes(jpegWithExif(datetime(2020, 1, 1)))
    with pytest.raises(ValueError, match="reference and selected files must exist"):
        folderPlan(folder)
    fresh = folderPlan(
        folder,
        referenceFile=new.name,
        selectedFiles=(new.name,),
        actualAt=datetime(2020, 1, 2),
    )
    assert not fresh.blocked
    assert fresh.payload["assets"][0]["rawCaptureAt"] == "2020-01-01T00:00:00"


def testNewFileAfterPreviewBlocksBeforeMutation(folder):
    plan = folderPlan(folder)
    (folder[0] / "new.JPG").write_bytes(jpegWithExif(datetime(2015, 1, 1)))
    with pytest.raises(ValueError, match="new files"):
        folderExecute(folder, plan)
    assert not folder[2].exists()


@pytest.mark.parametrize("when", ["copy", "remove"])
def testInterruptedFolderCorrectionResumesFrozenEvidence(folder, monkeypatch, when):
    plan = folderPlan(folder)
    method = "copyFile" if when == "copy" else "removeFile"
    original = getattr(FilesystemOperations, method)
    calls = 0

    def interrupt(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FilesystemOperations, method, interrupt)
    with pytest.raises(KeyboardInterrupt):
        folderExecute(folder, plan)
    for asset in plan.payload["assets"]:
        assert (
            Path(asset["sourcePath"]).exists()
            or Path(asset["destinationPath"]).exists()
        )
    monkeypatch.setattr(FilesystemOperations, method, original)
    retry = folderPlan(folder)
    assert retry.payload["ruleId"] == plan.payload["ruleId"]
    result = folderExecute(folder, retry)
    assert all(asset["outcome"] == "applied" for asset in result["assets"])
    assert len(result["attempts"]) == 2


def testOverlappingChangedRulesBlockedIncludingNestedSource(folder, monkeypatch):
    plan = folderPlan(folder)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(FilesystemOperations, "copyFile", fail)
    with pytest.raises(OSError):
        folderExecute(folder, plan)
    assert folderPlan(folder, actualAt=datetime(2019, 1, 1)).blocked
    assert folderPlan(folder, selectedFiles=("G0010000.JPG",)).blocked


@pytest.mark.parametrize("value", ["../escape.JPG", "/absolute.JPG", "missing.JPG", ""])
def testInvalidReferenceRejected(folder, value):
    with pytest.raises(ValueError):
        folderPlan(folder, referenceFile=value)


def testMissingTimestampAndOrphanCompanionBlock(folder):
    (folder[0] / "G0010001.JPG").write_bytes(b"no metadata")
    assert folderPlan(folder).blocked
    (folder[0] / "orphan.SRT").write_text("orphan")
    plan = folderPlan(folder)
    assert plan.blocked
    assert any(
        "unambiguous" in asset.get("error", "") for asset in plan.payload["assets"]
    )


def testUnsafeSourcePathsAndDestinationOverlapRejected(folder):
    source, root, database, manifests = folder
    link = source / "link.JPG"
    link.symlink_to(source / "G0010000.JPG")
    with pytest.raises(ValueError, match="symlink"):
        folderPlan(folder)
    link.unlink()
    for overlappingRoot in (source, source / "output"):
        overlappingRoot.mkdir(exist_ok=True)
        with pytest.raises(ValueError, match="descendant"):
            folderPlan((source, overlappingRoot, database, manifests))


def testScopeSelectorsMutuallyExclusiveAndRequired():
    from organiseMyVideo.cameraCli import _cameraParserBuild

    common = [
        "correct-time",
        "--root",
        "/archive",
        "--reference",
        "a.JPG",
        "--actual",
        "2018-08-25T19:00:00",
        "--reason",
        "event",
    ]
    for options in ([], ["--source", "/source", "--import-manifest", "/manifest"]):
        with pytest.raises(SystemExit) as error:
            _cameraParserBuild().parse_args(common + options)
        assert error.value.code == 2


def testChangedOriginalAfterPreviewRetained(folder):
    plan = folderPlan(folder)
    path = folder[0] / "G0010001.JPG"
    path.write_bytes(b"replacement")
    with pytest.raises(ValueError, match="SHA-256"):
        folderExecute(folder, plan)
    assert not folder[2].exists()
    assert path.read_bytes() == b"replacement"


def testChangingMetadataDuringSnapshotIsBlocked(folder, monkeypatch):
    from organiseMyVideo import cameraCorrectionFolder as module

    original = module.metadataCaptureDetailsRead

    def change(path):
        result = original(path)
        if path.name == "G0010001.JPG":
            path.write_bytes(b"changed after metadata read")
        return result

    monkeypatch.setattr(module, "metadataCaptureDetailsRead", change)
    plan = folderPlan(folder)
    assert plan.blocked
    assert "changed while reading" in plan.payload["assets"][1]["error"]


def testUnreadableMediaAndDirectoryReportedWithoutPartialScope(folder, monkeypatch):
    from organiseMyVideo import cameraCorrectionFolder as module

    original = module.mediaHashCalculate

    def failFile(path, **kwargs):
        if path.name == "G0010001.JPG":
            raise PermissionError("unreadable original")
        return original(path, **kwargs)

    monkeypatch.setattr(module, "mediaHashCalculate", failFile)
    plan = folderPlan(folder)
    assert plan.blocked and "unreadable" in plan.payload["assets"][1]["error"]

    def failWalk(path, *, onerror, **kwargs):
        onerror(PermissionError("unreadable directory"))
        return []

    monkeypatch.setattr(module.os, "walk", failWalk)
    with pytest.raises(PermissionError, match="directory"):
        folderPlan(folder)


def testNonRegularMediaNeverOpened(folder):
    import os

    os.mkfifo(folder[0] / "pipe.MP4")
    plan = folderPlan(folder)
    assert plan.blocked
    assert any(
        "regular file" in asset.get("error", "") for asset in plan.payload["assets"]
    )


def testSourceLockRejectsConcurrentDestinationRoots(folder):
    import fcntl
    import os

    plan = folderPlan(folder)
    descriptor = os.open(folder[0], os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="another correction"):
            folderExecute(folder, plan)
    finally:
        os.close(descriptor)
    assert not folder[2].exists()


def testFilenameTimestampWithoutEmbeddedMetadata(folder):
    source = folder[0]
    for path in source.iterdir():
        path.unlink()
    name = "20150101_123420.JPG"
    from cameraFixtures import jpegWithoutExif

    (source / name).write_bytes(jpegWithoutExif())
    plan = folderPlan(folder, referenceFile=name)
    assert not plan.blocked
    assert plan.payload["assets"][0]["dateSource"] == "filename"
    folderExecute(folder, plan)


def testCompanionCannotBeReferenceAndMissingSubsetFails(folder):
    (folder[0] / "G0010000.SRT").write_text("companion")
    with pytest.raises(ValueError, match="not a companion"):
        folderPlan(folder, referenceFile="G0010000.SRT")
    with pytest.raises(ValueError, match="must exist"):
        folderPlan(folder, selectedFiles=("G0010000.JPG", "absent.JPG"))


def testSameNameCollisionsAcrossNestedFoldersBlock(folder):
    source = folder[0]
    nested = source / "another"
    nested.mkdir()
    (nested / "G0010000.JPG").write_bytes(
        (source / "G0010000.JPG").read_bytes() + b"different"
    )
    plan = folderPlan(folder)
    assert plan.blocked
    assert any("collide" in asset.get("error", "") for asset in plan.payload["assets"])


def testReusedSourceFilenameDoesNotReceiveOldCorrection(folder):
    plan = folderPlan(folder)
    folderExecute(folder, plan)
    replacement = folder[0] / "G0010000.JPG"
    replacement.write_bytes(jpegWithExif(datetime(2024, 1, 1)))
    assert folderPlan(folder).blocked
    assert correctionTimestampRead(replacement, databasePath=folder[2]) is None


def testGoproQuickTimeClockIsNaiveCaptureEvidence(folder):
    import os

    source, root, database, _ = folder
    for path in source.iterdir():
        path.unlink()
    video = source / "GOPR4150.MP4"
    videoWithCreationWrite(video, datetime(2015, 1, 4, 7, 42, 46))
    # Deliberately different filesystem evidence must not determine correction.
    os.utime(video, (1420353781, 1420353781))
    before = video.read_bytes()
    plan = folderPlan(
        folder, referenceFile=video.name, actualAt=datetime(2018, 8, 22, 18)
    )
    assert not plan.blocked
    asset = plan.payload["assets"][0]
    assert asset["rawCaptureAt"] == "2015-01-04T07:42:46"
    assert asset["correctedCaptureAt"] == "2018-08-22T18:00:00"
    assert asset["timestampEvidence"]["source"] == "quicktime.mvhd.creation_time"
    assert asset["timestampEvidence"]["backendRaw"].endswith("Z")
    assert video.read_bytes() == before
    assert not database.exists()


def testTimezoneMismatchReportsBothReferenceValues(folder):
    from datetime import timezone

    with pytest.raises(ValueError) as error:
        folderPlan(folder, actualAt=datetime(2018, 8, 22, 18, tzinfo=timezone.utc))
    message = str(error.value)
    assert "same timezone/UTC offset" in message
    assert "recorded reference" in message
    assert "naive; no UTC offset" in message
    assert "2018-08-22T18:00:00+00:00 (aware; UTC offset 0:00:00)" in message


@pytest.mark.parametrize("short", [False, True])
def testCorrectionOptionNames(short):
    from organiseMyVideo.cameraCli import _cameraParserBuild

    options = (
        ["-s", "-r", "-R", "-a", "-f"]
        if short
        else ["--source", "--root", "--reference", "--actual", "--file"]
    )
    source, root, reference, actual, selected = options
    args = _cameraParserBuild().parse_args(
        [
            "correct-time",
            source,
            "/source",
            root,
            "/archive",
            reference,
            "GOPR4150.MP4",
            actual,
            "2018-08-22T18:00:00",
            selected,
            "GOPR4150.MP4",
            selected,
            "other.JPG",
            "--reason",
            "event",
        ]
    )
    assert args.source == Path("/source")
    assert args.root == Path("/archive")
    assert args.reference_file == "GOPR4150.MP4"
    assert args.actual_at.isoformat() == "2018-08-22T18:00:00"
    assert args.file == ["GOPR4150.MP4", "other.JPG"]
    assert args.reason == "event"
    assert not args.confirm


@pytest.mark.parametrize("obsolete", ["--reference-file", "--actual-at"])
def testCorrectionObsoleteOptionsRejected(obsolete, capsys):
    from organiseMyVideo.cameraCli import _cameraParserBuild

    with pytest.raises(SystemExit) as error:
        _cameraParserBuild().parse_args(
            [
                "correct-time",
                "-s",
                "/source",
                "-r",
                "/archive",
                "-R",
                "a.JPG",
                "-a",
                "2018-08-22T18:00:00",
                "--reason",
                "event",
                obsolete,
                "unused",
            ]
        )
    assert error.value.code == 2
    assert f"unrecognized arguments: {obsolete}" in capsys.readouterr().err


def testCorrectionReasonRequired():
    from organiseMyVideo.cameraCli import _cameraParserBuild

    with pytest.raises(SystemExit) as error:
        _cameraParserBuild().parse_args(
            [
                "correct-time",
                "-s",
                "/source",
                "-r",
                "/archive",
                "-R",
                "a.JPG",
                "-a",
                "2018-08-22T18:00:00",
            ]
        )
    assert error.value.code == 2


def testSuccessiveSamePathCorrectionsPreserveAuditAndUseCurrentEvidence(folder):
    from organiseMyVideo.cameraCorrectionStore import (
        correctionJournalRead,
        correctionJournalWrite,
    )

    first = folderExecute(folder, folderPlan(folder, selectedFiles=("G0010000.JPG",)))
    oldJournal = correctionJournalRead(folder[2])[0]
    oldManifest = Path(first["manifestPath"]).read_bytes()
    firstAsset = first["assets"][0]
    current = Path(firstAsset["destinationPath"])
    nextFolder = (current.parent, *folder[1:])
    beforeBytes = current.read_bytes()
    beforeMtime = current.stat().st_mtime_ns
    plan = folderPlan(
        nextFolder, actualAt=datetime.fromisoformat("2018-08-25T20:00:00")
    )
    assert not plan.blocked
    assert plan.payload["referenceRecordedAt"] == "2018-08-25T19:00:00"
    assert plan.payload["offsetSeconds"] == "3600"
    assert plan.payload["predecessorRuleIds"] == [first["ruleId"]]
    assert current.read_bytes() == beforeBytes
    second = folderExecute(nextFolder, plan)
    assert second["ruleId"] != first["ruleId"]
    asset = second["assets"][0]
    assert asset["sourcePath"] == asset["destinationPath"]
    assert asset["originalSha256"] == firstAsset["destinationSha256"]
    assert asset["originalMetadata"] == firstAsset["correctedMetadata"]
    assert asset["filesystemBefore"]["mtimeNs"] == beforeMtime
    assert metadataCaptureRead(current).isoformat() == "2018-08-25T20:00:00"
    assert (
        correctionTimestampRead(current, databasePath=folder[2])["ruleId"]
        == second["ruleId"]
    )
    assert correctionJournalRead(folder[2])[0] == oldJournal
    assert Path(first["manifestPath"]).read_bytes() == oldManifest
    with pytest.raises(ValueError, match="immutable"):
        correctionJournalWrite(folder[2], dict(oldJournal, reason="rewritten"))
    # An exact repeat verifies current output and leaves both audit records untouched.
    snapshot = folderSnapshot(folder[2].parent.parent)
    folderExecute(
        nextFolder,
        folderPlan(nextFolder, actualAt=datetime.fromisoformat("2018-08-25T20:00:00")),
    )
    assert folderSnapshot(folder[2].parent.parent) == snapshot


def testCompletedCorrectionReleasesSourceForFreshMedia(folder):
    first = folderExecute(folder, folderPlan(folder))
    replacement = folder[0] / "G0010000.JPG"
    replacement.write_bytes(jpegWithExif(datetime.fromisoformat("2020-01-01T12:00:00")))
    plan = folderPlan(folder, actualAt=datetime.fromisoformat("2021-01-02T13:00:00"))
    assert not plan.blocked
    assert plan.payload["referenceRecordedAt"] == "2020-01-01T12:00:00"
    assert not plan.payload["predecessorRuleIds"]
    result = folderExecute(folder, plan)
    assert result["ruleId"] != first["ruleId"]
    assert (
        metadataCaptureRead(Path(result["assets"][0]["destinationPath"])).year == 2021
    )


def testSecondCorrectionFailureResumesWithoutChangingFirstAudit(folder, monkeypatch):
    from organiseMyVideo.cameraCorrectionStore import correctionJournalRead

    first = folderExecute(folder, folderPlan(folder, selectedFiles=("G0010000.JPG",)))
    current = Path(first["assets"][0]["destinationPath"])
    nextFolder = (current.parent, *folder[1:])
    actual = datetime.fromisoformat("2019-01-01T12:00:00")
    second = folderPlan(nextFolder, actualAt=actual)
    saved = correctionJournalRead(folder[2])[0]
    copy = FilesystemOperations.copyFile

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(FilesystemOperations, "copyFile", fail)
    with pytest.raises(OSError, match="disk full"):
        folderExecute(nextFolder, second)
    assert current.exists()
    monkeypatch.setattr(FilesystemOperations, "copyFile", copy)
    retry = folderPlan(nextFolder, actualAt=actual)
    assert retry.payload["ruleId"] == second.payload["ruleId"]
    result = folderExecute(nextFolder, retry)
    assert len(result["attempts"]) == 2
    assert (
        metadataCaptureRead(Path(result["assets"][0]["destinationPath"])).isoformat()
        == actual.isoformat()
    )
    assert correctionJournalRead(folder[2])[0] == saved


def testPreservedMtimeChangedAfterPreviewBlocks(folder):
    import os

    plan = folderPlan(folder)
    source = Path(plan.payload["assets"][0]["sourcePath"])
    os.utime(
        source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1000000000)
    )
    with pytest.raises(ValueError, match="mtime changed"):
        folderExecute(folder, plan)
    assert not folder[2].exists()


def testCompletedOperationInvalidatesAnOlderIndependentPreview(folder):
    stale = folderPlan(folder)
    folderExecute(folder, folderPlan(folder))
    with pytest.raises(ValueError, match="scope changed"):
        folderExecute(folder, stale)


def testCleanupFailureResumesBeforeSealingAudit(folder, monkeypatch):
    from organiseMyVideo.cameraCorrectionStore import correctionJournalRead

    plan = folderPlan(folder)
    remove = FilesystemOperations.removeFile

    def failWork(self, path, **kwargs):
        if kwargs.get("stateKind") == "camera-correction-work":
            raise OSError("cleanup unavailable")
        return remove(self, path, **kwargs)

    monkeypatch.setattr(FilesystemOperations, "removeFile", failWork)
    with pytest.raises(OSError, match="cleanup unavailable"):
        folderExecute(folder, plan)
    assert "completedAt" not in correctionJournalRead(folder[2])[0]
    monkeypatch.setattr(FilesystemOperations, "removeFile", remove)
    result = folderExecute(folder, folderPlan(folder))
    assert result["completedAt"]
    assert len(result["attempts"]) == 2
