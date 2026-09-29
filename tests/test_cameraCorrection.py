"""REQ-024: real metadata/import/catalogue/relocation paths and failure evidence."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cameraFixtures import jpegWithExif, videoWithCreationWrite

from organiseMyVideo import constants
from organiseMyVideo.cameraCorrection import cameraCorrectionPlan
from organiseMyVideo.cameraCorrectionExecution import cameraCorrectionExecute
from organiseMyVideo.cameraCorrectionStore import correctionTimestampRead
from organiseMyVideo.cameraImport import CameraImporter
from organiseMyVideo.cameraMetadata import metadataCaptureRead
from organiseMyVideo.cameraPlan import CameraImportPlanner
from organiseMyVideo.filesystemOperations import FilesystemOperations


@pytest.fixture
def imported(tmp_path):
    card = tmp_path / "card" / "DCIM" / "100GOPRO"
    card.mkdir(parents=True)
    raw = datetime(2015, 1, 1, 12, 34, 20)
    for index, elapsed in enumerate((timedelta(), timedelta(days=2, seconds=1800))):
        (card / f"G001000{index}.JPG").write_bytes(jpegWithExif(raw + elapsed))
    root = tmp_path / "archive"
    database = tmp_path / "state" / "mediaCatalogue.sqlite"
    planner = CameraImportPlanner(
        goproDestination=root,
        droneDestination=root,
        dashcamDestination=root,
        databasePath=database,
    )
    result = CameraImporter(
        planner=planner, manifestDirectory=tmp_path / "imports", dryRun=False
    ).importMedia(card, cardId=2)
    return result, root, database, planner


def correctionPlan(imported, **kwargs):
    result, root, database, _ = imported
    return cameraCorrectionPlan(
        result.manifestPath,
        archiveRoot=root,
        referenceFile="G0010000.JPG",
        actualAt=kwargs.pop("actualAt", datetime(2018, 8, 25, 19)),
        reason="trusted event photograph",
        databasePath=database,
        **kwargs,
    )


def correctionExecute(imported, plan, **kwargs):
    result, _, database, _ = imported
    return cameraCorrectionExecute(
        plan,
        databasePath=database,
        manifestDirectory=result.manifestPath.parent,
        dryRun=False,
        **kwargs,
    )


def treeSnapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def testCardTwoPreviewAndConfirmedProductionPath(imported, tmp_path):
    result, root, database, planner = imported
    before = treeSnapshot(tmp_path)
    events = []
    plan = correctionPlan(
        imported, progressCallback=lambda *event: events.append(event)
    )
    assert not plan.blocked
    assert treeSnapshot(tmp_path) == before
    assert events[0][0] == 0 and events[-1][0] == 2
    assets = plan.payload["assets"]
    assert assets[0]["rawCaptureAt"] == "2015-01-01T12:34:20"
    assert assets[0]["correctedCaptureAt"] == "2018-08-25T19:00:00"
    assert assets[1]["correctedCaptureAt"] == "2018-08-27T19:30:00"
    assert Path(assets[0]["destinationPath"]) == root / "2018/08/25/G0010000.JPG"
    assert (
        cameraCorrectionExecute(plan, databasePath=database, manifestDirectory=root)[
            "assets"
        ]
        == assets
    )
    assert treeSnapshot(tmp_path) == before

    completed = correctionExecute(imported, plan)
    assert all(asset["outcome"] == "applied" for asset in completed["assets"])
    assert not (root / "2015").exists()
    assert (
        json.loads(Path(completed["manifestPath"]).read_text())["ruleId"]
        == plan.payload["ruleId"]
    )
    for asset in completed["assets"]:
        destination = Path(asset["destinationPath"])
        assert (
            metadataCaptureRead(destination).isoformat() == asset["correctedCaptureAt"]
        )
        stored = correctionTimestampRead(destination, databasePath=database)
        assert stored["rawCaptureAt"] == asset["rawCaptureAt"]
        assert stored["correctedCaptureAt"] == asset["correctedCaptureAt"]
    assert (
        result.manifestPath.read_bytes()
        == before[str(result.manifestPath.relative_to(tmp_path))]
    )

    # Organising the corrected archive must not send it back to 2015.
    replanned = planner.importPlan(root)
    assert len(replanned.operations) == 2
    assert all(op.asset.captureAt.year == 2018 for op in replanned.operations)
    assert all(op.asset.rawCaptureAt.year == 2015 for op in replanned.operations)
    assert all(op.outcome == "alreadyPresent" for op in replanned.operations)
    beforeRepeat = treeSnapshot(tmp_path)
    correctionExecute(imported, correctionPlan(imported))
    assert treeSnapshot(tmp_path) == beforeRepeat


@pytest.mark.parametrize(
    "actual", [datetime(2014, 12, 31, 23, 59), datetime(2016, 2, 28, 23, 59)]
)
def testNegativeAndLeapRollover(imported, actual):
    plan = correctionPlan(imported, actualAt=actual)
    corrected = [
        datetime.fromisoformat(asset["correctedCaptureAt"])
        for asset in plan.payload["assets"]
    ]
    assert corrected == [actual, actual + timedelta(days=2, minutes=30)]
    correctionExecute(imported, plan)


@pytest.mark.parametrize("same", [True, False])
def testExistingDestinationUsesContentEvidence(imported, tmp_path, same):
    plan = correctionPlan(imported)
    asset = plan.payload["assets"][0]
    destination = Path(asset["destinationPath"])
    destination.parent.mkdir(parents=True)
    destination.write_bytes(
        Path(asset["sourcePath"]).read_bytes() if same else b"different original"
    )
    before = treeSnapshot(tmp_path)
    plan = correctionPlan(imported)
    assert plan.blocked is not same
    if same:
        assert plan.payload["assets"][0]["outcome"] == "alreadyPresent"
        result = correctionExecute(imported, plan)
        assert result["assets"][0]["destinationExisted"]
    else:
        correctionExecute(imported, plan)
        assert treeSnapshot(tmp_path) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("captureAt", None),
        ("captureAt", "invalid"),
        ("dateSource", "filesystem"),
        ("destinationDigest", "bad"),
    ],
)
def testUnusableNonAnchorBlocksWholeScope(imported, field, value):
    result, _, database, _ = imported
    payload = json.loads(result.manifestPath.read_text())
    payload["assets"][1][field] = value
    result.manifestPath.write_text(json.dumps(payload))
    plan = correctionPlan(imported)
    assert plan.blocked
    correctionExecute(imported, plan)
    assert not database.exists()


def testMissingAnchorAndMixedTimezoneRejected(imported):
    result, root, database, _ = imported
    with pytest.raises(ValueError, match="reference"):
        cameraCorrectionPlan(
            result.manifestPath,
            archiveRoot=root,
            referenceFile="missing.JPG",
            actualAt=datetime(2018, 8, 25),
            reason="event",
            databasePath=database,
        )
    with pytest.raises(ValueError, match="timezone"):
        correctionPlan(
            imported, actualAt=datetime.fromisoformat("2018-08-25T19:00:00+01:00")
        )


def testChangedFileAfterPreviewRejectedBeforeStateWrite(imported):
    plan = correctionPlan(imported)
    Path(plan.payload["assets"][0]["sourcePath"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        correctionExecute(imported, plan)
    assert not imported[2].exists()


def testPartialCopyFailureRetainsSourcesAndCanResume(imported, monkeypatch):
    plan = correctionPlan(imported)
    original = FilesystemOperations.copyFile
    calls = 0

    def failSecond(self, source, destination, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        return original(self, source, destination, **kwargs)

    monkeypatch.setattr(FilesystemOperations, "copyFile", failSecond)
    with pytest.raises(OSError, match="disk full"):
        correctionExecute(imported, plan)
    assert all(Path(asset["sourcePath"]).exists() for asset in plan.payload["assets"])
    assert (
        correctionTimestampRead(
            Path(plan.payload["assets"][0]["destinationPath"]), databasePath=imported[2]
        )
        is None
    )
    monkeypatch.setattr(FilesystemOperations, "copyFile", original)
    completed = correctionExecute(imported, correctionPlan(imported))
    assert all(asset["outcome"] == "applied" for asset in completed["assets"])


def testInterruptedRemovalHasDurableRecoveryEvidence(imported, monkeypatch):
    plan = correctionPlan(imported)
    original = FilesystemOperations.removeFile
    calls = 0

    def interrupt(self, path, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt()
        return original(self, path, **kwargs)

    monkeypatch.setattr(FilesystemOperations, "removeFile", interrupt)
    with pytest.raises(KeyboardInterrupt):
        correctionExecute(imported, plan)
    for asset in plan.payload["assets"]:
        assert Path(asset["destinationPath"]).is_file()
    monkeypatch.setattr(FilesystemOperations, "removeFile", original)
    assert not correctionPlan(imported).blocked
    correctionExecute(imported, correctionPlan(imported))


def testCardReuseAndChangedRuleIsolation(imported):
    result, _, _, planner = imported
    correctionExecute(imported, correctionPlan(imported))
    assert not correctionPlan(imported, actualAt=datetime(2019, 1, 1)).blocked
    # Raw card media stays raw: even identical content at a different source path
    # is not corrected just because cardId or filename matches an earlier import.
    fresh = planner.importPlan(result.plan.sourcePath)
    assert all(op.asset.captureAt.year == 2015 for op in fresh.operations)


def testCatalogueUpdatePreservesInventoryAndRawEvidence(imported):
    from organiseMyVideo.mediaCatalogue import catalogueSchemaApply

    plan = correctionPlan(imported)
    database = imported[2]
    database.parent.mkdir(parents=True)
    asset = plan.payload["assets"][0]
    with sqlite3.connect(database) as connection:
        catalogueSchemaApply(connection)
        connection.execute(
            "INSERT INTO homeVideoItem(kind,relativePath,filePath,captureAt,dateSource,sizeBytes,scannedAt) VALUES(?,?,?,?,?,?,?)",
            (
                "gopro",
                "old",
                asset["sourcePath"],
                asset["rawCaptureAt"],
                "metadata",
                1,
                "today",
            ),
        )
    correctionExecute(imported, plan)
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT filePath,captureAt,dateSource FROM homeVideoItem"
        ).fetchone()
    assert row == (asset["destinationPath"], asset["correctedCaptureAt"], "correction")


def testCliPreviewConfirmationHelpAndInvalidAnchor(
    imported, monkeypatch, capsys, tmp_path
):
    from organiseMyVideo.__main__ import main

    result, root, database, _ = imported
    monkeypatch.setattr(constants, "MEDIA_CATALOGUE_DATABASE", database)
    monkeypatch.setattr(
        constants, "applicationStateDirectory", lambda: tmp_path / "state"
    )
    args = [
        "camera",
        "correct-time",
        "--import-manifest",
        str(result.manifestPath),
        "--root",
        str(root),
        "--reference",
        "G0010000.JPG",
        "--actual",
        "2018-08-25T19:00:00",
        "--reason",
        "event photograph",
    ]
    assert main(args) == 0
    output = capsys.readouterr().out
    assert all(
        word in output
        for word in (
            "Original:",
            "Corrected:",
            "Offset:",
            "Affected files: 2",
            "Preview only",
        )
    )
    assert not database.exists()
    assert main(args + ["-y"]) == 0
    assert database.exists()
    with pytest.raises(SystemExit) as stopped:
        main(["camera", "correct-time", "-h"])
    assert stopped.value.code == 0
    helpText = " ".join(capsys.readouterr().out.split())
    assert "-R, --reference FILE" in helpText.replace("-R FILE,", "-R,")
    assert "-a, --actual DATETIME" in helpText.replace("-a DATETIME,", "-a,")
    assert "file whose recorded capture time provides the correction anchor" in helpText
    assert "actual capture date/time of the reference file" in helpText
    assert "--reference-file" not in helpText
    assert "--actual-at" not in helpText
    args[args.index("2018-08-25T19:00:00")] = "yesterday"
    with pytest.raises(SystemExit):
        main(args)


def testActualGoproMp4MetadataCorrected(tmp_path):
    card = tmp_path / "card" / "DCIM" / "100GOPRO"
    card.mkdir(parents=True)
    source = card / "GH010001.MP4"
    videoWithCreationWrite(source, datetime(2015, 1, 1, 12, 34, 20))
    root = tmp_path / "archive"
    database = tmp_path / "catalogue.sqlite"
    planner = CameraImportPlanner(
        goproDestination=root,
        droneDestination=root,
        dashcamDestination=root,
        databasePath=database,
    )
    imported = CameraImporter(
        planner=planner, manifestDirectory=tmp_path / "imports", dryRun=False
    ).importMedia(card, cardId=2)
    actual = datetime.fromisoformat("2018-08-25T19:00:00")
    plan = cameraCorrectionPlan(
        imported.manifestPath,
        archiveRoot=root,
        referenceFile=source.name,
        actualAt=actual,
        reason="event evidence",
        databasePath=database,
    )
    assert not plan.blocked
    completed = cameraCorrectionExecute(
        plan,
        databasePath=database,
        manifestDirectory=tmp_path / "imports",
        dryRun=False,
    )
    destination = Path(completed["assets"][0]["destinationPath"])
    assert destination.read_bytes() != source.read_bytes()
    assert metadataCaptureRead(destination).year == 2018
    assert metadataCaptureRead(source).year == 2015


def testSelectedCompanionsAndOtherSessionRemainAligned(imported):
    result, _, _, _ = imported
    payload = json.loads(result.manifestPath.read_text())
    primary = payload["assets"][0]
    companion = dict(primary)
    companion["relativePath"] = "G0010000.THM"
    companion["destinationPath"] = str(
        Path(primary["destinationPath"]).with_suffix(".THM")
    )
    companion["fileKind"] = "thumbnail"
    Path(companion["destinationPath"]).write_bytes(
        Path(primary["destinationPath"]).read_bytes()
    )
    payload["assets"].append(companion)
    result.manifestPath.write_text(json.dumps(payload))
    plan = correctionPlan(imported, selectedFiles=("G0010000.JPG",))
    assert len(plan.payload["assets"]) == 2
    assert not plan.blocked
    correctionExecute(imported, plan)
    assert Path(payload["assets"][1]["destinationPath"]).exists()
    assert all(
        Path(asset["destinationPath"]).parent.name == "25"
        for asset in plan.payload["assets"]
    )


def testUnrecordedCompanionBlocksRatherThanBeingStranded(imported):
    plan = correctionPlan(imported)
    source = Path(plan.payload["assets"][0]["sourcePath"])
    source.with_suffix(".xml").write_text("metadata")
    assert correctionPlan(imported).blocked


def testSymlinkAndMissingArchiveFileAreBlocked(imported, tmp_path):
    plan = correctionPlan(imported)
    source = Path(plan.payload["assets"][0]["sourcePath"])
    saved = tmp_path / "saved.JPG"
    source.rename(saved)
    assert correctionPlan(imported).blocked
    source.symlink_to(saved)
    assert correctionPlan(imported).blocked


def testVerifiedCorrectionFollowsSubsequentArchiveCopy(imported, tmp_path):
    _, root, database, _ = imported
    correctionExecute(imported, correctionPlan(imported))
    target = tmp_path / "new-archive"
    planner = CameraImportPlanner(
        goproDestination=target,
        droneDestination=target,
        dashcamDestination=target,
        databasePath=database,
    )
    result = CameraImporter(
        planner=planner, manifestDirectory=tmp_path / "new-imports", dryRun=False
    ).importMedia(root, cardId=2)
    assert result.copied == 2
    manifest = json.loads(result.manifestPath.read_text())
    assert all(asset["rawCaptureAt"].startswith("2015") for asset in manifest["assets"])
    assert all(
        asset["correctedCaptureAt"].startswith("2018") for asset in manifest["assets"]
    )
    assert all(
        op.asset.captureAt.year == 2018 for op in planner.importPlan(target).operations
    )


def testPublishRaceDoesNotOverwriteDestination(tmp_path, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_bytes(b"original")
    original = FilesystemOperations._verifyFiles

    def race(self, source, temporary):
        original(self, source, temporary)
        destination.write_bytes(b"concurrent file")

    monkeypatch.setattr(FilesystemOperations, "_verifyFiles", race)
    with pytest.raises(FileExistsError):
        FilesystemOperations(dryRun=False).copyFile(
            source, destination, exclusivePublish=True
        )
    assert source.read_bytes() == b"original"
    assert destination.read_bytes() == b"concurrent file"
    assert not list(tmp_path.glob("*.tmp"))


def testInterruptedCopyCleansTemporaryFiles(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.write_bytes(b"original")

    def interrupt(*args):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        FilesystemOperations(dryRun=False).copyFile(
            source, destination, progressCallback=interrupt
        )
    assert source.exists() and not destination.exists()
    assert not list(tmp_path.glob("*.tmp"))


def testManifestFailureLeavesAllOriginalsUsable(imported, monkeypatch):
    plan = correctionPlan(imported)

    def fail(*args, **kwargs):
        raise OSError("state volume unavailable")

    monkeypatch.setattr(FilesystemOperations, "writeText", fail)
    with pytest.raises(OSError, match="state volume"):
        correctionExecute(imported, plan)
    assert all(Path(asset["sourcePath"]).exists() for asset in plan.payload["assets"])
    assert all(
        not Path(asset["destinationPath"]).exists() for asset in plan.payload["assets"]
    )


def testCliInterruptReturns130(imported, monkeypatch, capsys):
    from organiseMyVideo.cameraCli import _cameraParserBuild
    from organiseMyVideo.cameraCorrectionCli import cameraCorrectionCliRun

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        "organiseMyVideo.cameraCorrectionCli.cameraCorrectionPlan", interrupt
    )
    args = _cameraParserBuild().parse_args(
        [
            "correct-time",
            "--import-manifest",
            "unused",
            "--root",
            "unused",
            "--reference",
            "unused",
            "--actual",
            "2018-08-25T19:00:00",
            "--reason",
            "event",
        ]
    )
    assert cameraCorrectionCliRun(args) == 130
    assert "interrupted" in capsys.readouterr().err


@pytest.mark.parametrize(
    "mutation",
    [
        "noId",
        "noAssets",
        "badSource",
        "duplicatePath",
        "invalidAnchor",
        "dateOnly",
        "outsideRoot",
    ],
)
def testMalformedEvidenceIsRejected(imported, mutation):
    result, _, _, _ = imported
    payload = json.loads(result.manifestPath.read_text())
    if mutation == "noId":
        payload.pop("importId")
    elif mutation == "noAssets":
        payload["assets"] = []
    elif mutation == "badSource":
        payload["source"] = "wrong"
    elif mutation == "duplicatePath":
        payload["assets"][1]["relativePath"] = payload["assets"][0]["relativePath"]
    elif mutation == "invalidAnchor":
        payload["assets"][0]["captureAt"] = "2015-99-99T12:00:00"
    elif mutation == "dateOnly":
        payload["assets"][0]["captureAt"] = "2015-01-01"
    else:
        payload["assets"][1]["destinationPath"] = "/outside/file.JPG"
    result.manifestPath.write_text(json.dumps(payload))
    if mutation == "outsideRoot":
        assert correctionPlan(imported).blocked
    else:
        with pytest.raises(ValueError):
            correctionPlan(imported)


def testSelectedDestinationsCollideWithoutInventingFilename(imported):
    result, _, _, _ = imported
    payload = json.loads(result.manifestPath.read_text())
    first, second = payload["assets"]
    renamed = Path(second["destinationPath"]).with_name(
        Path(first["destinationPath"]).name
    )
    Path(second["destinationPath"]).rename(renamed)
    second["destinationPath"] = str(renamed)
    second["captureAt"] = first["captureAt"]
    result.manifestPath.write_text(json.dumps(payload))
    plan = correctionPlan(imported)
    assert plan.blocked
    assert all("collide" in asset["error"] for asset in plan.payload["assets"])


def testConflictingCompanionDatesBlockWholeScope(imported):
    result, _, _, _ = imported
    payload = json.loads(result.manifestPath.read_text())
    first, second = payload["assets"]
    renamed = Path(first["destinationPath"]).with_suffix(".THM")
    Path(second["destinationPath"]).rename(renamed)
    second["relativePath"] = "G0010000.THM"
    second["destinationPath"] = str(renamed)
    result.manifestPath.write_text(json.dumps(payload))
    plan = correctionPlan(imported)
    assert plan.blocked
    assert "companion timestamps" in plan.payload["assets"][0]["error"]


def testRootLockPreventsConcurrentExecution(imported):
    import fcntl
    import os

    plan = correctionPlan(imported)
    descriptor = os.open(imported[1], os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="another correction"):
            correctionExecute(imported, plan)
    finally:
        os.close(descriptor)
    assert not imported[2].exists()


def testDifferentRuleIntroducedAfterPreviewIsRejected(imported, monkeypatch):
    plan = correctionPlan(imported)
    altered = dict(plan.payload, ruleId="another-rule")
    monkeypatch.setattr(
        "organiseMyVideo.cameraCorrectionExecution.correctionJournalRead",
        lambda *args: [altered],
    )
    with pytest.raises(ValueError, match="scope changed"):
        correctionExecute(imported, plan)
    assert not imported[2].exists()


def testExistingCatalogueReadonlyPreviewAndChangedContentFallback(imported):
    from organiseMyVideo.cameraCorrectionStore import correctionEffectiveCaptureRead

    _, _, database, _ = imported
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE oldCatalogue(value TEXT)")
    before = database.read_bytes()
    plan = correctionPlan(imported)
    assert database.read_bytes() == before
    correctionExecute(imported, plan)
    path = Path(plan.payload["assets"][0]["destinationPath"])
    assert correctionEffectiveCaptureRead(path, databasePath=database) == datetime(
        2018, 8, 25, 19
    )
    path.write_bytes(b"replacement media")
    assert correctionEffectiveCaptureRead(path, databasePath=database) is None


def testConflictingPersistedEffectiveTimestampsAreNotChosenArbitrarily(imported):
    from organiseMyVideo.cameraCorrectionStore import correctionEffectiveCaptureRead

    plan = correctionPlan(imported)
    correctionExecute(imported, plan)
    database = imported[2]
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO cameraCaptureTime SELECT 'other-import',relativePath,ruleId,filePath,sha256,rawCaptureAt,'2020-01-01T00:00:00',dateSource FROM cameraCaptureTime"
        )
    with pytest.raises(ValueError, match="contradictory"):
        correctionEffectiveCaptureRead(
            Path(plan.payload["assets"][0]["destinationPath"]), databasePath=database
        )


def testCliBlockedAndExecutionError(imported, monkeypatch, capsys):
    from organiseMyVideo.cameraCli import _cameraParserBuild
    from organiseMyVideo.cameraCorrectionCli import cameraCorrectionCliRun

    result, root, database, _ = imported
    monkeypatch.setattr(constants, "MEDIA_CATALOGUE_DATABASE", database)
    args = _cameraParserBuild().parse_args(
        [
            "correct-time",
            "--import-manifest",
            str(result.manifestPath),
            "--root",
            str(root),
            "--reference",
            "G0010000.JPG",
            "--actual",
            "2018-08-25T19:00:00",
            "--reason",
            "event",
        ]
    )
    source = Path(correctionPlan(imported).payload["assets"][1]["sourcePath"])
    source.unlink()
    assert cameraCorrectionCliRun(args) == 2
    output = capsys.readouterr().out
    assert "CORRECTION BLOCKED" in output
    assert "Blocked files: 1 of 2. Correction cannot proceed." in output
    assert "G0010001.JPG" in output
    assert "No files have been changed by this invocation." in output
    assert not database.exists()
    result.manifestPath.unlink()
    assert cameraCorrectionCliRun(args) == 2
    assert "error:" in capsys.readouterr().err


def testHistoryCanLocateCorrectedImportWithoutRewritingEvidence(
    imported, monkeypatch, tmp_path
):
    from organiseMyVideo.cameraHistory import cameraHistoryCheck

    result, root, _, _ = imported
    monkeypatch.setattr(
        "organiseMyVideo.cameraHistory.applicationStateDirectory",
        lambda: tmp_path / "history-state",
    )
    correctionExecute(imported, correctionPlan(imported))
    records = cameraHistoryCheck(
        result.manifestPath.parent, cardId=2, archiveRoots=(root,)
    )
    assert len(records) == 2
    assert all(record.status == "moved" for record in records)


def testUnsupportedExclusivePublicationRetainsOriginals(imported, monkeypatch):
    plan = correctionPlan(imported)

    def unsupported(*args, **kwargs):
        raise OSError("hard links unsupported")

    monkeypatch.setattr("organiseMyVideo.filesystemOperations.os.link", unsupported)
    with pytest.raises(OSError, match="hard links"):
        correctionExecute(imported, plan)
    assert all(Path(asset["sourcePath"]).exists() for asset in plan.payload["assets"])
    assert all(
        not Path(asset["destinationPath"]).exists() for asset in plan.payload["assets"]
    )


def testCompanionAddedAfterPreviewBlocksBeforeStateWrite(imported):
    plan = correctionPlan(imported)
    Path(plan.payload["assets"][0]["sourcePath"]).with_suffix(".SRT").write_text(
        "new companion"
    )
    with pytest.raises(ValueError, match="companion"):
        correctionExecute(imported, plan)
    assert not imported[2].exists()


def testSuccessiveManifestCorrectionsFollowCurrentMediaAndKeepHistory(imported):
    from organiseMyVideo.cameraHistory import cameraHistoryCheck
    from organiseMyVideo.cameraCorrectionStore import correctionJournalRead

    first = correctionExecute(imported, correctionPlan(imported))
    firstManifest = Path(first["manifestPath"]).read_bytes()
    originalImport = imported[0].manifestPath.read_bytes()
    secondPlan = correctionPlan(
        imported, actualAt=datetime.fromisoformat("2019-01-01T12:00:00")
    )
    assert not secondPlan.blocked
    assert secondPlan.payload["referenceRecordedAt"] == "2018-08-25T19:00:00"
    second = correctionExecute(imported, secondPlan)
    thirdPlan = correctionPlan(
        imported, actualAt=datetime.fromisoformat("2017-01-01T12:00:00")
    )
    assert not thirdPlan.blocked
    assert thirdPlan.payload["referenceRecordedAt"] == "2019-01-01T12:00:00"
    third = correctionExecute(imported, thirdPlan)
    assert len(correctionJournalRead(imported[2])) == 3
    assert len({item["ruleId"] for item in (first, second, third)}) == 3
    assert third["predecessorRuleIds"] == [second["ruleId"]]
    for asset in third["assets"]:
        current = Path(asset["destinationPath"])
        assert metadataCaptureRead(current).isoformat() == asset["correctedCaptureAt"]
        effective = correctionTimestampRead(current, databasePath=imported[2])
        assert effective["ruleId"] == third["ruleId"]
        assert effective["rawCaptureAt"] == asset["rawCaptureAt"]
    assert Path(first["manifestPath"]).read_bytes() == firstManifest
    assert imported[0].manifestPath.read_bytes() == originalImport
    history = cameraHistoryCheck(
        imported[0].manifestPath.parent, archiveRoots=(imported[1],)
    )
    assert all(record.status == "moved" for record in history)
    assert {record.currentPath for record in history} == {
        Path(asset["destinationPath"]) for asset in third["assets"]
    }


def testZeroOffsetStepsRemainTraceableForLaterManifestCorrection(imported):
    first = correctionExecute(imported, correctionPlan(imported))
    for reason in ("Second independent confirmation", "Third independent confirmation"):
        plan = cameraCorrectionPlan(
            imported[0].manifestPath,
            archiveRoot=imported[1],
            referenceFile="G0010000.JPG",
            actualAt=datetime.fromisoformat("2018-08-25T19:00:00"),
            reason=reason,
            databasePath=imported[2],
        )
        assert not plan.blocked
        assert plan.payload["offsetSeconds"] == "0"
        correctionExecute(imported, plan)
    later = correctionPlan(
        imported, actualAt=datetime.fromisoformat("2019-01-01T12:00:00")
    )
    assert not later.blocked
    assert later.payload["ruleId"] != first["ruleId"]
    correctionExecute(imported, later)
