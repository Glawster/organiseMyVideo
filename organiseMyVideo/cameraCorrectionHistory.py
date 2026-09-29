"""Separate frozen recovery evidence from completed transformation provenance."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from organiseMediaStudio.identity.hash import mediaHashCalculate


def correctionCompleted(payload: dict) -> bool:
    """Recognise sealed records and fully cleaned legacy completions."""
    return bool(payload.get("completedAt")) or (
        payload.get("schemaVersion", 1) < 4
        and bool(payload.get("assets"))
        and all(asset["outcome"] == "applied" for asset in payload["assets"])
        and not any(
            asset.get(key) and Path(asset[key]).exists()
            for asset in payload["assets"]
            for key in ("workPath", "backupPath")
        )
    )


def correctionImportCurrent(assets: list[dict], journals: list[dict]) -> list[dict]:
    """Follow verified transformation identities, then read the resulting files afresh."""
    from .cameraCorrectionFolder import _folderAssetRead, _folderCompanionsResolve

    records = []
    refreshed = False
    for original in assets:
        path = original["destinationPath"]
        digest = original.get("destinationDigest") or original.get("sourceDigest")
        followed = set()
        while True:
            matches = [
                (journal, asset)
                for journal in journals
                if correctionCompleted(journal) and journal["ruleId"] not in followed
                for asset in journal["assets"]
                if asset["sourcePath"] == path and asset["sha256"] == digest
            ]
            if not matches:
                break
            # Unchanged bytes (zero offsets and sidecars) can have several steps
            # at one path. Follow their explicit ancestry rather than guessing.
            candidates = {journal["ruleId"] for journal, _ in matches}
            roots = [
                (journal, asset)
                for journal, asset in matches
                if not candidates.intersection(journal.get("predecessorRuleIds", []))
            ]
            if len(roots) != 1:
                raise ValueError("ambiguous correction history for imported media")
            journal, asset = roots[0]
            followed.add(journal["ruleId"])
            path = asset["destinationPath"]
            digest = asset.get("destinationSha256", asset["sha256"])
        if not followed and original.get("dateSource") != "correction":
            records.append(copy.deepcopy(original))
            continue
        refreshed = True
        current = _folderAssetRead(Path(path).parent, Path(path).name)
        current.update(relativePath=original["relativePath"], outcome="copied")
        records.append(current)
    if refreshed:
        _folderCompanionsResolve(records)
    return records


def correctionPredecessors(assets: list[dict], journals: list[dict]) -> list[str]:
    """Link current input bytes to completed outputs without reserving their paths."""
    identities = {
        (
            asset["destinationPath"],
            asset.get("destinationDigest") or asset.get("sourceDigest"),
        )
        for asset in assets
    }
    return sorted(
        journal["ruleId"]
        for journal in journals
        if correctionCompleted(journal)
        and any(
            (asset["destinationPath"], asset.get("destinationSha256", asset["sha256"]))
            in identities
            for asset in journal["assets"]
        )
    )


def correctionReplay(payload: dict) -> dict | None:
    """Return an unchanged completed record only while its output still verifies."""
    from .cameraCorrectionMetadata import (
        correctionMetadataVerify,
        correctionMtimeVerify,
    )

    if not correctionCompleted(payload) or any(
        not asset.get("metadataVersion") for asset in payload["assets"]
    ):
        return None
    try:
        for asset in payload["assets"]:
            path = Path(asset["destinationPath"])
            if path.is_symlink() or not path.is_file():
                return None
            if mediaHashCalculate(path, algorithm="sha256") != asset.get(
                "destinationSha256", asset["sha256"]
            ):
                return None
            state = asset.get("filesystemAfter")
            if state and (
                path.stat().st_size != state["sizeBytes"]
                or path.stat().st_mtime_ns != state["mtimeNs"]
            ):
                return None
            correctionMetadataVerify(path, asset)
            correctionMtimeVerify(path, asset)
    except (OSError, ValueError):
        return None
    return copy.deepcopy(payload)


def correctionRequestMatches(
    payload: dict, root: Path, reference: str, actual: datetime, reason: str
) -> bool:
    """Identify retries by the explicit operator request, not just its source path."""
    return (
        payload["archiveRoot"] == str(root)
        and payload["referenceFile"] == reference
        and payload["referenceActualAt"] == actual.isoformat()
        and payload["reason"] == reason
    )
