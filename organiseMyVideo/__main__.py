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
        "-s",
        "--source",
        dest="importSource",
        metavar="SOURCE",
        help="mounted card or copied card directory for a new import",
    )
    parser.add_argument(
        "--list",
        dest="listHistory",
        action="store_true",
        help="list all previous confirmed camera imports",
    )
    parser.add_argument("--full", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--card",
        type=int,
        help="without SOURCE show this card's full import manifest; with SOURCE assert card identity",
    )
    parser.add_argument("--gopro-destination")
    parser.add_argument("--drone-destination")
    parser.add_argument("--dashcam-destination")
    parser.add_argument("--photo-destination")
    parser.add_argument("--video-destination")
    parser.add_argument("--manifest-directory")
    parser.add_argument("--include-gopro-companions", action="store_true")
    parser.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
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
    parser.add_argument(
        "--list", dest="listInventory", action="store_true", required=True
    )
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
    parser.add_argument(
        "--format",
        action="store_true",
        required=True,
        help="format the numbered card selected with --card",
    )
    parser.add_argument(
        "--card",
        required=True,
        metavar="CARD",
        help="numbered card to format, for example 18",
    )
    parser.add_argument("-y", "--confirm", "--y", dest="confirm", action="store_true")
    return parser


def _cameraInventoryFormatRun(arguments: Sequence[str]) -> int:
    from .cameraFormat import cameraFormatRun, cameraFormatSummary

    parser = _cameraInventoryFormatParserBuild()
    args = parser.parse_args(list(arguments))
    try:
        plan = cameraFormatRun(
            args.card,
            dryRun=not args.confirm,
            databasePath=constants.CAMERA_INVENTORY_DATABASE,
        )
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))
    print(cameraFormatSummary(plan, dryRun=not args.confirm), end="")
    return 0


def _cameraInventoryLocationParserBuild() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera location",
        description="show or update the physical location of a numbered card",
    )
    parser.add_argument("--card", type=int, required=True)
    parser.add_argument(
        "--set",
        "--set-location",
        dest="setLocation",
        metavar="LOCATION",
        help="set the card's current physical location",
    )
    parser.add_argument("--location", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def _cameraInventoryLocationRun(arguments: Sequence[str]) -> int:
    from .cardLocation import cardLocationGet, cardLocationSet, cardLocationSummary

    parser = _cameraInventoryLocationParserBuild()
    args = parser.parse_args(list(arguments))
    if args.card < 1:
        parser.error("--card must be a positive integer")
    if args.setLocation is None:
        print(cardLocationSummary(args.card, cardLocationGet(args.card)), end="")
        return 0
    location = cardLocationSet(args.card, args.setLocation, dryRun=False)
    print(cardLocationSummary(args.card, location), end="")
    print("  Persisted:        yes")
    return 0


def _cameraImportHistoryRun(arguments: Sequence[str]) -> int:
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
    if (
        args.gopro_destination
        or args.drone_destination
        or args.dashcam_destination
        or args.photo_destination
        or args.video_destination
    ):
        parser.error("archive destination overrides are not valid for import history")
    if not args.listHistory and args.card is None:
        parser.error("use --list for all imports or --card ID for one card")

    manifestDirectory = Path(
        args.manifest_directory
        or constants.applicationStateDirectory() / "cameraImports"
    )
    records = cameraImportHistory(manifestDirectory, cardId=args.card)
    if args.card is not None:
        print(cameraImportHistoryFullSummary(records, cardId=args.card), end="")
        return 0
    print(cameraImportHistorySummary(records), end="")
    return 0


def _cameraImportArgumentsValidate(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
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
    lastName = ""

    def _render(copiedBytes: int, totalBytes: int, filename: str) -> None:
        nonlocal finished, lastName
        if finished or totalBytes <= 0:
            return
        copiedBytes = max(0, min(copiedBytes, totalBytes))
        isTty = getattr(sys.stderr, "isatty", None)
        if not callable(isTty) or not isTty():
            if not lastName and copiedBytes == 0:
                print(
                    f"Importing camera media: {_byteDisplay(totalBytes)} to copy...",
                    file=sys.stderr,
                )
            if filename and filename != lastName:
                print(f"Importing {filename}...", file=sys.stderr)
                lastName = filename
            if copiedBytes >= totalBytes:
                print(
                    f"Importing camera media: {_byteDisplay(copiedBytes)} / {_byteDisplay(totalBytes)} complete.",
                    file=sys.stderr,
                )
                finished = True
            return
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
        sys.stderr.write("\r\x1b[2K" + line)
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


def _cameraImportPlainSummaryRun(
    arguments: Sequence[str], *, expectedCardId: Optional[int] = None
) -> int:
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
    arguments: Sequence[str], *, expectedCardId: Optional[int] = None
) -> int:
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
    cardIndexes: set[int] = set()
    for index, value in enumerate(values):
        if value == "--card":
            if index + 1 >= len(values):
                return False
            cardIndexes.update({index, index + 1})
        elif value.startswith("--card="):
            cardIndexes.add(index)
        elif value == "--full":
            cardIndexes.add(index)
    if not cardIndexes:
        return False
    return all(index in cardIndexes for index in range(len(values)))


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)

    if arguments and arguments[0] == "camera":
        from .cameraCli import cameraCliRun

        return cameraCliRun(arguments[1:])

    _legacyGlobalsSync()
    return _legacy.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
