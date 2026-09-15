"""Safe formatting workflow for archived numbered removable media."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .cameraInventory import CameraInventory
from .cameraInventoryList import cameraInventoryList
from .constants import CAMERA_INVENTORY_DATABASE, applicationStateDirectory, cameraCardLabelFilename

CARD_TARGET = re.compile(r"^(?:card)?0*(\d+)$", re.IGNORECASE)
CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CameraFormatPlan:
    """Resolved destructive format operation for one numbered card."""

    cardId: int
    mountPath: Path
    devicePath: Path
    filesystemType: str
    volumeLabel: str


def cameraFormatTargetId(value: str) -> int:
    """Parse ``card18`` / ``card018`` / ``18`` into durable card ID 18."""

    match = CARD_TARGET.fullmatch(str(value).strip())
    if match is None:
        raise ValueError("format target must be a card name such as card18")
    cardId = int(match.group(1))
    if cardId < 1:
        raise ValueError("card ID must be a positive integer")
    return cardId


def cameraFormatPlan(
    target: str,
    *,
    databasePath: Optional[Path] = None,
    manifestDirectory: Optional[Path] = None,
    mountRoots: Optional[Sequence[Path]] = None,
    commandRunner: Optional[CommandRunner] = None,
) -> CameraFormatPlan:
    """Resolve and validate a format request without changing the medium."""

    cardId = cameraFormatTargetId(target)
    database = Path(databasePath or CAMERA_INVENTORY_DATABASE)
    manifests = Path(manifestDirectory or applicationStateDirectory() / "cameraImports")
    entries = cameraInventoryList(
        databasePath=database,
        cardId=cardId,
        manifestDirectory=manifests,
    )
    if not entries or entries[0].inventory is None:
        raise RuntimeError(f"card {cardId:03d} has no inventory snapshot")
    entry = entries[0]
    location = (entry.location or "").strip()
    if location:
        raise RuntimeError(
            f"card {cardId:03d} has active location '{location}'; clear the location before formatting"
        )
    if entry.inventory.capacity.contentBytes > 0 and not entry.archived:
        raise RuntimeError(
            f"card {cardId:03d} latest content is not archived; format refused"
        )

    mountPath = _mountedCardFind(cardId, mountRoots=mountRoots)
    runner = commandRunner or _commandRun
    deviceText = _commandText(runner, ["findmnt", "-n", "-o", "SOURCE", "--target", str(mountPath)])
    filesystemType = _commandText(
        runner, ["findmnt", "-n", "-o", "FSTYPE", "--target", str(mountPath)]
    ).lower()
    devicePath = Path(deviceText)
    if not str(devicePath).startswith("/dev/"):
        raise RuntimeError(f"refusing non-device mount source: {devicePath}")
    if filesystemType not in {"exfat", "vfat"}:
        raise RuntimeError(
            f"unsupported card filesystem '{filesystemType}'; expected exfat or vfat"
        )
    _removableDeviceRequire(devicePath, runner)

    return CameraFormatPlan(
        cardId=cardId,
        mountPath=mountPath,
        devicePath=devicePath,
        filesystemType=filesystemType,
        volumeLabel=f"Card{cardId}",
    )


def cameraFormatRun(
    target: str,
    *,
    dryRun: bool = True,
    databasePath: Optional[Path] = None,
    manifestDirectory: Optional[Path] = None,
    mountRoots: Optional[Sequence[Path]] = None,
    commandRunner: Optional[CommandRunner] = None,
) -> CameraFormatPlan:
    """Format one safely archived card and persist a fresh empty snapshot."""

    database = Path(databasePath or CAMERA_INVENTORY_DATABASE)
    runner = commandRunner or _commandRun
    plan = cameraFormatPlan(
        target,
        databasePath=database,
        manifestDirectory=manifestDirectory,
        mountRoots=mountRoots,
        commandRunner=runner,
    )
    if dryRun:
        return plan

    _commandChecked(runner, ["udisksctl", "unmount", "-b", str(plan.devicePath)])
    if plan.filesystemType == "exfat":
        formatCommand = [
            "sudo", "mkfs.exfat", "-n", plan.volumeLabel, str(plan.devicePath)
        ]
    else:
        formatCommand = [
            "sudo", "mkfs.vfat", "-F", "32", "-n", plan.volumeLabel, str(plan.devicePath)
        ]
    _commandChecked(runner, formatCommand)
    mountResult = _commandChecked(runner, ["udisksctl", "mount", "-b", str(plan.devicePath)])
    mounted = _mountPathFromUdisks(mountResult.stdout)
    if mounted is None or not mounted.is_dir():
        mounted = _mountedLabelFind(plan.volumeLabel, mountRoots=mountRoots)
    if mounted is None or not mounted.is_dir():
        raise RuntimeError(
            f"card {plan.cardId:03d} formatted but remounted path could not be resolved"
        )

    inventory = CameraInventory(dryRun=False, databasePath=database)
    record = inventory.inventoryScan(mounted, plan.cardId)
    inventory.inventoryPersist(record)
    return plan


def cameraFormatSummary(plan: CameraFormatPlan, *, dryRun: bool) -> str:
    """Return a compact format-plan/result summary."""

    mode = "DRY-RUN" if dryRun else "CONFIRMED"
    result = "would format" if dryRun else "formatted"
    return (
        f"CAMERA CARD FORMAT — {mode}\n\n"
        f"Card:        {plan.cardId:03d}\n"
        f"Mount:       {plan.mountPath}\n"
        f"Device:      {plan.devicePath}\n"
        f"Filesystem:  {plan.filesystemType}\n"
        f"Label:       {plan.volumeLabel}\n"
        f"Result:      {result}; card will be inventoried as empty\n"
    )


def _mountedCardFind(cardId: int, *, mountRoots: Optional[Sequence[Path]]) -> Path:
    labelName = cameraCardLabelFilename(cardId)
    matches: list[Path] = []
    for root in _mountRoots(mountRoots):
        if not root.is_dir():
            continue
        for mount in root.iterdir():
            if mount.is_dir() and (mount / labelName).is_file():
                matches.append(mount.resolve())
    unique = sorted(set(matches))
    if not unique:
        raise RuntimeError(
            f"card {cardId:03d} is not mounted with identity file {labelName}"
        )
    if len(unique) > 1:
        raise RuntimeError(
            f"multiple mounted volumes claim card {cardId:03d}: "
            + ", ".join(str(path) for path in unique)
        )
    return unique[0]


def _mountedLabelFind(label: str, *, mountRoots: Optional[Sequence[Path]]) -> Optional[Path]:
    matches = [
        path.resolve()
        for root in _mountRoots(mountRoots)
        if root.is_dir()
        for path in root.iterdir()
        if path.is_dir() and path.name.casefold() == label.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def _mountRoots(value: Optional[Sequence[Path]]) -> tuple[Path, ...]:
    if value is not None:
        return tuple(Path(path).expanduser() for path in value)
    user = os.environ.get("USER") or Path.home().name
    return (Path("/media") / user, Path("/run/media") / user)


def _removableDeviceRequire(devicePath: Path, runner: CommandRunner) -> None:
    parentName = _commandText(runner, ["lsblk", "-no", "PKNAME", str(devicePath)])
    disk = Path("/dev") / parentName if parentName else devicePath
    removable = _commandText(runner, ["lsblk", "-dn", "-o", "RM", str(disk)])
    if removable != "1":
        raise RuntimeError(f"refusing to format non-removable device {disk}")


def _commandRun(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _commandChecked(
    runner: CommandRunner,
    command: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    result = runner(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(f"{' '.join(command)}: {detail}")
    return result


def _commandText(runner: CommandRunner, command: Sequence[str]) -> str:
    return _commandChecked(runner, command).stdout.strip()


def _mountPathFromUdisks(output: str) -> Optional[Path]:
    marker = " at "
    if marker not in output:
        return None
    value = output.rsplit(marker, 1)[-1].strip().rstrip(".")
    return Path(value) if value else None
