"""Public camera CLI built around card lifecycle actions rather than inventory internals."""

from __future__ import annotations

import argparse
import errno
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable, Sequence

from . import constants
from . import mainLegacy as _legacy

MARKETED_VOLUME_GIGABYTES = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048)


def cameraCliRun(arguments: Sequence[str]) -> int:
    """Run one public ``organiseMyVideo camera`` command."""

    parser = _cameraParserBuild()
    args = parser.parse_args(list(arguments))

    if args.cameraAction == "list":
        return _cameraListRun()
    if args.cameraAction == "show":
        return _cameraShowRun(args.card)
    if args.cameraAction == "scan":
        return _cameraScanRun(args)
    if args.cameraAction == "archive":
        return _cameraArchiveRun(args)
    if args.cameraAction == "history":
        return _cameraHistoryRun(args.card, check=args.check)
    if args.cameraAction == "migrate":
        return _cameraMigrateRun(args)
    if args.cameraAction == "format":
        return _cameraFormatRun(args)
    if args.cameraAction == "location":
        return _cameraLocationRun(args)

    parser.error("camera action is required")
    return 2


def _cameraParserBuild() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organiseMyVideo camera",
        description="Manage numbered removable media, archive camera footage, inspect history, and maintain the camera archive.",
    )
    subparsers = parser.add_subparsers(dest="cameraAction", required=True)

    subparsers.add_parser(
        "list",
        help="list registered cards and removable volumes",
        description="List every registered camera card and removable volume known to organiseMyVideo.",
    )

    showParser = subparsers.add_parser(
        "show",
        help="show one card's details",
        description="Show the stored identity, capacity, contents, and lifecycle details for one numbered card.",
    )
    showParser.add_argument("--card", type=_positiveCardId, required=True)

    scanParser = subparsers.add_parser(
        "scan",
        help="scan or register a mounted camera card or USB volume",
        description="Inspect a mounted card or USB volume, identify its contents, and optionally persist a new inventory snapshot.",
    )
    scanParser.add_argument(
        "-s",
        "--source",
        required=True,
        metavar="SOURCE",
        help="mounted card, USB volume, or copied card directory",
    )
    scanParser.add_argument(
        "--card",
        type=_positiveCardId,
        help="numeric card ID; optional when the volume is already labelled",
    )
    scanParser.add_argument(
        "--reassign",
        action="store_true",
        help="replace an existing on-volume ID with --card",
    )
    _confirmArgumentAdd(scanParser)

    archiveParser = subparsers.add_parser(
        "archive",
        help="scan the source then archive supported camera media",
        description="Scan a mounted camera card, then copy and verify supported media into the configured archive hierarchy.",
    )
    archiveParser.add_argument(
        "-s",
        "--source",
        required=True,
        metavar="SOURCE",
        help="mounted removable volume containing camera media",
    )
    archiveParser.add_argument(
        "--card",
        type=_positiveCardId,
        help="numeric card ID; optional when the volume is already labelled",
    )
    _confirmArgumentAdd(archiveParser)

    historyParser = subparsers.add_parser(
        "history",
        help="show or verify recorded camera archive history",
        description="Show recorded archive history, or verify recorded destinations against the current archive with --check.",
    )
    historyParser.add_argument("--card", type=_positiveCardId)
    historyParser.add_argument(
        "--check",
        action="store_true",
        help="verify recorded archive assets and report ok, moved, missing, ambiguous, or changed",
    )

    migrateParser = subparsers.add_parser(
        "migrate",
        help="reconcile legacy camera archive month folders safely",
        description="Compare legacy YYYY/MM-MMM/DD camera folders with canonical YYYY/MM/DD folders and remove only SHA-256-verified duplicates. Dry-run is the default.",
    )
    migrateParser.add_argument(
        "--root",
        default="/mnt/myVideo/Video/GoPro",
        metavar="PATH",
        help="camera archive root to inspect (default: /mnt/myVideo/Video/GoPro)",
    )
    _confirmArgumentAdd(migrateParser)

    formatParser = subparsers.add_parser(
        "format",
        help="format an archived card and record it as empty",
        description="Format a numbered card only after its current contents are safely archived, then record a fresh empty inventory state.",
    )
    formatParser.add_argument("--card", type=_positiveCardId, required=True)
    _confirmArgumentAdd(formatParser)

    locationParser = subparsers.add_parser(
        "location",
        help="show or set a card's physical location",
        description="Show or update the recorded physical storage location for one numbered card.",
    )
    locationParser.add_argument("--card", type=_positiveCardId, required=True)
    locationParser.add_argument(
        "--set",
        dest="setLocation",
        metavar="LOCATION",
        help="set the current physical location",
    )

    return parser


def _confirmArgumentAdd(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-y",
        "--confirm",
        "--y",
        dest="confirm",
        action="store_true",
        help="confirm execution; default is dry-run",
    )


def _positiveCardId(value: str) -> int:
    try:
        cardId = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("card ID must be a positive integer") from error
    if cardId < 1:
        raise argparse.ArgumentTypeError("card ID must be a positive integer")
    return cardId


def _sourceValidate(parser: argparse.ArgumentParser, source: str) -> Path:
    sourcePath = Path(source).expanduser().resolve()
    if not sourcePath.is_dir():
        parser.error(f"source directory does not exist: {sourcePath}")
    return sourcePath


def _cameraListRun() -> int:
    from .cameraInventoryList import cameraInventoryList, cameraInventoryListSummary

    entries = cameraInventoryList(databasePath=constants.CAMERA_INVENTORY_DATABASE)
    print(cameraInventoryListSummary(entries), end="")
    return 0


def _cameraShowRun(cardId: int) -> int:
    from .cameraInventoryList import cameraInventoryFullSummary, cameraInventoryList

    entries = cameraInventoryList(
        databasePath=constants.CAMERA_INVENTORY_DATABASE,
        cardId=cardId,
    )
    if not entries:
        print(f"CAMERA CARD {cardId:03d}\n\nNo card registered.\n", end="")
        return 1
    print(cameraInventoryFullSummary(entries[0]), end="")
    return 0


def _cameraHistoryRun(cardId: int | None, *, check: bool = False) -> int:
    manifestDirectory = constants.applicationStateDirectory() / "cameraImports"
    if check:
        from .cameraHistory import cameraHistoryCheck, cameraHistorySummary

        results = cameraHistoryCheck(manifestDirectory, cardId=cardId)
        print(cameraHistorySummary(results, cardId=cardId), end="")
        return 0

    if cardId is None:
        print("organiseMyVideo camera history: error: --card is required unless --check is used")
        return 2

    from .cameraImport import cameraImportHistory
    from .cameraImportHistoryView import cameraImportHistoryFullSummary

    records = cameraImportHistory(manifestDirectory, cardId=cardId)
    print(cameraImportHistoryFullSummary(records, cardId=cardId), end="")
    return 0


def _cameraMigrateProgressRenderer() -> Callable[[int, int, str], None]:
    """Return a compact terminal progress renderer for archive migration scans."""

    finished = False

    def _render(completed: int, total: int, filename: str) -> None:
        nonlocal finished
        if finished:
            return
        isTty = getattr(sys.stderr, "isatty", None)
        if not callable(isTty) or not isTty():
            if completed == 0:
                print(f"Scanning legacy camera archive: {total} file(s) to inspect...", file=sys.stderr)
            elif total and completed == total:
                print(f"Scanning legacy camera archive: {completed}/{total} complete.", file=sys.stderr)
                finished = True
            return
        if total <= 0:
            sys.stderr.write("Scanning legacy camera archive: no legacy files found.\n")
            sys.stderr.flush()
            finished = True
            return
        completed = max(0, min(completed, total))
        percent = int((completed * 100) / total)
        suffix = f"  {filename}" if filename else ""
        columns = shutil.get_terminal_size(fallback=(100, 24)).columns
        prefix = f"Scanning [{percent:3d}%] {completed}/{total}"
        line = prefix + suffix
        if len(line) >= columns:
            line = line[: max(1, columns - 1)]
        sys.stderr.write("\r" + line)
        sys.stderr.flush()
        if completed >= total:
            sys.stderr.write("\n")
            sys.stderr.flush()
            finished = True

    return _render


def _cameraMigrateRun(args: argparse.Namespace) -> int:
    """Reconcile hash-identical legacy ``MM-MMM`` month-folder duplicates."""

    from .cameraMigration import (
        cameraMonthDuplicatesReconcile,
        cameraMonthDuplicatesSummary,
    )

    root = Path(args.root).expanduser()
    try:
        result = cameraMonthDuplicatesReconcile(
            root,
            dryRun=not args.confirm,
            progressCallback=_cameraMigrateProgressRenderer(),
        )
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"organiseMyVideo camera migrate: error: {error}")
        return 2
    print(cameraMonthDuplicatesSummary(result), end="")
    return 0


def _volumeKindResolve(record) -> str:
    """Use camera layout/identity evidence even when a camera card has no media files."""

    hasCameraIdentity = any(
        value
        for value in (
            record.manufacturer,
            record.cameraModel,
            record.cameraSerial,
            record.firmwareVersion,
            record.cameraWifiMac,
            record.goproCardId,
        )
    )
    return "sd" if record.cameraKinds or hasCameraIdentity else "usb"


def _marketedGigabytesResolve(totalBytes: int | None, stored: int | None) -> int | None:
    if totalBytes:
        for gigabytes in MARKETED_VOLUME_GIGABYTES:
            ratio = totalBytes / (gigabytes * 1_000_000_000)
            if 0.90 <= ratio <= 1.02:
                return gigabytes
    return stored


def _markerWriteFailure(error: OSError, sourcePath: Path, markerPath: str | None) -> bool:
    """Return True when persistence failed only because the mounted volume is read-only."""

    if error.errno == errno.EROFS:
        return True
    if markerPath is None or error.filename is None:
        return False
    try:
        failedPath = Path(error.filename).resolve()
        markerRoot = Path(markerPath).resolve().parent
    except OSError:
        return False
    return failedPath.parent == markerRoot and markerRoot == sourcePath.resolve()


def _cameraScanExecute(args: argparse.Namespace):
    """Scan and optionally persist one volume, retaining DB state for read-only media."""

    from .cameraInventory import CameraInventory, cameraInventorySummary

    parser = argparse.ArgumentParser(prog="organiseMyVideo camera scan")
    sourcePath = _sourceValidate(parser, args.source)
    service = CameraInventory(
        dryRun=not args.confirm,
        databasePath=constants.CAMERA_INVENTORY_DATABASE,
    )
    try:
        record = service.inventoryScan(
            sourcePath,
            args.card,
            reassign=bool(getattr(args, "reassign", False)),
        )
        record = replace(
            record,
            volumeKind=_volumeKindResolve(record),
            cardRatedGigabytes=_marketedGigabytesResolve(
                record.capacity.totalBytes,
                record.cardRatedGigabytes,
            ),
        )
        markerWarning = None
        if args.confirm:
            try:
                service.inventoryPersist(record)
            except OSError as error:
                if not _markerWriteFailure(error, sourcePath, record.cardLabelPath):
                    raise
                if getattr(args, "reassign", False):
                    raise RuntimeError(
                        "cannot reassign a card ID while the volume filesystem is read-only"
                    ) from error
                databaseRecord = replace(
                    record,
                    cardLabelPath=None,
                    previousLabelPaths=(),
                )
                service.inventoryPersist(databaseRecord)
                markerWarning = (
                    f"WARNING: {sourcePath} is read-only; "
                    f"{Path(record.cardLabelPath).name} could not be written. "
                    "The inventory snapshot was stored in the database."
                )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"organiseMyVideo camera scan: error: {error}")
        return 1, None

    print(
        cameraInventorySummary(
            record,
            persisted=bool(args.confirm),
            databasePath=constants.CAMERA_INVENTORY_DATABASE,
        ),
        end="",
    )
    if markerWarning:
        print(markerWarning)
    return 0, record


def _cameraScanRun(args: argparse.Namespace) -> int:
    status, _record = _cameraScanExecute(args)
    return status


def _cameraArchiveRun(args: argparse.Namespace) -> int:
    """Scan first, then run the established camera-import service."""

    status, record = _cameraScanExecute(args)
    if status != 0 or record is None:
        return status
    if not record.cameraKinds:
        print(
            "organiseMyVideo camera archive: error: "
            "archive expects camera media, no camera media found"
        )
        return 2

    legacyArguments = [
        "camera",
        "import",
        "-s",
        str(Path(args.source).expanduser().resolve()),
    ]
    if args.confirm:
        legacyArguments.append("--confirm")

    from . import __main__ as applicationMain

    if args.confirm:
        return applicationMain._cameraImportConfirmedRun(
            legacyArguments,
            expectedCardId=record.cardId,
        )
    return applicationMain._cameraImportPlainSummaryRun(
        legacyArguments,
        expectedCardId=record.cardId,
    )


def _cameraFormatRun(args: argparse.Namespace) -> int:
    from .cameraFormat import cameraFormatRun, cameraFormatSummary

    try:
        plan = cameraFormatRun(
            str(args.card),
            dryRun=not args.confirm,
            databasePath=constants.CAMERA_INVENTORY_DATABASE,
        )
    except (RuntimeError, ValueError) as error:
        print(f"organiseMyVideo camera format: error: {error}")
        return 2
    print(cameraFormatSummary(plan, dryRun=not args.confirm), end="")
    return 0


def _cameraLocationRun(args: argparse.Namespace) -> int:
    from .cardLocation import cardLocationGet, cardLocationSet, cardLocationSummary

    if args.setLocation is None:
        print(
            cardLocationSummary(
                args.card,
                cardLocationGet(
                    args.card,
                    databasePath=constants.CAMERA_INVENTORY_DATABASE,
                ),
            ),
            end="",
        )
        return 0

    location = cardLocationSet(
        args.card,
        args.setLocation,
        databasePath=constants.CAMERA_INVENTORY_DATABASE,
        dryRun=False,
    )
    print(cardLocationSummary(args.card, location), end="")
    print("  Persisted:        yes")
    return 0


def _legacyGlobalsSync() -> None:
    """Use the wrapper's patchable logger/config globals in legacy execution."""

    try:
        from . import __main__ as applicationMain

        _legacy.getLogger = applicationMain.getLogger
        _legacy.APP_CONFIG_FILE = applicationMain.APP_CONFIG_FILE
    except (AttributeError, ImportError):
        pass
