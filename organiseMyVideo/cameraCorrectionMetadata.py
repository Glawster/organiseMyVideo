"""Embedded metadata and filesystem-time policy for journalled camera correction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from organiseMediaStudio.metadata.captureTags import (
    captureTagsPlan,
    captureTagsVerify,
    captureTagsWrite,
)

_METADATA_SUFFIXES = {".jpg", ".jpeg", ".thm", ".mp4", ".mov", ".lrv"}
_SIDECAR_SUFFIXES = {".srt", ".xml", ".nmea", ".png", ".webp"}
CORRECTION_EVIDENCE_KEYS = (
    "metadataVersion",
    "filesystemBefore",
    "filesystemAfter",
    "originalMetadata",
    "correctedMetadata",
    "originalMtimeNs",
    "resultingMtimeNs",
    "mtimePolicy",
    "originalSha256",
    "destinationSha256",
    "workPath",
    "backupPath",
    "metadataState",
    "abandonedStages",
)


def correctionMetadataPlan(path: Path, asset: dict, offset: timedelta) -> dict:
    """Preserve original tags and mtime before any destination write."""
    correctedAt = datetime.fromisoformat(asset["correctedCaptureAt"])
    if path.suffix.lower() in _METADATA_SUFFIXES:
        tags = captureTagsPlan(path, offset, correctedAt)
    elif path.suffix.lower() in _SIDECAR_SUFFIXES:
        tags = {"original": {}, "corrected": {}}
    else:
        raise ValueError(f"no safe embedded metadata writer for {path.suffix}")
    record = dict(
        metadataVersion=1,
        filesystemBefore={
            "sizeBytes": path.stat().st_size,
            "mtimeNs": path.stat().st_mtime_ns,
        },
        originalMetadata=tags["original"],
        correctedMetadata=tags["corrected"],
        mtimePolicy="preserve",
        originalSha256=asset["sha256"],
        metadataState="untouched",
    )
    originalMtime = path.stat().st_mtime_ns
    # POSIX mtime is an instant. Naive capture times use the host local zone
    # only for this comparison; embedded evidence stays timezone-naive.
    elapsed = correctedAt.astimezone(timezone.utc) - datetime(
        1970, 1, 1, tzinfo=timezone.utc
    )
    captureInstant = (
        (elapsed.days * 86400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds
    ) * 1000
    offsetNs = (
        (offset.days * 86400 + offset.seconds) * 1_000_000 + offset.microseconds
    ) * 1000
    if originalMtime < captureInstant and offsetNs:
        record.update(
            mtimePolicy="shift",
            originalMtimeNs=originalMtime,
            resultingMtimeNs=originalMtime + offsetNs,
        )
    return record


def correctionMtimeVerify(path: Path, asset: dict) -> None:
    """Check a changed mtime, or preservation against a still-available original."""
    expected = asset.get("resultingMtimeNs")
    if expected is None:
        for key in ("sourcePath", "backupPath"):
            candidate = Path(asset[key]) if asset.get(key) else None
            if candidate and candidate != path and candidate.exists():
                expected = candidate.stat().st_mtime_ns
                break
    if expected is not None and path.stat().st_mtime_ns != expected:
        raise ValueError(f"corrected destination mtime changed: {path}")


def correctionMetadataWrite(path: Path, asset: dict) -> None:
    """Write absolute target tags on an already verified private copy."""
    if asset["correctedMetadata"]:
        captureTagsWrite(path, asset["correctedMetadata"])


def correctionMetadataVerify(path: Path, asset: dict) -> None:
    """Read embedded metadata back independently of the OMV catalogue."""
    if asset["correctedMetadata"]:
        captureTagsVerify(path, asset["correctedMetadata"])
