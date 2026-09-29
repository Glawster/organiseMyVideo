"""Read-only capture-correction evidence for folders without import history."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime
from pathlib import Path

from organiseMediaStudio.identity.hash import mediaHashCalculate

from .cameraCorrection import (
    CameraCorrectionPlan,
    CorrectionProgress,
    _correctionPathValidate,
    cameraCorrectionEvidencePlan,
)
from .cameraCorrectionHistory import (
    correctionCompleted,
    correctionReplay,
    correctionRequestMatches,
)
from .cameraCorrectionStore import correctionJournalRead
from .cameraMetadata import metadataCaptureDetailsRead

_ORIGINAL_SUFFIXES = {".mp4", ".mov", ".jpg", ".jpeg", ".cr3"}
_COMPANION_SUFFIXES = {".srt", ".nmea", ".xml", ".thm", ".lrv", ".png", ".webp"}


def cameraCorrectionFolderPlan(
    source: Path,
    *,
    archiveRoot: Path,
    referenceFile: str,
    actualAt: datetime,
    reason: str,
    databasePath: Path,
    selectedFiles: tuple[str, ...] = (),
    progressCallback: CorrectionProgress | None = None,
) -> CameraCorrectionPlan:
    """Snapshot an explicit folder selection, or review its saved correction evidence."""
    sourceRoot = Path(source).expanduser().resolve(strict=True)
    root = Path(archiveRoot).expanduser().resolve(strict=True)
    if not sourceRoot.is_dir() or not root.is_dir():
        raise ValueError("source and archive root must be existing directories")
    if root.is_relative_to(sourceRoot):
        raise ValueError("archive root must not be the source or a descendant of it")
    requested = tuple(sorted({_folderRelativeValidate(name) for name in selectedFiles}))
    referenceFile = _folderRelativeValidate(referenceFile)
    # This lookup identifies a frozen selection, not a rule for future folder content.
    scopeId = "folder:" + _folderIdentity(
        {"sourceRoot": str(sourceRoot), "requestedFiles": requested}
    )
    journals = correctionJournalRead(databasePath)
    matching = [
        item
        for item in journals
        if item.get("selectionId", item.get("scopeId")) == scopeId
    ]
    previous = next((item for item in matching if not correctionCompleted(item)), None)
    # Completed scopes release their paths. Only an unchanged, exact repeat is a no-op.
    if previous is None:
        for item in reversed(matching):
            if not correctionRequestMatches(
                item, root, referenceFile, actualAt, reason
            ):
                continue
            paths, _ = _folderFilesList(sourceRoot)
            current = {
                str(sourceRoot / name)
                for name in _folderSelectionPaths(paths, requested)
            }
            outputs = {asset["destinationPath"] for asset in item["assets"]}
            if current <= outputs:
                replay = correctionReplay(item)
                if replay is not None:
                    return CameraCorrectionPlan(replay)
    if previous:
        correctionFolderScopeValidate(previous)
        evidence = {
            key: previous[key]
            for key in (
                "scopeId",
                "scopeType",
                "sourceRoot",
                "requestedFiles",
                "folderEvidence",
                "excludedPaths",
            )
        }
    else:
        legacy = next(
            (
                item
                for item in reversed(matching)
                if correctionCompleted(item)
                and correctionRequestMatches(
                    item, root, referenceFile, actualAt, reason
                )
                and all(not asset.get("metadataVersion") for asset in item["assets"])
            ),
            None,
        )
        if legacy and not (sourceRoot / referenceFile).exists():
            # Upgrade catalogue-only history through a new transformation of its outputs.
            records = []
            for asset in legacy["assets"]:
                path = Path(asset["destinationPath"])
                record = _folderAssetRead(path.parent, path.name)
                record["relativePath"] = asset["relativePath"]
                records.append(record)
            _folderCompanionsResolve(records)
            sourceRoot = root
            requested = tuple(
                str(Path(asset["destinationPath"]).relative_to(root))
                for asset in legacy["assets"]
            )
            evidence = {"folderEvidence": records, "excludedPaths": []}
        else:
            evidence = _folderEvidenceCollect(
                sourceRoot, requested, referenceFile, progressCallback
            )
        evidence.update(
            scopeId=scopeId,
            scopeType="folder",
            sourceRoot=str(sourceRoot),
            requestedFiles=list(requested),
        )
    evidence["selectionId"] = scopeId
    if previous is None:
        evidence["scopeId"] = "folder:" + _folderIdentity(evidence)
    assets = evidence["folderEvidence"]
    if referenceFile not in {asset["relativePath"] for asset in assets}:
        raise ValueError(
            "reference file must be an original in the selected folder scope"
        )
    if Path(referenceFile).suffix.lower() not in _ORIGINAL_SUFFIXES:
        raise ValueError("reference file must be original media, not a companion")
    return cameraCorrectionEvidencePlan(
        assets,
        root=root,
        sourceRoot=Path(evidence["sourceRoot"]),
        referenceFile=referenceFile,
        actualAt=actualAt,
        reason=reason,
        databasePath=databasePath,
        importId=None,
        scopeEvidence=evidence,
        previous=journals,
        progressCallback=progressCallback,
    )


def correctionFolderScopeValidate(payload: dict) -> None:
    """Reject newly added selected media; retries use the saved file set and hashes."""
    source = Path(payload["sourceRoot"])
    if not source.is_dir() or source.resolve() != source:
        raise ValueError("recorded source folder is missing or has changed")
    paths, _ = _folderFilesList(source)
    current = _folderSelectionPaths(paths, tuple(payload["requestedFiles"]))
    known = {Path(asset["sourcePath"]) for asset in payload["assets"]}
    destinations = {Path(asset["destinationPath"]) for asset in payload["assets"]}
    work = {
        Path(value)
        for asset in payload["assets"]
        for value in [
            asset.get("workPath"),
            asset.get("backupPath"),
            *asset.get("abandonedStages", []),
        ]
        if value
    }
    added = {source / name for name in current} - known - destinations - work
    if added:
        raise ValueError(
            "folder scope contains new files; use an explicit new --file selection: "
            + ", ".join(str(path) for path in sorted(added))
        )


## evidence


def _folderEvidenceCollect(
    source: Path,
    requested: tuple[str, ...],
    reference: str,
    progress: CorrectionProgress | None,
) -> dict:
    if progress:
        progress(0, 0, "Scanning correction source folder")
    paths, ignored = _folderFilesList(source)
    names = _folderSelectionPaths(paths, requested)
    if (
        not names
        or reference not in names
        or any(name not in names for name in requested)
    ):
        raise ValueError("reference and selected files must exist in the source folder")
    records = []
    for index, name in enumerate(names):
        if progress:
            progress(index, len(names), f"Reading metadata/hashing {name}")
        records.append(_folderAssetRead(source, name))
    _folderCompanionsResolve(records)
    if progress:
        progress(len(names), len(names), "Folder evidence collected")
    return {
        "folderEvidence": records,
        "excludedPaths": sorted(set(ignored) | (set(paths) - set(names))),
    }


def _folderAssetRead(source: Path, name: str) -> dict:
    path = source / name
    record = {
        "relativePath": name,
        "destinationPath": str(path),
        "captureAt": None,
        "dateSource": "unavailable",
        "outcome": "observed",
    }
    try:
        _correctionPathValidate(path, source)
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"not a regular file: {path}")
        captured, dateSource, timestampEvidence = metadataCaptureDetailsRead(path)
        digest = mediaHashCalculate(path, algorithm="sha256")
        after = path.stat()
        # Evidence may not combine metadata and content from different file versions.
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError(f"file changed while reading capture evidence: {path}")
        record.update(
            captureAt=captured.isoformat() if captured else None,
            dateSource=dateSource,
            timestampEvidence=timestampEvidence,
            sourceDigest=digest,
            sizeBytes=after.st_size,
        )
    except (OSError, ValueError) as error:
        record["error"] = str(error)
    return record


def _folderCompanionsResolve(records: list[dict]) -> None:
    """Route helper files by an unambiguous same-stem original; retain their evidence."""
    for record in records:
        path = Path(record["relativePath"])
        if path.suffix.lower() not in _COMPANION_SUFFIXES:
            continue
        originals = [
            item
            for item in records
            if Path(item["relativePath"]).parent == path.parent
            and Path(item["relativePath"]).stem.lower() == path.stem.lower()
            and Path(item["relativePath"]).suffix.lower() in _ORIGINAL_SUFFIXES
        ]
        times = {item["captureAt"] for item in originals if not item.get("error")}
        if (
            not originals
            or None in times
            or len(times) != 1
            or any(item.get("error") for item in originals)
        ):
            record["error"] = "companion has no unambiguous original capture timestamp"
            continue
        primary = originals[0]
        record.update(
            observedCaptureAt=record["captureAt"],
            observedDateSource=record["dateSource"],
            captureAt=primary["captureAt"],
            dateSource="companion",
            timestampEvidencePath=primary["relativePath"],
        )


## selection


def _folderFilesList(source: Path) -> tuple[list[str], list[str]]:
    paths, ignored = [], []

    def fail(error: OSError) -> None:
        raise error

    for directory, subdirectories, filenames in os.walk(
        source, followlinks=False, onerror=fail
    ):
        for name in sorted(subdirectories + filenames):
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError(f"symlink in correction source: {path}")
            if name in subdirectories:
                continue
            relative = path.relative_to(source).as_posix()
            if path.suffix.lower() in _ORIGINAL_SUFFIXES | _COMPANION_SUFFIXES:
                paths.append(relative)
            else:
                ignored.append(relative)
    return sorted(paths), sorted(ignored)


def _folderSelectionPaths(paths: list[str], requested: tuple[str, ...]) -> list[str]:
    if not requested:
        return paths
    # Expand all requested stems, including a missing original during recovery.
    groups = {(Path(name).parent, Path(name).stem.lower()) for name in requested}
    return [
        name for name in paths if (Path(name).parent, Path(name).stem.lower()) in groups
    ]


def _folderRelativeValidate(value: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ValueError(
            "reference and --file values must be relative filenames within --source"
        )
    return path.as_posix()


def _folderIdentity(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
