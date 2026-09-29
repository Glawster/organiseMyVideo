"""Journalled, verified relocation of a reviewed camera correction scope."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from organiseMediaStudio.identity.hash import mediaHashCalculate

from .cameraCorrection import (
    CameraCorrectionPlan,
    CorrectionProgress,
    _correctionCompanionsCheck,
    _correctionDigestVerify,
    _correctionExistingValidate,
    _correctionPathValidate,
)
from .cameraCorrectionHistory import correctionCompleted, correctionReplay
from .cameraCorrectionMetadata import (
    CORRECTION_EVIDENCE_KEYS,
    correctionMetadataVerify,
    correctionMetadataWrite,
    correctionMtimeVerify,
)
from .cameraCorrectionStore import (
    correctionJournalRead,
    correctionJournalWrite,
    correctionScopeKey,
)
from .filesystemOperations import FilesystemOperations


def cameraCorrectionExecute(
    plan: CameraCorrectionPlan,
    *,
    databasePath: Path,
    manifestDirectory: Path,
    dryRun: bool = True,
    progressCallback: CorrectionProgress | None = None,
) -> dict:
    """Copy/verify the whole scope before removing old paths; retain a recovery journal."""
    payload = copy.deepcopy(plan.payload)
    if dryRun or plan.blocked:
        return payload
    if correctionCompleted(payload):
        return payload
    # Directory locking serialises this workflow without creating dry-run state.
    descriptors = []
    try:
        roots = {
            payload["archiveRoot"],
            payload.get("sourceRoot", payload["archiveRoot"]),
        }
        for root in sorted(roots):
            descriptor = os.open(root, os.O_RDONLY)
            descriptors.append(descriptor)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(
                    "another correction is running for this source/archive root"
                ) from error
        return _correctionApply(
            payload, databasePath, manifestDirectory, progressCallback
        )
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _correctionApply(
    payload: dict,
    databasePath: Path,
    manifestDirectory: Path,
    progressCallback: CorrectionProgress | None,
) -> dict:
    previous = next(
        (
            item
            for item in correctionJournalRead(databasePath, correctionScopeKey(payload))
            if item["ruleId"] == payload["ruleId"]
        ),
        {},
    )
    if previous and correctionCompleted(previous):
        replay = correctionReplay(previous)
        if replay is None:
            raise ValueError(
                "completed correction output changed; create a fresh preview"
            )
        return replay
    payload["executedAt"] = datetime.now(timezone.utc).isoformat()
    # Resume from the last durable byte identities, including a saved preview.
    priorAssets = {item["relativePath"]: item for item in previous.get("assets", [])}
    for asset in payload["assets"]:
        prior = priorAssets.get(asset["relativePath"], {})
        if prior.get("metadataVersion"):
            asset.update(
                {key: prior[key] for key in CORRECTION_EVIDENCE_KEYS if key in prior}
            )
    payload["attempts"] = previous.get("attempts", []) + [payload["executedAt"]]
    manifestPath = (
        Path(manifestDirectory) / f"camera-correction-{payload['ruleId']}.json"
    )
    payload["manifestPath"] = str(manifestPath)
    filesystem = FilesystemOperations(dryRun=False)
    # Recheck the entire preview before persisting any new state or copying media.
    _correctionPreflight(payload, databasePath)
    for asset in payload["assets"]:
        asset["outcome"] = "pending"
    _correctionCheckpoint(payload, databasePath, manifestPath, filesystem)
    try:

        def checkpoint() -> None:
            _correctionCheckpoint(payload, databasePath, manifestPath, filesystem)

        _correctionDestinationsPrepare(
            payload, filesystem, progressCallback, checkpoint
        )
        _correctionDestinationsPublish(payload, filesystem, checkpoint)
        for asset in payload["assets"]:
            destination = Path(asset["destinationPath"])
            asset["filesystemAfter"] = {
                "sizeBytes": destination.stat().st_size,
                "mtimeNs": destination.stat().st_mtime_ns,
            }
            asset["outcome"] = "verified"
        # Effective dates are committed only after every destination is verified.
        _correctionCheckpoint(payload, databasePath, manifestPath, filesystem)
        _correctionSourcesRemove(
            payload, databasePath, manifestPath, filesystem, progressCallback
        )
    except (Exception, KeyboardInterrupt) as error:
        payload["error"] = str(error) or "interrupted"
        # The previous durable checkpoint remains useful even if this write fails.
        _correctionCheckpoint(payload, databasePath, manifestPath, filesystem)
        raise
    _correctionWorkClean(payload, filesystem)
    _correctionDirectoriesClean(payload, filesystem)
    payload.pop("error", None)
    payload["completedAt"] = datetime.now(timezone.utc).isoformat()
    _correctionCheckpoint(payload, databasePath, manifestPath, filesystem)
    return payload


## execution


def _correctionCheckpoint(
    payload: dict,
    databasePath: Path,
    manifestPath: Path,
    filesystem: FilesystemOperations,
) -> None:
    correctionJournalWrite(databasePath, payload)
    filesystem.writeText(
        manifestPath,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        stateKind="camera-correction-manifest",
    )


def _correctionPreflight(payload: dict, databasePath: Path) -> None:
    root = Path(payload["archiveRoot"])
    folderScope = payload.get("scopeType") == "folder"
    if folderScope:
        from .cameraCorrectionFolder import correctionFolderScopeValidate

        correctionFolderScopeValidate(payload)
    for previous in correctionJournalRead(databasePath):
        previousPaths = {
            item[key]
            for item in previous["assets"]
            for key in ("sourcePath", "destinationPath")
        }
        currentPaths = {
            item[key]
            for item in payload["assets"]
            for key in ("sourcePath", "destinationPath")
        }
        unobserved = previous["ruleId"] not in payload.get("observedRuleIds", [])
        if (
            previous["ruleId"] != payload["ruleId"]
            and previousPaths & currentPaths
            and (not correctionCompleted(previous) or unobserved)
        ):
            raise ValueError("correction scope changed after preview")
    for asset in payload["assets"]:
        original, destination = Path(asset["sourcePath"]), Path(
            asset["destinationPath"]
        )
        source = Path(asset["currentPath"])
        for key in ("workPath", "backupPath"):
            if asset.get(key):
                _correctionPathValidate(Path(asset[key]), root)
        if source == original:
            _correctionPathValidate(source, Path(payload.get("sourceRoot", root)))
        else:
            _correctionPathValidate(source, root)
        _correctionPathValidate(destination, root)
        if source.exists():
            expected = asset["sha256"]
            if source == destination and asset.get("destinationSha256"):
                observed = mediaHashCalculate(source, algorithm="sha256")
                if observed == asset["destinationSha256"]:
                    expected = observed
            _correctionDigestVerify(source, expected)
        elif not asset.get("destinationSha256"):
            raise ValueError(f"missing original capture evidence: {source}")
        if (
            source.exists()
            and mediaHashCalculate(source, algorithm="sha256") == asset["sha256"]
        ):
            before = asset.get("filesystemBefore")
            correctedInPlace = (
                source == destination
                and asset.get("destinationSha256")
                and _correctionDestinationReady(source, asset)
            )
            if (
                before
                and not correctedInPlace
                and source.stat().st_mtime_ns != before["mtimeNs"]
            ):
                raise ValueError(f"source mtime changed after preview: {source}")
        _correctionExistingValidate(source, destination, asset, databasePath)
        _correctionCompanionsCheck(
            original,
            [{"destinationPath": item["sourcePath"]} for item in payload["assets"]],
        )
        if destination.exists():
            observed = mediaHashCalculate(destination, algorithm="sha256")
            if observed not in {asset["sha256"], asset.get("destinationSha256")}:
                raise ValueError(f"SHA-256 conflict or changed content: {destination}")
        if original.exists() and original != destination:
            _correctionDigestVerify(original, asset["sha256"])


def _correctionDestinationsPrepare(
    payload: dict,
    filesystem: FilesystemOperations,
    progress: CorrectionProgress | None,
    checkpoint,
) -> None:
    assets = payload["assets"]
    for index, asset in enumerate(assets):
        source, destination = Path(asset["currentPath"]), Path(asset["destinationPath"])
        if progress:
            progress(index, len(assets), f"Copying/correcting/verifying {source.name}")
        _correctionPathValidate(destination, Path(payload["archiveRoot"]))
        correctedDigest = asset.get("destinationSha256")
        if correctedDigest and _correctionDestinationReady(destination, asset):
            continue
        work = Path(asset["workPath"]) if asset.get("workPath") else None
        if work and work.exists():
            digest = mediaHashCalculate(work, algorithm="sha256")
            if correctedDigest:
                _correctionDigestVerify(work, correctedDigest)
                correctionMetadataVerify(work, asset)
                correctionMtimeVerify(work, asset)
                continue
            if digest != asset["sha256"]:
                # A crash may interrupt ExifTool before a corrected hash is durable.
                # Retain that uncertain copy and rebuild from verified raw evidence.
                asset.setdefault("abandonedStages", []).append(str(work))
                work = None
        if work is None:
            token = uuid.uuid4().hex
            work = destination.with_name(f".omv-{token}.omvwork")
            asset["workPath"] = str(work)
            asset["metadataState"] = "copying"
            checkpoint()
        if not work.exists():
            _correctionDigestVerify(source, asset["sha256"])
            filesystem.copyFile(
                source,
                work,
                preserveMetadata=False,
                stateKind="camera-correction",
                exclusivePublish=True,
                progressCallback=(
                    None
                    if progress is None
                    else lambda done, total, name=source.name: progress(
                        done, total, f"Copying {name}"
                    )
                ),
            )
        _correctionDigestVerify(work, asset["sha256"])
        asset["metadataState"] = "copied"
        checkpoint()
        asset["metadataState"] = "metadata-writing"
        checkpoint()
        originalMtime = source.stat().st_mtime_ns
        if asset.get("originalMtimeNs", originalMtime) != originalMtime:
            raise ValueError(f"source mtime changed after preview: {source}")
        correctionMetadataWrite(work, asset)
        correctionMetadataVerify(work, asset)
        filesystem.setModificationTime(
            work, asset.get("resultingMtimeNs", originalMtime)
        )
        asset["destinationSha256"] = mediaHashCalculate(work, algorithm="sha256")
        asset["metadataState"] = "metadata-verified"
        checkpoint()
    if progress:
        progress(len(assets), len(assets), "All corrected copies verified")


def _correctionDestinationReady(path: Path, asset: dict) -> bool:
    if (
        not path.exists()
        or mediaHashCalculate(path, algorithm="sha256") != asset["destinationSha256"]
    ):
        return False
    correctionMetadataVerify(path, asset)
    try:
        correctionMtimeVerify(path, asset)
    except ValueError:
        # Unchanged sidecar bytes alone do not prove mtime was corrected.
        if asset["sha256"] == asset["destinationSha256"]:
            return False
        raise
    return True


def _correctionDestinationsPublish(
    payload: dict, filesystem: FilesystemOperations, checkpoint
) -> None:
    for asset in payload["assets"]:
        destination = Path(asset["destinationPath"])
        if _correctionDestinationReady(destination, asset):
            continue
        if not asset.get("backupPath"):
            asset["backupPath"] = str(
                destination.with_name(f".omv-original-{uuid.uuid4().hex}.omvwork")
            )
            checkpoint()
        filesystem.publishVerifiedCopy(
            Path(asset["workPath"]),
            destination,
            correctedDigest=asset["destinationSha256"],
            originalDigest=asset["sha256"],
            backup=Path(asset["backupPath"]),
            correctedMtimeNs=Path(asset["workPath"]).stat().st_mtime_ns,
        )
        _correctionDigestVerify(destination, asset["destinationSha256"])
        correctionMetadataVerify(destination, asset)
        asset["metadataState"] = "published"
        checkpoint()


def _correctionWorkClean(payload: dict, filesystem: FilesystemOperations) -> None:
    for asset in payload["assets"]:
        for key, digest in (
            ("workPath", asset["destinationSha256"]),
            ("backupPath", asset["sha256"]),
        ):
            if asset.get(key) and Path(asset[key]).exists():
                path = Path(asset[key])
                _correctionPathValidate(path, Path(payload["archiveRoot"]))
                _correctionDigestVerify(path, digest)
                filesystem.removeFile(path, stateKind="camera-correction-work")


def _correctionSourcesRemove(
    payload: dict,
    databasePath: Path,
    manifestPath: Path,
    filesystem: FilesystemOperations,
    progress: CorrectionProgress | None,
) -> None:
    for index, asset in enumerate(payload["assets"]):
        source, destination = Path(asset["sourcePath"]), Path(asset["destinationPath"])
        if progress:
            progress(index, len(payload["assets"]), f"Finalising {source.name}")
        # Revalidate both copies immediately before deleting the previous path.
        _correctionPathValidate(
            source, Path(payload.get("sourceRoot", payload["archiveRoot"]))
        )
        _correctionPathValidate(destination, Path(payload["archiveRoot"]))
        _correctionDigestVerify(destination, asset["destinationSha256"])
        correctionMetadataVerify(destination, asset)
        correctionMtimeVerify(destination, asset)
        if source != destination and source.exists():
            _correctionDigestVerify(source, asset["sha256"])
            filesystem.removeFile(source, stateKind="camera-correction")
        asset["outcome"] = "applied"
        _correctionCheckpoint(payload, databasePath, manifestPath, filesystem)
    if progress:
        progress(len(payload["assets"]), len(payload["assets"]), "Correction complete")


def _correctionDirectoriesClean(
    payload: dict, filesystem: FilesystemOperations
) -> None:
    root = Path(payload.get("sourceRoot", payload["archiveRoot"]))
    directories = {
        parent
        for asset in payload["assets"]
        for parent in Path(asset["sourcePath"]).parents
        if parent != root and parent.is_relative_to(root)
    }
    for directory in sorted(
        directories, key=lambda path: len(path.parts), reverse=True
    ):
        if (
            directory.is_dir()
            and not directory.is_symlink()
            and not any(directory.iterdir())
        ):
            filesystem.removeEmptyDirectory(directory, stateKind="camera-correction")
