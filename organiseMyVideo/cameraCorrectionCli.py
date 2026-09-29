"""Presentation and argparse adapter for camera capture-time correction."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

from . import constants
from .cameraCorrection import cameraCorrectionPlan
from .cameraCorrectionExecution import cameraCorrectionExecute
from .terminalProgress import TerminalProgress


def cameraCorrectionArgumentsAdd(parser: argparse.ArgumentParser) -> None:
    """Register explicit scope, trusted anchor and archive-root options."""
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument(
        "-s",
        "--source",
        type=Path,
        help="folder of existing camera media, scanned recursively without requiring import history",
    )
    scope.add_argument(
        "--import-manifest",
        type=Path,
        help="one confirmed camera import JSON manifest (scope is never all uses of a card)",
    )
    parser.add_argument(
        "-r",
        "--root",
        type=Path,
        required=True,
        help="destination archive root above YYYY/MM/DD; source folders may be outside it",
    )
    parser.add_argument(
        "-R",
        "--reference",
        dest="reference_file",
        metavar="FILE",
        required=True,
        help="file whose recorded capture time provides the correction anchor",
    )
    parser.add_argument(
        "-a",
        "--actual",
        dest="actual_at",
        metavar="DATETIME",
        type=_correctionTimestampParse,
        required=True,
        help="actual capture date/time of the reference file",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="reason and trusted evidence/source for this correction",
    )
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        default=[],
        help="select a source-relative or manifest-relative filename (repeatable); defaults to all supported files and includes same-stem companions",
    )


def cameraCorrectionCliRun(args: argparse.Namespace) -> int:
    """Print the full plan before any confirmed mutation, with clean interruption."""
    progress = TerminalProgress(0, "Capture correction")

    def report(completed: int, total: int, name: str) -> None:
        progress.total = total
        progress.render(completed, name)
        if not progress.enabled and (completed == 0 or completed == total):
            print(f"Capture correction: {completed}/{total} {name}", file=sys.stderr)

    try:
        planner = cameraCorrectionPlan
        scopePath = args.import_manifest
        if args.source is not None:
            from .cameraCorrectionFolder import cameraCorrectionFolderPlan

            planner = cameraCorrectionFolderPlan
            scopePath = args.source
        plan = planner(
            scopePath,
            archiveRoot=args.root,
            referenceFile=args.reference_file,
            actualAt=args.actual_at,
            reason=args.reason,
            selectedFiles=tuple(args.file),
            databasePath=constants.MEDIA_CATALOGUE_DATABASE,
            progressCallback=report,
        )
        progress.finish()
        print(cameraCorrectionSummary(plan.payload), flush=True)
        if plan.blocked:
            print(cameraCorrectionBlockedSummary(plan.payload))
            return 2
        result = cameraCorrectionExecute(
            plan,
            databasePath=constants.MEDIA_CATALOGUE_DATABASE,
            manifestDirectory=constants.applicationStateDirectory() / "cameraImports",
            dryRun=not args.confirm,
            progressCallback=report,
        )
        progress.finish()
        print(
            "Correction complete."
            if args.confirm
            else "Preview only. Use -y/--confirm to apply this scope."
        )
        if result.get("manifestPath"):
            print(f"Manifest: {result['manifestPath']}")
        return 0
    except KeyboardInterrupt:
        progress.finish()
        print(
            "\nCapture correction interrupted. Re-run the same command to review/resume recorded work.",
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        progress.finish()
        print(f"organiseMyVideo camera correct-time: error: {error}", file=sys.stderr)
        return 2
    finally:
        progress.finish()


def cameraCorrectionSummary(payload: dict) -> str:
    """Distinguish raw evidence, effective dates, paths and conflicts for review."""
    offset = payload["offsetMicroseconds"]
    assets = payload["assets"]
    blocked = [asset for asset in assets if asset.get("outcome") == "blocked"]
    lines = [
        "CAMERA CAPTURE-TIME CORRECTION",
        "",
        (
            f"Folder scope: {payload['scopeId']}\nSource: {payload['sourceRoot']}"
            if payload.get("scopeType") == "folder"
            else f"Import: {payload['importId']}"
        ),
        f"Reference: {payload['referenceFile']}",
        f"Anchor: {payload['referenceRecordedAt']} -> {payload['referenceActualAt']}",
        f"Offset: {'+' if offset >= 0 else '-'}{abs(offset)} microseconds ({timedelta(microseconds=offset)})",
        f"Reason/source: {payload['reason']}",
        f"Affected files: {len(assets)}",
        f"Ready:          {len(assets) - len(blocked)}",
        f"Blocked:        {len(blocked)}",
    ]
    if blocked:
        lines.extend(["", "Correction cannot proceed:"])
        for asset in blocked:
            lines.append(
                f"  {asset['relativePath']} - {_correctionIssuePlain(asset.get('error'))}"
            )
    for asset in assets:
        lines.extend(
            [
                "",
                f"  {asset['outcome']}: {asset['relativePath']}",
                f"    Original:  {asset['rawCaptureAt']} ({asset['dateSource']})",
                f"    Corrected: {asset['correctedCaptureAt']}",
                f"    Current:   {asset.get('currentPath', asset['sourcePath'])}",
                f"    Proposed:  {asset['destinationPath']}",
                f"    Embedded:  {len(asset.get('correctedMetadata', {}))} timestamp fields to verify",
                f"    mtime:     {asset.get('mtimePolicy', 'unavailable')} (shift only when earlier than corrected capture)",
            ]
        )
        if asset.get("timestampEvidencePath"):
            lines.append(f"    Timestamp from: {asset['timestampEvidencePath']}")
        if asset.get("error"):
            lines.append(f"    Issue:     {_correctionIssuePlain(asset['error'])}")
    if payload.get("excludedPaths"):
        lines.append("\nUnselected/unsupported files retained:")
        lines.extend(f"  {path}" for path in payload["excludedPaths"])
    return "\n".join(lines)


def cameraCorrectionBlockedSummary(payload: dict) -> str:
    """Explain blocked work in operator language and state the safe next action."""
    blocked = [
        asset for asset in payload["assets"] if asset.get("outcome") == "blocked"
    ]
    lines = [
        "",
        "CORRECTION BLOCKED",
        "",
        f"Blocked files: {len(blocked)} of {len(payload['assets'])}. Correction cannot proceed.",
    ]
    for asset in blocked:
        lines.extend(
            [
                "",
                asset["relativePath"],
                f"  {_correctionIssuePlain(asset.get('error'))}",
                f"  Current:  {asset.get('currentPath', asset['sourcePath'])}",
                f"  Proposed: {asset['destinationPath']}",
            ]
        )
        expected = asset.get("sourceDigest") or asset.get("expectedDigest")
        current = asset.get("currentDigest")
        destination = asset.get("destinationDigest")
        if expected:
            lines.append(f"  Expected SHA-256:    {expected}")
        if current:
            lines.append(f"  Current SHA-256:     {current}")
        if destination:
            lines.append(f"  Destination SHA-256: {destination}")
    lines.extend(
        [
            "",
            "No files have been changed by this invocation.",
            "Review the blocking file(s) above before confirming the correction.",
        ]
    )
    return "\n".join(lines)


def _correctionIssuePlain(error: str | None) -> str:
    """Translate planner diagnostics into concise operator-facing explanations."""
    if not error:
        return "The correction planner reported a conflict."
    lower = error.lower()
    if "sha-256 conflict" in lower or "changed content" in lower:
        return (
            "The file content differs from the evidence recorded for this correction "
            "or from a file already present at the proposed destination."
        )
    if "destination" in lower and ("different" in lower or "conflict" in lower):
        return "A different file already exists at the proposed destination."
    return error


def _correctionTimestampParse(value: str) -> datetime:
    if "T" not in value and " " not in value:
        raise argparse.ArgumentTypeError("anchor must include both date and time")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "anchor must be a valid ISO date/time"
        ) from error
