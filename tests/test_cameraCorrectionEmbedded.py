"""Independent ExifTool acceptance of corrected media, recovery and file times."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from cameraFixtures import jpegWithExif

from organiseMyVideo.cameraCorrectionExecution import cameraCorrectionExecute
from organiseMyVideo.cameraCorrectionFolder import cameraCorrectionFolderPlan
from organiseMyVideo.cameraCorrectionStore import (
    correctionJournalRead,
    correctionTimestampRead,
)
from organiseMyVideo.filesystemOperations import FilesystemOperations


def exifRead(path):
    result = subprocess.run(
        [
            "exiftool",
            "-j",
            "-G1",
            "-a",
            "-s",
            "-api",
            "QuickTimeUTC=0",
            "-time:all",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)[0]


def digestRead(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def media(tmp_path):
    source = tmp_path / "incorrect"
    root = tmp_path / "archive"
    source.mkdir()
    root.mkdir()
    image = source / "G0044159.JPG"
    image.write_bytes(jpegWithExif(datetime(2015, 1, 4, 9, 48, 48)))
    subprocess.run(
        [
            "exiftool",
            "-overwrite_original",
            "-CreateDate=2015:01:04 09:48:48",
            "-ModifyDate=2015:01:04 09:48:48",
            str(image),
        ],
        check=True,
        capture_output=True,
    )
    video = source / "GOPR4150.MP4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=16x16:r=10",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=8000:cl=mono",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map",
            "1:a",
            "-t",
            "0.2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-metadata",
            "creation_time=2015-01-04T07:42:46Z",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    for path in (image, video):
        os.utime(path, (1000000000, datetime(2015, 1, 4, 6, 43, 1).timestamp()))
    return source, root, tmp_path / "state.sqlite", tmp_path / "manifests"


def planRead(media):
    source, root, database, _ = media
    return cameraCorrectionFolderPlan(
        source,
        archiveRoot=root,
        referenceFile="GOPR4150.MP4",
        actualAt=datetime(2018, 8, 22, 18),
        reason="Known event date",
        databasePath=database,
    )


def correctionRun(media, plan=None):
    _, _, database, manifests = media
    return cameraCorrectionExecute(
        plan or planRead(media),
        databasePath=database,
        manifestDirectory=manifests,
        dryRun=False,
    )


def testIndependentGoProAndJpegAcceptance(media):
    source, root, database, _ = media
    originals = {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns, exifRead(path))
        for path in source.iterdir()
    }
    packetCommand = [
        "ffprobe",
        "-v",
        "error",
        "-show_packets",
        "-show_entries",
        "packet=stream_index,data_hash",
        "-show_data_hash",
        "sha256",
        "-of",
        "json",
    ]
    originalPackets = json.loads(
        subprocess.check_output(packetCommand + [str(source / "GOPR4150.MP4")])
    )
    plan = planRead(media)
    assert not plan.blocked
    assert (
        plan.payload["offsetMicroseconds"]
        == (1326 * 86400 + 10 * 3600 + 17 * 60 + 14) * 1000000
    )
    completed = correctionRun(media, plan)
    for asset in completed["assets"]:
        path = Path(asset["destinationPath"])
        oldBytes, oldMtime, oldMetadata = originals[path.name]
        expected = (
            "2018:08:22 18:00:00" if path.suffix == ".MP4" else "2018:08:22 20:06:02"
        )
        metadata = exifRead(path)
        if path.suffix == ".MP4":
            assert (
                json.loads(subprocess.check_output(packetCommand + [str(path)]))
                == originalPackets
            )
            keys = ["QuickTime:CreateDate", "QuickTime:ModifyDate"] + [
                f"Track{track}:{tag}"
                for track in (1, 2, 3)
                for tag in (
                    "TrackCreateDate",
                    "TrackModifyDate",
                    "MediaCreateDate",
                    "MediaModifyDate",
                )
            ]
        else:
            keys = ["ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate", "IFD0:ModifyDate"]
            # Compressed image data is unchanged; only metadata was written.
            assert (
                path.read_bytes().split(b"\xff\xda", 1)[1]
                == oldBytes.split(b"\xff\xda", 1)[1]
            )
        for key in keys:
            assert metadata[key] == expected
            assert asset["originalMetadata"][key] == oldMetadata[key]
            assert asset["correctedMetadata"][key] == expected
        assert asset["originalSha256"] == hashlib.sha256(oldBytes).hexdigest()
        assert asset["destinationSha256"] == digestRead(path) != asset["originalSha256"]
        assert asset["originalMtimeNs"] == oldMtime
        assert (
            path.stat().st_mtime_ns
            == oldMtime + plan.payload["offsetMicroseconds"] * 1000
        )
        assert asset["resultingMtimeNs"] == path.stat().st_mtime_ns
        assert (
            correctionTimestampRead(path, databasePath=database)["sha256"]
            == asset["destinationSha256"]
        )
    saved = correctionJournalRead(database)[0]
    assert saved["reason"] == "Known event date"
    assert saved["referenceRecordedAt"] == "2015-01-04T07:42:46"
    assert saved["referenceActualAt"] == "2018-08-22T18:00:00"
    assert saved["ruleId"] == plan.payload["ruleId"]
    before = {
        path: (digestRead(path), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }
    correctionRun(media)
    assert {
        path: (digestRead(path), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.parametrize("failure", ["write", "verify", "after-write", "after-publish"])
def testMetadataFailureRetainsOriginalsAndResumes(media, monkeypatch, failure):
    import organiseMyVideo.cameraCorrectionExecution as execution

    originals = {path: digestRead(path) for path in media[0].iterdir()}
    plan = planRead(media)
    method = {
        "write": "correctionMetadataWrite",
        "verify": "correctionMetadataVerify",
        "after-write": "correctionMetadataWrite",
    }.get(failure)
    if method:
        original = getattr(execution, method)

        def fail(*args):
            if failure == "after-write":
                original(*args)
            raise ValueError("injected metadata failure")

        monkeypatch.setattr(execution, method, fail)
    else:
        original = FilesystemOperations.publishVerifiedCopy

        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("injected metadata failure")

        monkeypatch.setattr(FilesystemOperations, "publishVerifiedCopy", fail)
    with pytest.raises(ValueError, match="injected"):
        correctionRun(media, plan)
    assert all(
        path.exists() and digestRead(path) == digest
        for path, digest in originals.items()
    )
    journal = correctionJournalRead(media[2])[0]
    assert all(
        asset["originalMetadata"] and asset["originalSha256"]
        for asset in journal["assets"]
    )
    monkeypatch.undo()
    repeated = correctionRun(media)
    assert all(asset["outcome"] == "applied" for asset in repeated["assets"])
    assert all(not path.exists() for path in originals)


def testMtimeSetterDoesNotRewriteAtime(tmp_path, monkeypatch):
    path = tmp_path / "file"
    path.write_bytes(b"original")
    os.utime(path, ns=(1000000000000000000, 1100000000000000000))
    atime = path.stat().st_atime_ns

    def forbidden(*args, **kwargs):
        raise AssertionError("os.utime must not round-trip atime")

    monkeypatch.setattr(os, "utime", forbidden)
    FilesystemOperations(dryRun=False).setModificationTime(path, 1500000000000000000)
    assert path.stat().st_atime_ns == atime
    assert path.stat().st_mtime_ns == 1500000000000000000


def testSamePathCorrectionUsesVerifiedCopy(tmp_path):
    root = tmp_path / "archive"
    source = root / "2015/01/04"
    source.mkdir(parents=True)
    path = source / "GOPR4150.JPG"
    path.write_bytes(jpegWithExif(datetime(2015, 1, 4, 7, 42, 46)))
    original = digestRead(path)
    database = tmp_path / "state.sqlite"

    def plan():
        return cameraCorrectionFolderPlan(
            source,
            archiveRoot=root,
            referenceFile=path.name,
            actualAt=datetime(2015, 1, 4, 18),
            reason="Same-day clock",
            databasePath=database,
        )

    preview = plan()
    assert not preview.blocked
    result = cameraCorrectionExecute(
        preview,
        databasePath=database,
        manifestDirectory=tmp_path / "manifests",
        dryRun=False,
    )
    assert exifRead(path)["ExifIFD:DateTimeOriginal"] == "2015:01:04 18:00:00"
    assert result["assets"][0]["originalSha256"] == original != digestRead(path)
    assert len(list(source.iterdir())) == 1
    assert plan().payload["assets"][0]["outcome"] == "applied"


@pytest.mark.parametrize(
    "mtime", [datetime(2018, 8, 22, 18), datetime(2026, 1, 2), datetime(2017, 1, 1)]
)
def testConditionalMtimeAndJournalOnlyChangedValues(media, mtime):
    path = media[0] / "GOPR4150.MP4"
    originalNs = round(mtime.timestamp() * 1_000_000_000) + 123
    os.utime(path, ns=(1000000000000000000, originalNs))
    plan = planRead(media)
    changed = originalNs < round(datetime(2018, 8, 22, 18).timestamp() * 1_000_000_000)
    result = correctionRun(media, plan)
    asset = next(item for item in result["assets"] if item["relativePath"] == path.name)
    destination = Path(asset["destinationPath"])
    if changed:
        assert asset["originalMtimeNs"] == originalNs
        assert (
            asset["resultingMtimeNs"]
            == originalNs + plan.payload["offsetMicroseconds"] * 1000
        )
        assert destination.stat().st_mtime_ns == asset["resultingMtimeNs"]
    else:
        assert destination.stat().st_mtime_ns == originalNs
        assert "originalMtimeNs" not in asset and "resultingMtimeNs" not in asset
        saved = next(
            item
            for item in correctionJournalRead(media[2])[0]["assets"]
            if item["relativePath"] == path.name
        )
        assert "originalMtimeNs" not in saved and "resultingMtimeNs" not in saved


def testCopiedRawCheckpointResumesWithoutSecondOffset(media, monkeypatch):
    import organiseMyVideo.cameraCorrectionExecution as execution

    original = execution._correctionCheckpoint

    def interrupt(payload, *args):
        original(payload, *args)
        if any(asset.get("metadataState") == "copied" for asset in payload["assets"]):
            raise KeyboardInterrupt()

    monkeypatch.setattr(execution, "_correctionCheckpoint", interrupt)
    with pytest.raises(KeyboardInterrupt):
        correctionRun(media)
    saved = correctionJournalRead(media[2])[0]
    copied = next(
        asset for asset in saved["assets"] if asset["metadataState"] == "copied"
    )
    assert digestRead(Path(copied["workPath"])) == copied["originalSha256"]
    monkeypatch.undo()
    result = correctionRun(media)
    assert all(asset["outcome"] == "applied" for asset in result["assets"])


def testDuplicateSidecarStillReceivesMtimeCorrection(media):
    source, root, _, _ = media
    sidecar = source / "GOPR4150.SRT"
    sidecar.write_text("telemetry")
    oldNs = round(datetime(2015, 1, 4, 6, 43, 1).timestamp() * 1_000_000_000)
    os.utime(sidecar, ns=(1000000000000000000, oldNs))
    destination = root / "2018/08/22/GOPR4150.SRT"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(sidecar.read_bytes())
    plan = planRead(media)
    correctionRun(media, plan)
    assert (
        destination.stat().st_mtime_ns
        == oldNs + plan.payload["offsetMicroseconds"] * 1000
    )
    assert not sidecar.exists()


def testLegacyCatalogueOnlyCorrectionCanBeUpgraded(media):
    from organiseMyVideo.cameraCorrectionMetadata import CORRECTION_EVIDENCE_KEYS
    from organiseMyVideo.cameraCorrectionStore import correctionJournalWrite

    preview = planRead(media)
    legacy = preview.payload
    legacy["schemaVersion"] = 2
    for asset in legacy["assets"]:
        for key in CORRECTION_EVIDENCE_KEYS:
            asset.pop(key, None)
        source, destination = Path(asset["sourcePath"]), Path(asset["destinationPath"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        source.unlink()
        asset["outcome"] = "applied"
    correctionJournalWrite(media[2], legacy)
    upgraded = planRead(media)
    assert not upgraded.blocked
    assert all(asset["outcome"] != "applied" for asset in upgraded.payload["assets"])
    result = correctionRun(media, upgraded)
    for asset in result["assets"]:
        assert asset["destinationSha256"] != asset["originalSha256"]
        assert exifRead(Path(asset["destinationPath"]))[
            next(iter(asset["correctedMetadata"]))
        ].startswith("2018:")


@pytest.mark.parametrize(
    "offsetSeconds,mtimeSeconds,changed,resultSeconds",
    [
        (1000, 1000, True, 2000),
        (-1000, 1000, True, 0),
        (1000, 2000, False, 2000),
        (1000, 3000, False, 3000),
        (0, 1000, False, 1000),
    ],
)
def testExactConditionalMtimePolicy(
    tmp_path, offsetSeconds, mtimeSeconds, changed, resultSeconds
):
    from datetime import timedelta, timezone

    from organiseMyVideo.cameraCorrectionMetadata import correctionMetadataPlan

    path = tmp_path / "file.SRT"
    path.write_text("sidecar")
    os.utime(path, ns=(1000000000, mtimeSeconds * 1000000000))
    asset = {
        "sha256": "0" * 64,
        "correctedCaptureAt": datetime.fromtimestamp(2000, tz=timezone.utc).isoformat(),
    }
    result = correctionMetadataPlan(path, asset, timedelta(seconds=offsetSeconds))
    assert (result["mtimePolicy"] == "shift") == changed
    assert (
        result.get("resultingMtimeNs", mtimeSeconds * 1000000000)
        == resultSeconds * 1000000000
    )
    assert ("originalMtimeNs" in result) == changed
    assert ("resultingMtimeNs" in result) == changed


def testPublicationInterruptionPreservesOriginalBackupAndResumes(media, monkeypatch):
    source, root, _, _ = media
    plan = planRead(media)
    asset = plan.payload["assets"][0]
    destination = Path(asset["destinationPath"])
    destination.parent.mkdir(parents=True)
    destination.write_bytes(Path(asset["sourcePath"]).read_bytes())
    original = os.link

    def failPublish(first, second, *args, **kwargs):
        if Path(second) == destination:
            raise OSError("publication interrupted")
        return original(first, second, *args, **kwargs)

    monkeypatch.setattr(os, "link", failPublish)
    with pytest.raises(OSError, match="publication interrupted"):
        correctionRun(media)
    saved = correctionJournalRead(media[2])[0]
    entry = next(
        item
        for item in saved["assets"]
        if item["relativePath"] == asset["relativePath"]
    )
    assert digestRead(Path(entry["backupPath"])) == entry["originalSha256"]
    assert all(Path(item["sourcePath"]).exists() for item in saved["assets"])
    monkeypatch.undo()
    assert all(item["outcome"] == "applied" for item in correctionRun(media)["assets"])


def testCorrectionDoesNotDeliberatelyRewriteAtime(media, monkeypatch):
    import shutil

    def forbidden(*args, **kwargs):
        raise AssertionError("correction must not set atime through utime/copystat")

    monkeypatch.setattr(os, "utime", forbidden)
    monkeypatch.setattr(shutil, "copystat", forbidden)
    assert all(
        asset["outcome"] == "applied" for asset in correctionRun(media)["assets"]
    )


def testSecondGoProCorrectionUsesCurrentTracksAndSidecarState(media):
    first = correctionRun(media)
    originalAudit = Path(first["manifestPath"]).read_bytes()
    currentFolder = media[1] / "2018/08/22"
    sidecar = currentFolder / "GOPR4150.SRT"
    sidecar.write_text("telemetry")
    os.utime(sidecar, (1000000000, datetime(2018, 8, 22, 17).timestamp()))
    sidecarBefore = sidecar.stat().st_mtime_ns
    secondPlan = cameraCorrectionFolderPlan(
        currentFolder,
        archiveRoot=media[1],
        referenceFile="GOPR4150.MP4",
        actualAt=datetime.fromisoformat("2018-08-22T18:05:00"),
        reason="Refined event evidence",
        databasePath=media[2],
    )
    assert not secondPlan.blocked
    assert secondPlan.payload["offsetSeconds"] == "300"
    second = correctionRun(media, secondPlan)
    video = next(
        asset for asset in second["assets"] if asset["relativePath"].endswith("MP4")
    )
    tags = exifRead(Path(video["destinationPath"]))
    for key in video["correctedMetadata"]:
        assert tags[key] == "2018:08:22 18:05:00"
    assert (
        exifRead(currentFolder / "G0044159.JPG")["ExifIFD:DateTimeOriginal"]
        == "2018:08:22 20:11:02"
    )
    assert sidecar.read_text() == "telemetry"
    assert sidecar.stat().st_mtime_ns == sidecarBefore + 300000000000
    assert (
        correctionTimestampRead(sidecar, databasePath=media[2])["ruleId"]
        == second["ruleId"]
    )
    assert Path(first["manifestPath"]).read_bytes() == originalAudit
