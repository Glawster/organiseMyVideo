"""Safe reconciliation of legacy camera archive month folders."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .filesystemOperations import FilesystemOperations

LEGACY_MONTH_PATTERN = re.compile(r"^(0[1-9]|1[0-2])-[A-Za-z]{3}$")
YEAR_PATTERN = re.compile(r"^\d{4}$")
CameraMigrationProgress = Callable[[int, int, str], None]


@dataclass(frozen=True)
class CameraDuplicate:
    """One legacy file matching its canonical archive path and size."""

    legacyPath: Path
    canonicalPath: Path
    sha256: Optional[str] = None


@dataclass(frozen=True)
class CameraMigrationConflict:
    """One legacy file that cannot be removed automatically."""

    legacyPath: Path
    canonicalPath: Path
    reason: str


@dataclass(frozen=True)
class CameraMigrationResult:
    """Result of one legacy-month duplicate reconciliation."""

    archiveRoot: Path
    dryRun: bool
    duplicates: tuple[CameraDuplicate, ...]
    conflicts: tuple[CameraMigrationConflict, ...]
    removedFiles: int
    removedDirectories: int


def cameraMonthDuplicatesReconcile(
    archiveRoot: Path,
    *,
    dryRun: bool = True,
    progressCallback: Optional[CameraMigrationProgress] = None,
) -> CameraMigrationResult:
    """Reconcile legacy ``MM-MMM`` month folders safely.

    The canonical archive path is ``YYYY/MM/DD``. Dry-run deliberately avoids
    full-file hashing: matching canonical path plus file size identifies a
    duplicate *candidate*. On a confirmed run, each candidate is SHA-256
    verified immediately before the legacy file is removed. Missing canonical
    files, size mismatches, and confirmed content mismatches are retained and
    reported.
    """

    root = Path(archiveRoot).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)

    duplicates: list[CameraDuplicate] = []
    conflicts: list[CameraMigrationConflict] = []
    legacyMonths = _legacyMonthDirectories(root)
    legacyFiles = tuple(
        sorted(
            path
            for legacyMonth in legacyMonths
            for path in legacyMonth.rglob("*")
            if path.is_file()
        )
    )
    totalFiles = len(legacyFiles)
    totalSteps = totalFiles if dryRun else totalFiles * 2
    if progressCallback is not None:
        progressCallback(0, totalSteps, "")

    completedFiles = 0
    candidates: dict[Path, CameraDuplicate] = {}
    for legacyPath in legacyFiles:
        legacyMonth = next(
            month for month in legacyMonths if legacyPath.is_relative_to(month)
        )
        canonicalMonth = legacyMonth.parent / legacyMonth.name[:2]
        relativePath = legacyPath.relative_to(legacyMonth)
        canonicalPath = canonicalMonth / relativePath
        try:
            if not canonicalPath.is_file():
                conflicts.append(
                    CameraMigrationConflict(
                        legacyPath=legacyPath,
                        canonicalPath=canonicalPath,
                        reason="canonical file missing",
                    )
                )
                continue
            if legacyPath.stat().st_size != canonicalPath.stat().st_size:
                conflicts.append(
                    CameraMigrationConflict(
                        legacyPath=legacyPath,
                        canonicalPath=canonicalPath,
                        reason="size differs",
                    )
                )
                continue
            candidates[legacyPath] = CameraDuplicate(
                legacyPath=legacyPath,
                canonicalPath=canonicalPath,
            )
        finally:
            completedFiles += 1
            if progressCallback is not None:
                progressCallback(completedFiles, totalSteps, legacyPath.name)

    removedFiles = 0
    removedDirectories = 0
    if dryRun:
        duplicates.extend(candidates.values())
    else:
        filesystem = FilesystemOperations(dryRun=False)
        for verificationIndex, legacyPath in enumerate(legacyFiles, start=1):
            candidate = candidates.get(legacyPath)
            completedSteps = totalFiles + verificationIndex - 1
            if candidate is None:
                if progressCallback is not None:
                    progressCallback(
                        completedSteps + 1,
                        totalSteps,
                        f"skip {legacyPath.name}",
                    )
                continue

            if progressCallback is not None:
                progressCallback(
                    completedSteps,
                    totalSteps,
                    f"verifying {candidate.legacyPath.name}",
                )

            if not candidate.legacyPath.is_file() or not candidate.canonicalPath.is_file():
                conflicts.append(
                    CameraMigrationConflict(
                        legacyPath=candidate.legacyPath,
                        canonicalPath=candidate.canonicalPath,
                        reason="file changed after scan",
                    )
                )
            elif candidate.legacyPath.stat().st_size != candidate.canonicalPath.stat().st_size:
                conflicts.append(
                    CameraMigrationConflict(
                        legacyPath=candidate.legacyPath,
                        canonicalPath=candidate.canonicalPath,
                        reason="size changed after scan",
                    )
                )
            else:
                legacyDigest = _sha256(candidate.legacyPath)
                canonicalDigest = _sha256(candidate.canonicalPath)
                if legacyDigest != canonicalDigest:
                    conflicts.append(
                        CameraMigrationConflict(
                            legacyPath=candidate.legacyPath,
                            canonicalPath=candidate.canonicalPath,
                            reason="SHA-256 differs",
                        )
                    )
                else:
                    verified = CameraDuplicate(
                        legacyPath=candidate.legacyPath,
                        canonicalPath=candidate.canonicalPath,
                        sha256=legacyDigest,
                    )
                    filesystem.removeFile(
                        verified.legacyPath,
                        stateKind="camera-migration-duplicate",
                    )
                    duplicates.append(verified)
                    removedFiles += 1

            if progressCallback is not None:
                progressCallback(
                    completedSteps + 1,
                    totalSteps,
                    candidate.legacyPath.name,
                )

        for legacyMonth in legacyMonths:
            directories = sorted(
                (path for path in legacyMonth.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            )
            directories.append(legacyMonth)
            for directory in directories:
                if directory.is_dir() and not any(directory.iterdir()):
                    filesystem.removeEmptyDirectory(
                        directory,
                        stateKind="camera-migration-duplicate",
                    )
                    removedDirectories += 1

    return CameraMigrationResult(
        archiveRoot=root,
        dryRun=dryRun,
        duplicates=tuple(duplicates),
        conflicts=tuple(conflicts),
        removedFiles=removedFiles,
        removedDirectories=removedDirectories,
    )


def cameraMonthDuplicatesSummary(result: CameraMigrationResult) -> str:
    """Return an operator-readable duplicate reconciliation summary."""

    mode = "DRY-RUN" if result.dryRun else "CONFIRMED"
    duplicateLabel = "Candidates" if result.dryRun else "Verified"
    lines = [
        "CAMERA MIGRATION — DUPLICATE MONTH FOLDERS",
        "",
        f"Archive root:  {result.archiveRoot}",
        f"Mode:          {mode}",
        f"{duplicateLabel + ':':<14}{len(result.duplicates)}",
        f"Conflicts:     {len(result.conflicts)}",
    ]
    if result.dryRun:
        lines.append("SHA-256:       deferred until --confirm")
    else:
        lines.extend(
            [
                f"Removed files: {result.removedFiles}",
                f"Removed dirs:  {result.removedDirectories}",
            ]
        )

    if result.duplicates:
        if result.dryRun:
            lines.extend(["", "Duplicate candidates (matching path and size)"])
            action = "would verify/remove"
        else:
            lines.extend(["", "SHA-256 verified duplicates"])
            action = "removed"
        for duplicate in result.duplicates:
            lines.append(f"  {action}  {duplicate.legacyPath}")
            lines.append(f"    keep    {duplicate.canonicalPath}")

    if result.conflicts:
        lines.extend(["", "Retained for review"])
        for conflict in result.conflicts:
            lines.append(f"  retained  {conflict.legacyPath}")
            lines.append(f"    {conflict.reason}: {conflict.canonicalPath}")

    lines.append("")
    return "\n".join(lines) + "\n"


def _legacyMonthDirectories(root: Path) -> tuple[Path, ...]:
    months: list[Path] = []
    for yearPath in sorted(path for path in root.iterdir() if path.is_dir()):
        if YEAR_PATTERN.fullmatch(yearPath.name) is None:
            continue
        for monthPath in sorted(path for path in yearPath.iterdir() if path.is_dir()):
            if LEGACY_MONTH_PATTERN.fullmatch(monthPath.name) is not None:
                months.append(monthPath)
    return tuple(months)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
