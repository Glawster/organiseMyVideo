"""Non-mutating camera-media detection for REQ-004."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .cameraInventory import (
    DASHCAM_DIRECTORY_NAMES,
    DASHCAM_FILENAME,
    DASHCAM_MODEL_FOLDER,
    DASHCAM_NUMBERED_FOLDER,
    DJI_MEDIA_FOLDER,
    GOPRO_STEM,
    IGNORED_DIRECTORY_NAMES,
    IGNORED_FILE_NAMES,
)

SUPPORTED_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".mp4",
    ".mov",
    ".srt",
    ".nmea",
    ".lrv",
    ".thm",
}


@dataclass(frozen=True)
class CameraDetectedFile:
    """One file classified by camera family without changing the filesystem."""

    path: Path
    relativePath: str
    cameraKind: str
    fileKind: str


@dataclass(frozen=True)
class CameraDetection:
    """Supported camera files plus unknown content encountered during detection."""

    sourcePath: Path
    files: tuple[CameraDetectedFile, ...]
    unknownPaths: tuple[str, ...]


def cameraDetect(source: Path) -> CameraDetection:
    """Detect supported GoPro, DJI and dash-cam files below *source*."""

    sourcePath = Path(source).expanduser().resolve()
    if not sourcePath.is_dir():
        raise ValueError(f"source directory does not exist: {sourcePath}")

    detected: list[CameraDetectedFile] = []
    unknown: list[str] = []
    for path in sorted(sourcePath.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(sourcePath)
        if _pathIgnored(relative):
            continue
        cameraKind = cameraKindDetect(relative)
        suffix = path.suffix.lower()
        if cameraKind == "unknown" or suffix not in SUPPORTED_SUFFIXES:
            unknown.append(relative.as_posix())
            continue
        detected.append(
            CameraDetectedFile(
                path=path,
                relativePath=relative.as_posix(),
                cameraKind=cameraKind,
                fileKind=_fileKind(suffix),
            )
        )
    return CameraDetection(sourcePath, tuple(detected), tuple(unknown))


def cameraKindDetect(relativePath: Path) -> str:
    """Return ``gopro``, ``dji``, ``dashcam`` or ``unknown`` for a relative path."""

    parts = relativePath.parts
    lowerParts = [part.lower() for part in parts[:-1]]
    name = relativePath.name
    stem = relativePath.stem

    if any(part.endswith("gopro") for part in lowerParts) or GOPRO_STEM.match(stem):
        return "gopro"

    if any(DJI_MEDIA_FOLDER.fullmatch(part) for part in parts[:-1]):
        if stem.upper().startswith("DJI_"):
            return "dji"
    if stem.upper().startswith("DJI_"):
        return "dji"

    if DASHCAM_FILENAME.match(stem):
        return "dashcam"
    for part in parts[:-1]:
        lower = part.lower()
        if (
            lower in DASHCAM_DIRECTORY_NAMES
            or DASHCAM_NUMBERED_FOLDER.fullmatch(part)
            or DASHCAM_MODEL_FOLDER.fullmatch(part)
        ):
            return "dashcam"
    return "unknown"


def _pathIgnored(relativePath: Path) -> bool:
    """Return whether a path is known non-media camera/OS content."""

    for part in relativePath.parts[:-1]:
        if part.lower() in IGNORED_DIRECTORY_NAMES:
            return True
    name = relativePath.name.lower()
    return (
        name in IGNORED_FILE_NAMES
        or name.startswith("._")
        or re.search(r"\.(db|log)$", name) is not None
    )


def _fileKind(suffix: str) -> str:
    if suffix in {".mp4", ".mov"}:
        return "video"
    if suffix in {".jpg", ".jpeg"}:
        return "photo"
    if suffix in {".srt", ".nmea"}:
        return "sidecar"
    if suffix == ".lrv":
        return "preview"
    if suffix == ".thm":
        return "thumbnail"
    return "unknown"
