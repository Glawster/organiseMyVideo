"""Evidence-scoped camera capture-time correction planning, without mutations."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from organiseMediaStudio.identity.hash import mediaHashCalculate
from organiseMediaStudio.metadata.captureCorrection import CaptureDateCorrection

from .cameraCorrectionHistory import (
    correctionCompleted,
    correctionImportCurrent,
    correctionPredecessors,
    correctionReplay,
    correctionRequestMatches,
)
from .cameraCorrectionMetadata import CORRECTION_EVIDENCE_KEYS, correctionMetadataPlan
from .cameraCorrectionStore import correctionJournalRead, correctionTimestampRead

CorrectionProgress = Callable[[int, int, str], None]


@dataclass(frozen=True)
class CameraCorrectionPlan:
    """Reviewable provenance and per-file decisions for one bounded correction scope."""

    payload: dict

    @property
    def blocked(self) -> bool:
        """A conflict or missing evidence blocks the whole selected scope."""
        return any(asset["outcome"] == "blocked" for asset in self.payload["assets"])


def cameraCorrectionPlan(
    manifestPath: Path,
    *,
    archiveRoot: Path,
    referenceFile: str,
    actualAt: datetime,
    reason: str,
    databasePath: Path,
    selectedFiles: tuple[str, ...] = (),
    progressCallback: CorrectionProgress | None = None,
) -> CameraCorrectionPlan:
    """Plan a fixed offset from one import's recorded reference and trusted time."""
    root = Path(archiveRoot).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"archive root is not a directory: {root}")
    manifest = _correctionManifestRead(manifestPath)
    assets = _correctionAssetsSelect(manifest, selectedFiles, referenceFile)
    journals = correctionJournalRead(databasePath)
    selected = sorted(asset["relativePath"] for asset in assets)
    matching = [
        item
        for item in journals
        if item.get("importId") == manifest["importId"]
        and item["selectedFiles"] == selected
    ]
    active = next((item for item in matching if not correctionCompleted(item)), None)
    if active:
        assets = active.get("inputEvidence", assets)
    else:
        for item in reversed(matching):
            if correctionRequestMatches(item, root, referenceFile, actualAt, reason):
                replay = correctionReplay(item)
                if replay is not None:
                    return CameraCorrectionPlan(replay)
        assets = correctionImportCurrent(assets, journals)
    return cameraCorrectionEvidencePlan(
        assets,
        root=root,
        referenceFile=referenceFile,
        actualAt=actualAt,
        reason=reason,
        databasePath=databasePath,
        importId=manifest["importId"],
        previous=journals,
        manifestPath=manifestPath,
        cardId=manifest.get("source", {}).get("cardId"),
        snapshotId=manifest.get("snapshotId"),
        progressCallback=progressCallback,
    )


def cameraCorrectionEvidencePlan(
    assets: list[dict],
    *,
    root: Path,
    referenceFile: str,
    actualAt: datetime,
    reason: str,
    databasePath: Path,
    importId: str | None,
    manifestPath: Path | None = None,
    cardId: int | None = None,
    snapshotId: str | None = None,
    sourceRoot: Path | None = None,
    scopeEvidence: dict | None = None,
    previous: list[dict] | None = None,
    progressCallback: CorrectionProgress | None = None,
) -> CameraCorrectionPlan:
    """Plan verified import or observed folder evidence through the same policy."""
    reference = next(
        (asset for asset in assets if asset["relativePath"] == referenceFile), None
    )
    if reference is None:
        raise ValueError("reference file must belong to the selected correction scope")
    if reference.get("error"):
        raise ValueError(f"reference evidence unavailable: {reference['error']}")
    recordedAt = _correctionRawRead(reference)
    try:
        rule = CaptureDateCorrection(recordedAt, actualAt, reason)
    except ValueError as error:

        def evidenceDescribe(value: datetime) -> str:
            offset = value.utcoffset()
            state = (
                "naive; no UTC offset"
                if offset is None
                else f"aware; UTC offset {offset}"
            )
            return f"{value.isoformat()} ({state})"

        raise ValueError(
            f"{error}; recorded reference {referenceFile}: {evidenceDescribe(recordedAt)}; "
            f"supplied actual: {evidenceDescribe(actualAt)}; "
            f"capture source: {reference.get('timestampEvidence') or reference.get('dateSource', 'unknown')}"
        ) from error
    previous = correctionJournalRead(databasePath) if previous is None else previous
    provenance = {
        "importId": importId,
        "archiveRoot": str(root),
        "referenceFile": referenceFile,
        "referenceRecordedAt": rule.referenceRecordedAt.isoformat(),
        "referenceActualAt": actualAt.isoformat(),
        "reason": reason,
        "selectedFiles": sorted(asset["relativePath"] for asset in assets),
    }
    provenance.update(scopeEvidence or {})
    provenance["inputEvidence"] = assets
    provenance["predecessorRuleIds"] = correctionPredecessors(assets, previous)
    active = next(
        (
            item
            for item in previous
            if not correctionCompleted(item)
            and correctionRequestMatches(item, root, referenceFile, actualAt, reason)
            and item["selectedFiles"] == provenance["selectedFiles"]
            and item.get("inputEvidence", assets) == assets
            and item.get("scopeId") == provenance.get("scopeId")
            and item.get("importId") == importId
        ),
        None,
    )
    provenance["operationId"] = (
        active.get("operationId") if active else uuid.uuid4().hex
    )
    ruleId = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    if active and not active.get("operationId"):
        ruleId = active["ruleId"]
    payload = dict(
        provenance,
        schemaVersion=4,
        ruleId=ruleId,
        correctionMethod="fixed-offset",
        offsetMicroseconds=rule.offsetMicroseconds,
        offsetSeconds=str(Decimal(rule.offsetMicroseconds) / Decimal(1_000_000)),
        cardId=cardId,
        snapshotId=snapshotId,
        importManifest=str(Path(manifestPath).resolve()) if manifestPath else None,
        observedRuleIds=[item["ruleId"] for item in previous],
        assets=[],
    )
    for index, asset in enumerate(assets):
        if progressCallback:
            progressCallback(
                index, len(assets), f"Checking/hashing {asset['relativePath']}"
            )
        payload["assets"].append(
            _correctionAssetPlan(
                asset,
                rule,
                root,
                ruleId,
                previous,
                databasePath,
                assets,
                sourceRoot=sourceRoot,
                folderScope=scopeEvidence is not None,
            )
        )
    _correctionTargetsCheck(payload["assets"])
    if progressCallback:
        progressCallback(len(assets), len(assets), "Correction plan complete")
    return CameraCorrectionPlan(payload)


## validation


def _correctionManifestRead(path: Path) -> dict:
    manifest = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or not isinstance(manifest.get("importId"), str)
        or not manifest["importId"].strip()
    ):
        raise ValueError(
            "a confirmed import manifest with a durable importId is required"
        )
    assets = manifest.get("assets")
    if (
        not isinstance(assets, list)
        or not assets
        or not all(isinstance(asset, dict) for asset in assets)
    ):
        raise ValueError("import manifest has no usable asset records")
    if not isinstance(manifest.get("source", {}), dict):
        raise ValueError("invalid import source identity")
    return manifest


def _correctionAssetsSelect(
    manifest: dict, selected: tuple[str, ...], reference: str
) -> list[dict]:
    assets = manifest["assets"]
    names = [asset.get("relativePath") for asset in assets]
    if any(not isinstance(name, str) or not name for name in names) or len(
        set(names)
    ) != len(names):
        raise ValueError("manifest relative paths must be non-empty and unique")
    wanted = set(selected) if selected else set(names)
    if reference not in wanted or not wanted.issubset(names):
        raise ValueError(
            "reference and selected files must belong to this import scope"
        )
    # Select same-stem recorded companions together, even for an explicit subset.
    groups = {(Path(name).parent, Path(name).stem.lower()) for name in wanted}
    return [
        asset
        for asset in assets
        if (
            Path(asset["relativePath"]).parent,
            Path(asset["relativePath"]).stem.lower(),
        )
        in groups
    ]


def _correctionRawRead(asset: dict) -> datetime:
    if asset.get("dateSource") not in {
        "metadata",
        "filename",
        "correction",
        "companion",
    }:
        raise ValueError(
            "no usable camera capture timestamp (filesystem fallback is not an anchor)"
        )
    value = asset.get("rawCaptureAt") or asset.get("captureAt")
    if not isinstance(value, str) or "T" not in value and " " not in value:
        raise ValueError("missing or invalid recorded capture timestamp")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("missing or invalid recorded capture timestamp") from error


def _correctionPathValidate(path: Path, root: Path) -> None:
    if not path.is_absolute() or not path.is_relative_to(root) or path == root:
        raise ValueError(f"file is outside the explicit archive root: {path}")
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError(f"symlink in archive path: {candidate}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"file escapes archive root: {path}")


## assets


def _correctionAssetPlan(
    asset: dict,
    rule: CaptureDateCorrection,
    root: Path,
    ruleId: str,
    previous: list[dict],
    databasePath: Path,
    selectedAssets: list[dict],
    *,
    sourceRoot: Path | None = None,
    folderScope: bool = False,
) -> dict:
    record = dict(
        relativePath=asset["relativePath"],
        sourcePath=asset.get("destinationPath", ""),
        rawCaptureAt=asset.get("captureAt"),
        correctedCaptureAt=None,
        dateSource=asset.get("rawDateSource") or asset.get("dateSource"),
        destinationPath=None,
        outcome="blocked",
    )
    for key in (
        "timestampEvidencePath",
        "observedCaptureAt",
        "observedDateSource",
        "timestampEvidence",
    ):
        if key in asset:
            record[key] = asset[key]
    try:
        if asset.get("error"):
            raise ValueError(asset["error"])
        raw = _correctionRawRead(asset)
        corrected = rule.apply(raw).correctedCaptureAt
        source = Path(record["sourcePath"])
        destination = (
            root
            / f"{corrected.year:04d}"
            / f"{corrected.month:02d}"
            / f"{corrected.day:02d}"
            / source.name
        )
        _correctionPathValidate(source, sourceRoot or root)
        _correctionPathValidate(destination, root)
        _correctionCompanionsCheck(source, selectedAssets)
        digest = asset.get("destinationDigest") or asset.get("sourceDigest")
        if (
            asset.get("outcome")
            not in ({"observed"} if folderScope else {"copied", "alreadyPresent"})
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise ValueError("verified SHA-256 import evidence is required")
        record.update(
            rawCaptureAt=raw.isoformat(),
            correctedCaptureAt=corrected.isoformat(),
            destinationPath=str(destination),
            sha256=digest,
            destinationExisted=destination.exists(),
        )
        prior = _correctionPriorFind(
            previous,
            asset["relativePath"],
            ruleId,
            sourcePath=str(source),
        )
        if prior and prior["destinationPath"] != str(destination):
            raise ValueError("recorded correction destination differs")
        if prior and prior.get("metadataVersion"):
            record.update(
                {key: prior[key] for key in CORRECTION_EVIDENCE_KEYS if key in prior}
            )
        if not source.exists() and prior:
            backup = prior.get("backupPath")
            source = Path(backup) if backup and Path(backup).exists() else destination
        sourceDigest = digest
        if source == destination and record.get("destinationSha256"):
            observed = mediaHashCalculate(source, algorithm="sha256")
            if observed == record["destinationSha256"]:
                sourceDigest = observed
        # A corrected destination and an untouched source intentionally differ.
        _correctionDigestVerify(source, sourceDigest)
        if (
            record.get("destinationSha256")
            and sourceDigest == record["destinationSha256"]
        ):
            from .cameraCorrectionMetadata import correctionMetadataVerify

            correctionMetadataVerify(source, record)
        _correctionExistingValidate(source, destination, record, databasePath)
        if destination.exists():
            observed = mediaHashCalculate(destination, algorithm="sha256")
            if observed not in {digest, record.get("destinationSha256")}:
                raise ValueError(f"SHA-256 conflict or changed content: {destination}")
        if not record.get("metadataVersion"):
            record.update(correctionMetadataPlan(source, record, rule.offset))
        record["outcome"] = (
            "applied"
            if prior and prior["outcome"] == "applied" and prior.get("metadataVersion")
            else ("alreadyPresent" if destination.exists() else "relocate")
        )
        if prior:
            record["destinationExisted"] = prior["destinationExisted"]
        record["currentPath"] = str(source)
    except (OSError, ValueError, TypeError) as error:
        record["error"] = str(error)
    return record


def _correctionDigestVerify(path: Path, digest: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or non-regular archive file: {path}")
    if mediaHashCalculate(path, algorithm="sha256") != digest:
        raise ValueError(f"SHA-256 conflict or changed content: {path}")


def _correctionPriorFind(
    previous: list[dict], relativePath: str, ruleId: str, sourcePath: str | None = None
) -> dict | None:
    found = None
    for payload in previous:
        completed = correctionCompleted(payload)
        if completed and payload["ruleId"] != ruleId:
            continue
        for asset in payload["assets"]:
            paths = {asset["sourcePath"]}
            if not completed:
                paths.add(asset["destinationPath"])
            matches = (
                sourcePath in paths
                if sourcePath
                else asset["relativePath"] == relativePath
            )
            if not matches:
                continue
            if payload["ruleId"] != ruleId:
                raise ValueError(
                    "selected file already belongs to a different unfinished correction; review its journal"
                )
            found = asset
    return found


def _correctionTargetsCheck(assets: list[dict]) -> None:
    """Reject intra-plan collisions and companions split across archive days."""
    destinations: dict[str, dict] = {}
    groups: dict[tuple[str, str], dict] = {}
    for asset in assets:
        if asset["outcome"] == "blocked":
            continue
        path = Path(asset["sourcePath"])
        group = (str(path.parent), path.stem.lower())
        previous = destinations.get(asset["destinationPath"])
        companion = groups.get(group)
        if previous and (
            previous["sha256"] != asset["sha256"]
            or previous["correctedCaptureAt"] != asset["correctedCaptureAt"]
        ):
            for item in (previous, asset):
                item.update(
                    outcome="blocked",
                    error="selected files collide at corrected destination",
                )
        if (
            companion
            and Path(companion["destinationPath"]).parent
            != Path(asset["destinationPath"]).parent
        ):
            for item in (companion, asset):
                item.update(
                    outcome="blocked",
                    error="companion timestamps disagree on corrected archive day",
                )
        destinations[asset["destinationPath"]] = asset
        groups[group] = asset


def _correctionCompanionsCheck(source: Path, selected: list[dict]) -> None:
    """Do not strand known camera sidecars absent from the selected evidence."""
    if not source.parent.is_dir():
        return
    recorded = {item.get("destinationPath") for item in selected}
    for sibling in source.parent.iterdir():
        if sibling.stem.lower() != source.stem.lower() or sibling == source:
            continue
        if (
            sibling.suffix.lower()
            in {
                ".srt",
                ".nmea",
                ".png",
                ".webp",
                ".thm",
                ".lrv",
                ".xml",
                ".jpg",
                ".jpeg",
                ".cr3",
                ".mp4",
                ".mov",
            }
            and str(sibling) not in recorded
        ):
            raise ValueError(f"companion lacks selected import evidence: {sibling}")


def _correctionExistingValidate(
    source: Path, destination: Path, asset: dict, databasePath: Path
) -> None:
    """Reject conflicting destination chronology without reserving input paths."""
    # Source provenance explains the input; it does not constrain a new target time.
    for candidate in ({destination} if destination != source else set()):
        existing = (
            correctionTimestampRead(candidate, databasePath=databasePath)
            if candidate.exists()
            else None
        )
        if existing and (
            existing["correctedCaptureAt"] != asset["correctedCaptureAt"]
            or existing["rawCaptureAt"] != asset["rawCaptureAt"]
        ):
            raise ValueError("file already has a different authoritative correction")
