#!/usr/bin/env python3
"""Entry point with camera-card lifecycle and import-history dispatch."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import constants
from . import mainLegacy as _legacy
from .cameraImport import cameraImportHistory, cameraImportHistorySummary
from .cameraImportHistoryView import cameraImportHistoryFullSummary

APP_VERSION = _legacy.APP_VERSION
APP_CONFIG_FILE = _legacy.APP_CONFIG_FILE
buildParser = _legacy.buildParser
getLogger = _legacy.getLogger
logging = _legacy.logging


def __getattr__(name: str):
    return getattr(_legacy, name)


def _cameraImportParserBuild() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera import",
        description="plan/import camera media or inspect recorded imports",
    )
    parser.add_argument(
        "-s", "--source", dest="importSource", metavar="SOURCE",
        help="mounted card or copied card directory for a new import",
    )
    parser.add_argument(
        "--list", dest="listHistory", action="store_true",
        help="list all previous confirmed camera imports",
    )
    parser.add_argument(
        "--full", action="store_true", help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--card", type=int,
        help="without SOURCE show this card's full import manifest; with SOURCE assert card identity",
    )
    parser.add_argument("--gopro-destination")
    parser.add_argument("--drone-destination")
    parser.add_argument("--dashcam-destination")
    parser.add_argument("--manifest-directory")
    parser.add_argument("--include-gopro-companions", action="store_true")
    parser.add_argument(
        "-y", "--confirm", "--y", dest="confirm", action="store_true",
        help="confirm execution — actually make changes (default is dry-run)",
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def _cameraInventoryListParserBuild() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera inventory",
        description="list registered camera cards",
    )
    parser.add_argument("--list", dest="listInventory", action="store_true", required=True)
    parser.add_argument("--card", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--full", action="store_true", help=argparse.SUPPRESS)
    return parser


def _cameraInventoryListRun(arguments: Sequence[str]) -> int:
    from .cameraInventoryList import (
        cameraInventoryFullSummary,
        cameraInventoryList,
        cameraInventoryListSummary,
    )

    parser = _cameraInventoryListParserBuild()
    args = parser.parse_args(list(arguments))
    if args.card is not None and args.card < 1:
        parser.error("--card must be a positive integer")

    entries = cameraInventoryList(
        databasePath=constants.CAMERA_INVENTORY_DATABASE,
        cardId=args.card,
    )
    if args.card is not None:
        if not entries:
            print(f"CAMERA CARD {args.card:03d}\n\nNo card registered.\n", end="")
            return 1
        print(cameraInventoryFullSummary(entries[0]), end="")
        return 0
    print(cameraInventoryListSummary(entries), end="")
    return 0


def _cameraInventoryCardRun(arguments: Sequence[str]) -> int:
    """Show all known details for one numbered card."""

    from .cameraInventoryList import cameraInventoryFullSummary, cameraInventoryList

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera inventory",
        description="show all known details for one numbered card",
    )
    parser.add_argument("--card", type=int, required=True)
    parser.add_argument("--full", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(list(arguments))
    if args.card < 1:
        parser.error("--card must be a positive integer")
    entries = cameraInventoryList(
        databasePath=constants.CAMERA_INVENTORY_DATABASE,
        cardId=args.card,
    )
    if not entries:
        print(f"CAMERA CARD {args.card:03d}\n\nNo card registered.\n", end="")
        return 1
    print(cameraInventoryFullSummary(entries[0]), end="")
    return 0


def _cameraInventoryFormatParserBuild() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera inventory",
        description="format an archived numbered card and record a fresh empty inventory",
    )
    parser.add_argument("--format", dest="formatTarget", metavar="CARD", required=True)
    parser.add_argument("-y", "--confirm", "--y", dest="confirm", action="store_true")
    return parser


def _cameraInventoryFormatRun(arguments: Sequence[str]) -> int:
    from .cameraFormat import cameraFormatRun, cameraFormatSummary

    parser = _cameraInventoryFormatParserBuild()
    args = parser.parse_args(list(arguments))
    try:
        plan = cameraFormatRun(
            args.formatTarget,
            dryRun=not args.confirm,
            databasePath=constants.CAMERA_INVENTORY_DATABASE,
        )
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(cameraFormatSummary(plan, dryRun=not args.confirm), end="")
    return 0


def _cameraInventoryLocationParserBuild() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera inventory",
        description="show or update the physical location of a numbered card",
    )
    parser.add_argument("--card", type=int, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--location", action="store_true")
    group.add_argument("--set-location", metavar="LOCATION")
    parser.add_argument("-y", "--confirm", "--y", dest="confirm", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def _cameraInventoryLocationRun(arguments: Sequence[str]) -> int:
    from .cardLocation import cardLocationGet, cardLocationSet, cardLocationSummary

    parser = _cameraInventoryLocationParserBuild()
    args = parser.parse_args(list(arguments))
    if args.card < 1:
        parser.error("--card must be a positive integer")
    if args.location:
        print(cardLocationSummary(args.card, cardLocationGet(args.card)), end="")
        return 0
    location = cardLocationSet(args.card, args.set_location, dryRun=not args.confirm)
    print(cardLocationSummary(args.card, location), end="")
    print(f"  Persisted:        {'yes' if args.confirm else 'no (dry-run)'}")
    return 0


def _cameraImportHistoryRun(arguments: Sequence[str]) -> int:
    """Show all imports or the full per-file manifest history for one card."""

    parser = _cameraImportParserBuild()
    args = parser.parse_args(list(arguments))
    if args.card is not None and args.card < 1:
        parser.error("--card must be a positive integer")
    if args.importSource is not None:
        parser.error("history queries do not accept -s/--source")
    if args.confirm:
        parser.error("--confirm is not valid for import history")
    if args.include_gopro_companions:
        parser.error("--include-gopro-companions is not valid for import history")
    if args.gopro_destination or args.drone_destination or args.dashcam_destination:
        parser.error("archive destination overrides are not valid for import history")
    if not args.listHistory and args.card is None:
        parser.error("use --list for all imports or --card ID for one card")

    manifestDirectory = Path(
        args.manifest_directory or constants.applicationStateDirectory() / "cameraImports"
    )
    records = cameraImportHistory(manifestDirectory, cardId=args.card)
    if args.card is not None:
        print(cameraImportHistoryFullSummary(records, cardId=args.card), end="")
        return 0
    print(cameraImportHistorySummary(records), end="")
    return 0


def _cameraImportArgumentsValidate(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.full:
        parser.error("--full is no longer required; use --card ID")
    if args.importSource is None:
        parser.error("-s/--source is required for a new import")
    source = Path(args.importSource).expanduser()
    if not source.is_dir():
        parser.error(f"source directory does not exist: {source}")
    if args.card is not None and args.card < 1:
        parser.error("--card must be a positive integer")


def _cameraImportLegacyArguments(arguments: Sequence[str]) -> list[str]:
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
    amount = float(max(value, 0))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            return f"{int(amount)} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024.0
    return f"{amount:.1f} TiB"


def _cameraImportProgressRenderer() -> Callable[[int, int, str], None]:
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
        progressText = f" {percent:3d}%  {_byteDisplay(copiedBytes)} / {_byteDisplay(totalBytes)}"
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
    _legacy.getLogger = getLogger
    _legacy.APP_CONFIG_FILE = APP_CONFIG_FILE


def _getSummaryReportPath(sourcePath: str, mode: str) -> Path:
    _legacyGlobalsSync()
    return _legacy._getSummaryReportPath(sourcePath, mode)


def _cameraImportRunPatch(
    expectedCardId: Optional[int],
    *,
    progressCallback: Optional[Callable[[int, int, str], None]] = None,
):
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


def _cameraImportPlainSummaryRun(arguments: Sequence[str], *, expectedCardId: Optional[int] = None) -> int:
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


def _cameraImportConfirmedRun(arguments: Sequence[str], *, expectedCardId: Optional[int] = None) -> int:
    progressCallback = _cameraImportProgressRenderer()
    cameraImportModule, originalRun, patchedRun = _cameraImportRunPatch(
        expectedCardId, progressCallback=progressCallback
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


def _inventoryCardQuery(arguments: Sequence[str]) -> bool:
    """Return True only for the pure read-only ``--card ID`` detail form."""

    values = list(arguments)
    if "--card" not in values and not any(value.startswith("--card=") for value in values):
        return False
    actionOptions = {
        "-s", "--source", "--brand", "--reassign", "--location", "--set-location",
        "--format", "--list", "-y", "--confirm", "--y", "--auto", "--clean",
        "--refresh", "--rescan",
    }
    return not any(
        value in actionOptions or any(value.startswith(option + "=") for option in actionOptions if option.startswith("--"))
        for value in values
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if len(arguments) >= 2 and arguments[:2] == ["camera", "inventory"]:
        inventoryArguments = arguments[2:]
        if "--format" in inventoryArguments:
            return _cameraInventoryFormatRun(inventoryArguments)
        if "--list" in inventoryArguments:
            return _cameraInventoryListRun(inventoryArguments)
        if "--location" in inventoryArguments or "--set-location" in inventoryArguments:
            return _cameraInventoryLocationRun(inventoryArguments)
        if _inventoryCardQuery(inventoryArguments):
            return _cameraInventoryCardRun(inventoryArguments)

    if len(arguments) >= 2 and arguments[:2] == ["camera", "import"]:
        importArguments = arguments[2:]
        parser = _cameraImportParserBuild()
        if "--help" in importArguments or "-h" in importArguments:
            parser.parse_args(importArguments)
        parsed = parser.parse_args(importArguments)
        if parsed.listHistory or (parsed.card is not None and parsed.importSource is None):
            return _cameraImportHistoryRun(importArguments)
        _cameraImportArgumentsValidate(parser, parsed)
        legacyArguments = _cameraImportLegacyArguments(arguments)
        if parsed.confirm:
            return _cameraImportConfirmedRun(legacyArguments, expectedCardId=parsed.card)
        return _cameraImportPlainSummaryRun(legacyArguments, expectedCardId=parsed.card)

    _legacyGlobalsSync()
    return _legacy.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
