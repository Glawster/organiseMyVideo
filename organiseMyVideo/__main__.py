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

APP_VERSION = _legacy.APP_VERSION
APP_CONFIG_FILE = _legacy.APP_CONFIG_FILE
buildParser = _legacy.buildParser
getLogger = _legacy.getLogger
logging = _legacy.logging


def __getattr__(name: str):
    """Delegate established CLI helpers to the preserved implementation."""

    return getattr(_legacy, name)


def _cameraImportParserBuild() -> argparse.ArgumentParser:
    """Return the camera-import parser including history and identity options."""

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
        help=(
            "expected numbered card ID for an import; with --list, show imports "
            "for this card only"
        ),
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


def _cameraInventoryLocationParserBuild() -> argparse.ArgumentParser:
    """Return the parser for card-location metadata commands."""

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera inventory",
        description="show or update the physical location of a numbered card",
    )
    parser.add_argument("--card", type=int, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--location",
        action="store_true",
        help="show the currently stored physical location",
    )
    group.add_argument(
        "--set-location",
        metavar="LOCATION",
        help="set the current physical location, for example 'Car JSZ5017'",
    )
    parser.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
        help="confirm the location update; default is dry-run",
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def _cameraInventoryLocationRun(arguments: Sequence[str]) -> int:
    """Show or update persistent location metadata for one card."""

    from .cardLocation import cardLocationGet, cardLocationSet, cardLocationSummary

    parser = _cameraInventoryLocationParserBuild()
    args = parser.parse_args(list(arguments))
    if args.card < 1:
        parser.error("--card must be a positive integer")

    if args.location:
        print(cardLocationSummary(args.card, cardLocationGet(args.card)), end="")
        return 0

    location = cardLocationSet(
        args.card,
        args.set_location,
        dryRun=not args.confirm,
    )
    print(cardLocationSummary(args.card, location), end="")
    print(f"  Persisted:        {'yes' if args.confirm else 'no (dry-run)'}")
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


def _cameraImportArgumentsValidate(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    """Validate non-history camera-import arguments handled by this entry point."""

    if args.importSource is None:
        parser.error("-s/--source is required unless --list is used")
    source = Path(args.importSource).expanduser()
    if not source.is_dir():
        parser.error(f"source directory does not exist: {source}")
    if args.card is not None and args.card < 1:
        parser.error("--card must be a positive integer")


def _cameraImportLegacyArguments(arguments: Sequence[str]) -> list[str]:
    """Remove entry-point-only ``--card`` before delegating to the legacy parser."""

    cleaned: list[str] = []
    values = list(arguments)
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--card":
            index += 2
            continue
        if value.startswith("--card="):
            index += 1
            continue
        cleaned.append(value)
        index += 1
    return cleaned


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


def _cameraImportRunPatch(
    expectedCardId: Optional[int],
    *,
    progressCallback: Optional[Callable[[int, int, str], None]] = None,
):
    """Return a cameraImportRun wrapper carrying CLI identity/progress context."""

    from . import cameraImport as cameraImportModule

    originalRun = cameraImportModule.cameraImportRun

    def _run(**kwargs):
        if expectedCardId is not None:
            source = Path(kwargs["source"])
            actualCardId = cameraImportModule.cameraCardIdResolve(source)
            if actualCardId is None:
                raise RuntimeError(
                    f"camera source has no numbered card label; register card {expectedCardId} first with: "
                    f"organiseMyVideo camera inventory -s {source} --card {expectedCardId} --confirm"
                )
            kwargs["expectedCardId"] = expectedCardId
        if progressCallback is not None:
            kwargs["progressCallback"] = progressCallback
        return originalRun(**kwargs)

    return cameraImportModule, originalRun, _run


def _cameraImportPlainSummaryRun(
    arguments: Sequence[str],
    *,
    expectedCardId: Optional[int] = None,
) -> int:
    """Delegate camera import while rendering its summary without an ASCII box."""

    cameraImportModule, originalRun, patchedRun = _cameraImportRunPatch(expectedCardId)
    originalDrawBox = _legacy.drawBox
    cameraImportModule.cameraImportRun = patchedRun
    _legacy.drawBox = lambda text: print(text, end="" if text.endswith("\n") else "\n")
    try:
        _legacyGlobalsSync()
        return _legacy.main(arguments)
    finally:
        cameraImportModule.cameraImportRun = originalRun
        _legacy.drawBox = originalDrawBox


def _cameraImportConfirmedRun(
    arguments: Sequence[str],
    *,
    expectedCardId: Optional[int] = None,
) -> int:
    """Delegate confirmed camera import with progress and a plain final summary."""

    progressCallback = _cameraImportProgressRenderer()
    cameraImportModule, originalRun, patchedRun = _cameraImportRunPatch(
        expectedCardId,
        progressCallback=progressCallback,
    )
    originalDrawBox = _legacy.drawBox
    cameraImportModule.cameraImportRun = patchedRun
    _legacy.drawBox = lambda text: print(text, end="" if text.endswith("\n") else "\n")
    try:
        _legacyGlobalsSync()
        return _legacy.main(arguments)
    finally:
        cameraImportModule.cameraImportRun = originalRun
        _legacy.drawBox = originalDrawBox


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the command-line application and return a process status."""

    arguments = list(sys.argv[1:] if argv is None else argv)

    if len(arguments) >= 2 and arguments[:2] == ["camera", "inventory"]:
        inventoryArguments = arguments[2:]
        if "--location" in inventoryArguments or "--set-location" in inventoryArguments:
            return _cameraInventoryLocationRun(inventoryArguments)

    if len(arguments) >= 2 and arguments[:2] == ["camera", "import"]:
        importArguments = arguments[2:]
        parser = _cameraImportParserBuild()
        if "--help" in importArguments or "-h" in importArguments:
            parser.parse_args(importArguments)
        if "--list" in importArguments:
            return _cameraImportHistoryRun(importArguments)

        parsed = parser.parse_args(importArguments)
        _cameraImportArgumentsValidate(parser, parsed)
        legacyArguments = _cameraImportLegacyArguments(arguments)
        if parsed.confirm:
            return _cameraImportConfirmedRun(
                legacyArguments,
                expectedCardId=parsed.card,
            )
        return _cameraImportPlainSummaryRun(
            legacyArguments,
            expectedCardId=parsed.card,
        )

    _legacyGlobalsSync()
    return _legacy.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
