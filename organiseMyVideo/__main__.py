#!/usr/bin/env python3
"""Entry point with camera-import history dispatch layered over the established CLI."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import constants
from . import mainLegacy as _legacy
from .cameraImport import cameraImportHistory, cameraImportHistorySummary
from .cameraInventoryList import cameraInventoryList, cameraInventoryListSummary

# Keep the established CLI API visible to tests and callers while the camera
# import history syntax is layered on top of it.
APP_VERSION = _legacy.APP_VERSION
APP_CONFIG_FILE = _legacy.APP_CONFIG_FILE
buildParser = _legacy.buildParser
getLogger = _legacy.getLogger
logging = _legacy.logging


def __getattr__(name: str):
    """Delegate established CLI helpers to the preserved implementation."""

    return getattr(_legacy, name)


def _cameraImportParserBuild() -> argparse.ArgumentParser:
    """Return the camera-import parser including history options."""

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera import",
        description="plan, import, or list supported camera media imports",
    )
    parser.add_argument(
        "-s",
        "--source",
        dest="importSource",
        metavar="SOURCE",
        help="mounted card or copied card directory; required unless --list is used",
    )
    parser.add_argument(
        "--list",
        dest="listHistory",
        action="store_true",
        help="list previous confirmed camera imports",
    )
    parser.add_argument(
        "--card",
        type=int,
        help="with --list, show imports for this numbered card only",
    )
    parser.add_argument(
        "--gopro-destination",
        help="override the configured GoPro archive destination",
    )
    parser.add_argument(
        "--drone-destination",
        help="override the configured Drone archive destination",
    )
    parser.add_argument(
        "--dashcam-destination",
        help="override the configured Dashcam archive destination",
    )
    parser.add_argument(
        "--manifest-directory",
        help="override the camera-import manifest directory",
    )
    parser.add_argument(
        "--include-gopro-companions",
        action="store_true",
        help="retain GoPro LRV and THM helper files",
    )
    parser.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
        help="confirm execution — actually make changes (default is dry-run)",
    )
    parser.add_argument("--debug", action="store_true", help="enable debug-level logging")
    parser.add_argument("--quiet", action="store_true", help="show errors only")
    return parser


def _cameraInventoryListParserBuild() -> argparse.ArgumentParser:
    """Return camera-inventory help including the list option."""

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera inventory",
        description="catalogue a numbered camera card or list inventoried cards",
    )
    parser.add_argument(
        "SOURCE",
        nargs="?",
        help="mounted card or copied card directory",
    )
    parser.add_argument(
        "-s",
        "--source",
        dest="inventorySourceOption",
        metavar="SOURCE",
        help="mounted card or copied card directory; alternative to positional SOURCE",
    )
    parser.add_argument(
        "--card",
        type=int,
        help="numeric ID assigned to this card (required on first scan)",
    )
    parser.add_argument(
        "--reassign",
        action="store_true",
        help="allow --card to replace an existing on-card ID (requires --confirm)",
    )
    parser.add_argument(
        "--brand",
        help="card brand to store on the card, for example SanDisk or Transcend",
    )
    parser.add_argument(
        "--list",
        dest="listInventory",
        action="store_true",
        help="list the latest snapshot for every numbered card",
    )
    parser.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
        help="confirm execution — actually make changes (default is dry-run)",
    )
    parser.add_argument("--debug", action="store_true", help="enable debug-level logging")
    parser.add_argument("--quiet", action="store_true", help="show errors only")
    return parser


def _cameraInventoryListRun(arguments: Sequence[str]) -> int:
    """List the latest camera-card inventory state."""

    parser = _cameraInventoryListParserBuild()
    args = parser.parse_args(list(arguments))
    if not args.listInventory:
        parser.error("--list is required for camera inventory listing")
    if args.SOURCE is not None or args.inventorySourceOption is not None:
        parser.error("--list does not use a source path")
    if args.card is not None:
        parser.error("--card is not valid with camera inventory --list")
    if args.reassign or args.brand or args.confirm:
        parser.error("--reassign, --brand, and --confirm are not valid with --list")
    manifestDirectory = constants.applicationStateDirectory() / "cameraImports"
    records = cameraInventoryList(
        constants.CAMERA_INVENTORY_DATABASE,
        manifestDirectory=manifestDirectory,
    )
    isTty = getattr(sys.stdout, "isatty", None)
    useColour = bool(callable(isTty) and isTty())
    print(cameraInventoryListSummary(records, useColour=useColour), end="")
    return 0


def _cameraImportHistoryRun(arguments: Sequence[str]) -> int:
    """List recorded camera-import manifests, optionally for one card."""

    parser = _cameraImportParserBuild()
    args = parser.parse_args(list(arguments))
    if not args.listHistory:
        parser.error("--list is required for camera import history")
    if args.card is not None and args.card < 1:
        parser.error("--card must be a positive integer")
    if args.importSource is not None:
        parser.error("--list identifies a card with --card, not -s/--source")
    if args.confirm:
        parser.error("--confirm is not valid with --list")
    if args.include_gopro_companions:
        parser.error("--include-gopro-companions is not valid with --list")
    if args.gopro_destination or args.drone_destination or args.dashcam_destination:
        parser.error("archive destination overrides are not valid with --list")

    manifestDirectory = Path(
        args.manifest_directory
        or constants.applicationStateDirectory() / "cameraImports"
    )
    records = cameraImportHistory(manifestDirectory, cardId=args.card)
    print(cameraImportHistorySummary(records, cardId=args.card), end="")
    return 0


def _byteDisplay(value: int) -> str:
    """Return a compact binary byte count for progress output."""

    amount = float(max(value, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{amount:.1f} TiB"


def _cameraImportProgressRenderer() -> Callable[[int, int, str], None]:
    """Return a TTY renderer for aggregate camera-import byte progress."""

    finished = False

    def _render(copiedBytes: int, totalBytes: int, filename: str) -> None:
        nonlocal finished
        if finished or totalBytes <= 0:
            return
        isTty = getattr(sys.stderr, "isatty", None)
        if not callable(isTty) or not isTty():
            return

        copiedBytes = max(0, min(copiedBytes, totalBytes))
        percent = int((copiedBytes * 100) / totalBytes)
        progressText = (
            f" {percent:3d}%  {_byteDisplay(copiedBytes)} / {_byteDisplay(totalBytes)}"
        )
        suffix = f"  {filename}" if filename else ""
        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        barWidth = max(10, min(40, columns - len(progressText) - len(suffix) - 14))
        filled = int((copiedBytes * barWidth) / totalBytes)
        bar = "#" * filled + "-" * (barWidth - filled)
        line = f"Importing [{bar}]{progressText}{suffix}"
        if len(line) >= columns:
            line = line[: max(1, columns - 1)]
        sys.stderr.write("\r" + line)
        sys.stderr.flush()
        if copiedBytes >= totalBytes:
            sys.stderr.write("\n")
            sys.stderr.flush()
            finished = True

    return _render


def _legacyGlobalsSync() -> None:
    """Propagate patchable compatibility globals into the preserved CLI module."""

    _legacy.getLogger = getLogger
    _legacy.APP_CONFIG_FILE = APP_CONFIG_FILE


def _getSummaryReportPath(sourcePath: str, mode: str) -> Path:
    """Return the summary path using this module's patchable application state."""

    _legacyGlobalsSync()
    return _legacy._getSummaryReportPath(sourcePath, mode)


def _cameraImportConfirmedRun(arguments: Sequence[str]) -> int:
    """Delegate confirmed camera import while injecting terminal progress."""

    from . import cameraImport as cameraImportModule

    originalRun = cameraImportModule.cameraImportRun
    progressCallback = _cameraImportProgressRenderer()

    def _runWithProgress(**kwargs):
        kwargs["progressCallback"] = progressCallback
        return originalRun(**kwargs)

    cameraImportModule.cameraImportRun = _runWithProgress
    try:
        _legacyGlobalsSync()
        return _legacy.main(arguments)
    finally:
        cameraImportModule.cameraImportRun = originalRun


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command-line application and return a process status."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) >= 2 and arguments[:2] == ["camera", "inventory"]:
        inventoryArguments = arguments[2:]
        if "--help" in inventoryArguments or "-h" in inventoryArguments:
            _cameraInventoryListParserBuild().parse_args(inventoryArguments)
        if "--list" in inventoryArguments:
            return _cameraInventoryListRun(inventoryArguments)
    if len(arguments) >= 2 and arguments[:2] == ["camera", "import"]:
        importArguments = arguments[2:]
        if "--help" in importArguments or "-h" in importArguments:
            _cameraImportParserBuild().parse_args(importArguments)
        if "--list" in importArguments:
            return _cameraImportHistoryRun(importArguments)
        if any(option in importArguments for option in ("-y", "--y", "--confirm")):
            return _cameraImportConfirmedRun(arguments)

    _legacyGlobalsSync()
    return _legacy.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
