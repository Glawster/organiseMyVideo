"""Capture-time readers for camera JPEG/THM stills and MP4 movies."""

from __future__ import annotations

import re
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# MP4/QuickTime creation times count seconds from 1904-01-01 UTC.
_MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

_JPEG_SUFFIXES = {".jpg", ".jpeg", ".thm"}
_MP4_SUFFIXES = {".mp4", ".mov"}
_DASHCAM_DATE_YMD_HMS = re.compile(r"^(\d{8})_(\d{6})")
_DASHCAM_DATE_YYMD_HMS = re.compile(r"^(\d{6})_(\d{6})_")
_DASHCAM_DATE_Y_MD_HMS = re.compile(r"^(\d{4})_(\d{4})_(\d{6})")
_DASHCAM_DATE_Y_M_D_HMS = re.compile(r"^(\d{4})_(\d{2})_(\d{2})_(\d{6})")
_DASHCAM_DATE_DASHED = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})")
_DASHCAM_DATE_COMPACT = re.compile(r"^(?:TS)?(\d{14})", re.IGNORECASE)

_TYPE_BYTE = 1
_TYPE_ASCII = 2
_TYPE_SHORT = 3
_TYPE_LONG = 4
_TAG_DATETIME = 0x0132
_TAG_EXIF_IFD = 0x8769
_TAG_DATETIME_ORIGINAL = 0x9003
_TAG_DATETIME_DIGITIZED = 0x9004


def metadataCaptureRead(path: Path) -> Optional[datetime]:
    """Return capture time from metadata, then dated dash-cam filenames."""

    suffix = path.suffix.lower()
    captured = None
    if suffix in _JPEG_SUFFIXES:
        captured = metadataJpegCaptureRead(path)
    elif suffix in _MP4_SUFFIXES:
        captured = metadataMp4CaptureRead(path)
    if captured is not None:
        return captured
    return metadataFilenameCaptureRead(path)


def metadataFilenameCaptureRead(path: Path) -> Optional[datetime]:
    """Return a timestamp encoded in common dash-cam filenames, if any."""

    stem = path.stem
    match = _DASHCAM_DATE_COMPACT.match(stem)
    if match:
        digits = match.group(1)
        return _datetimeFromParts(digits[:8], digits[8:])
    match = _DASHCAM_DATE_YMD_HMS.match(stem)
    if match:
        return _datetimeFromParts(match.group(1), match.group(2))
    match = _DASHCAM_DATE_YYMD_HMS.match(stem)
    if match:
        return _datetimeFromParts("20" + match.group(1), match.group(2))
    match = _DASHCAM_DATE_Y_MD_HMS.match(stem)
    if match:
        return _datetimeFromParts(match.group(1) + match.group(2), match.group(3))
    match = _DASHCAM_DATE_Y_M_D_HMS.match(stem)
    if match:
        return _datetimeFromParts(
            match.group(1) + match.group(2) + match.group(3), match.group(4)
        )
    match = _DASHCAM_DATE_DASHED.match(stem)
    if match:
        parts = match.groups()
        return _datetimeFromParts("".join(parts[:3]), "".join(parts[3:]))
    return None


def metadataJpegCaptureRead(path: Path) -> Optional[datetime]:
    """Return EXIF capture time from a JPEG or GoPro ``.THM`` thumbnail."""

    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None

    # Walk JPEG markers until APP1/Exif or the start of compressed image data.
    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            return None
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            return None
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if length < 2 or offset + length > len(data):
            return None
        payload = data[offset + 2 : offset + length]
        offset += length
        if marker == 0xE1 and payload.startswith(b"Exif\x00\x00"):
            return _exifDatetimeRead(payload[6:])
        if marker == 0xDA:
            return None
    return None


def metadataMp4CaptureRead(path: Path) -> Optional[datetime]:
    """Return the movie-header creation time from an MP4 or QuickTime file."""

    try:
        with path.open("rb") as handle:
            creation = _mp4MvhdCreationRead(handle)
    except OSError:
        return None
    if not creation:
        return None
    return _MP4_EPOCH + timedelta(seconds=creation)


## datetime


def _datetimeFromParts(dateDigits: str, timeDigits: str) -> Optional[datetime]:
    """Build a naive datetime from compact ``YYYYMMDD`` and ``HHMMSS`` digits."""

    if len(dateDigits) != 8 or len(timeDigits) != 6:
        return None
    try:
        return datetime.strptime(dateDigits + timeDigits, "%Y%m%d%H%M%S")
    except ValueError:
        return None


## exif


def _exifDatetimeParse(value: str) -> Optional[datetime]:
    """Parse an EXIF ASCII timestamp such as ``2024:04:20 12:00:00``."""

    cleaned = value.strip().strip("\x00")
    if not cleaned or cleaned.startswith("0000"):
        return None
    for formatName in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, formatName)
        except ValueError:
            continue
    return None


def _exifDatetimeRead(tiff: bytes) -> Optional[datetime]:
    """Read DateTimeOriginal, DateTimeDigitized, or DateTime from TIFF bytes."""

    if len(tiff) < 8:
        return None
    endianCode = tiff[:2]
    if endianCode == b"II":
        endian = "<"
    elif endianCode == b"MM":
        endian = ">"
    else:
        return None
    try:
        magic = struct.unpack(endian + "H", tiff[2:4])[0]
        ifdOffset = struct.unpack(endian + "I", tiff[4:8])[0]
    except struct.error:
        return None
    if magic != 42:
        return None

    ifd0 = _exifIfdRead(tiff, endian, ifdOffset)
    preferred = (
        _exifDatetimeParse(ifd0.get(_TAG_DATETIME_ORIGINAL, ""))
        or _exifDatetimeParse(ifd0.get(_TAG_DATETIME_DIGITIZED, ""))
        or _exifDatetimeParse(ifd0.get(_TAG_DATETIME, ""))
    )
    if preferred is not None:
        return preferred

    exifOffset = ifd0.get(_TAG_EXIF_IFD)
    if not isinstance(exifOffset, int):
        return None
    exifIfd = _exifIfdRead(tiff, endian, exifOffset)
    return (
        _exifDatetimeParse(exifIfd.get(_TAG_DATETIME_ORIGINAL, ""))
        or _exifDatetimeParse(exifIfd.get(_TAG_DATETIME_DIGITIZED, ""))
        or _exifDatetimeParse(exifIfd.get(_TAG_DATETIME, ""))
    )


def _exifIfdRead(tiff: bytes, endian: str, offset: int) -> dict:
    """Return tag values from one TIFF IFD, including a nested Exif IFD."""

    values: dict = {}
    if offset < 0 or offset + 2 > len(tiff):
        return values
    count = struct.unpack(endian + "H", tiff[offset : offset + 2])[0]
    entryOffset = offset + 2
    for _ in range(count):
        end = entryOffset + 12
        if end > len(tiff):
            break
        tag, typeCode, number = struct.unpack(endian + "HHI", tiff[entryOffset:end][:8])
        rawValue = tiff[entryOffset + 8 : end]
        entryOffset = end
        decoded = _exifValueDecode(tiff, endian, typeCode, number, rawValue)
        if decoded is None:
            continue
        values[tag] = decoded
        if tag == _TAG_EXIF_IFD and isinstance(decoded, int):
            values.update(_exifIfdRead(tiff, endian, decoded))
    return values


def _exifValueDecode(
    tiff: bytes, endian: str, typeCode: int, count: int, rawValue: bytes
) -> object:
    """Decode one TIFF IFD value, following offsets when the payload is large."""

    typeSize = {_TYPE_BYTE: 1, _TYPE_ASCII: 1, _TYPE_SHORT: 2, _TYPE_LONG: 4}.get(
        typeCode
    )
    if typeSize is None or count <= 0:
        return None
    byteCount = typeSize * count
    if byteCount <= 4:
        payload = rawValue[:byteCount]
    else:
        (dataOffset,) = struct.unpack(endian + "I", rawValue)
        payload = tiff[dataOffset : dataOffset + byteCount]
        if len(payload) < byteCount:
            return None
    if typeCode == _TYPE_ASCII:
        return payload.decode("ascii", errors="replace")
    if typeCode == _TYPE_LONG and count == 1:
        return struct.unpack(endian + "I", payload[:4])[0]
    if typeCode == _TYPE_SHORT and count == 1:
        return struct.unpack(endian + "H", payload[:2])[0]
    return payload


## mp4


def _mp4BoxIterate(handle, limit: Optional[int] = None):
    """Yield ``(boxType, payloadStart, payloadSize)`` until *limit* or EOF."""

    while True:
        start = handle.tell()
        if limit is not None and start >= limit:
            return
        header = handle.read(8)
        if len(header) < 8:
            return
        size = struct.unpack(">I", header[:4])[0]
        boxType = header[4:8]
        headerSize = 8
        if size == 1:
            large = handle.read(8)
            if len(large) < 8:
                return
            size = struct.unpack(">Q", large)[0]
            headerSize = 16
        elif size == 0:
            current = handle.tell()
            handle.seek(0, 2)
            end = handle.tell()
            handle.seek(current)
            size = end - start
        if size < headerSize:
            return
        payloadStart = handle.tell()
        payloadSize = size - headerSize
        payloadEnd = payloadStart + payloadSize
        if limit is not None and payloadEnd > limit:
            return
        yield boxType, payloadStart, payloadSize
        handle.seek(payloadEnd)


def _mp4MvhdCreationRead(handle) -> Optional[int]:
    """Return a non-zero mvhd creation timestamp, or ``None``."""

    for boxType, payloadStart, payloadSize in _mp4BoxIterate(handle):
        if boxType != b"moov":
            continue
        handle.seek(payloadStart)
        for innerType, innerStart, innerSize in _mp4BoxIterate(
            handle, payloadStart + payloadSize
        ):
            if innerType != b"mvhd" or innerSize < 12:
                continue
            handle.seek(innerStart)
            versionFlags = handle.read(4)
            if len(versionFlags) < 4:
                return None
            version = versionFlags[0]
            if version == 1:
                raw = handle.read(8)
                if len(raw) < 8:
                    return None
                creation = struct.unpack(">Q", raw)[0]
            else:
                raw = handle.read(4)
                if len(raw) < 4:
                    return None
                creation = struct.unpack(">I", raw)[0]
            return creation or None
        return None
    return None
