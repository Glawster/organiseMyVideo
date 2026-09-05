"""Synthetic GoPro/DJI files for camera metadata and inventory tests."""

from __future__ import annotations

import json
import struct
from datetime import datetime, timezone
from pathlib import Path


def jpegWithExif(capture: datetime) -> bytes:
    """Return a minimal JPEG whose EXIF DateTimeOriginal is *capture*."""

    stamp = capture.strftime("%Y:%m:%d %H:%M:%S") + "\x00"
    ifd0Offset = 8
    exifIfdOffset = 26
    stringOffset = 44
    tiff = bytearray()
    tiff += b"II" + struct.pack("<H", 42) + struct.pack("<I", ifd0Offset)
    tiff += struct.pack("<H", 1)
    tiff += struct.pack("<HHI", 0x8769, 4, 1)
    tiff += struct.pack("<I", exifIfdOffset)
    tiff += struct.pack("<I", 0)
    tiff += struct.pack("<H", 1)
    tiff += struct.pack("<HHI", 0x9003, 2, 20)
    tiff += struct.pack("<I", stringOffset)
    tiff += struct.pack("<I", 0)
    tiff += stamp.encode("ascii")
    app1Payload = b"Exif\x00\x00" + bytes(tiff)
    return (
        b"\xff\xd8"
        + b"\xff\xe1"
        + struct.pack(">H", 2 + len(app1Payload))
        + app1Payload
        + b"\xff\xd9"
    )


def jpegWithoutExif() -> bytes:
    """Return a JPEG with no APP1/Exif segment."""

    return b"\xff\xd8\xff\xd9"


def mp4WithCreation(capture: datetime) -> bytes:
    """Return a tiny MP4 whose mvhd creation time is *capture*."""

    if capture.tzinfo is None:
        capture = capture.replace(tzinfo=timezone.utc)
    macTimestamp = int(capture.timestamp()) + 2082844800
    mvhdPayload = (
        b"\x00\x00\x00\x00"
        + struct.pack(">IIII", macTimestamp, macTimestamp, 1000, 0)
        + struct.pack(">I", 0x00010000)
        + struct.pack(">HH", 0x0100, 0)
        + b"\x00" * 8
        + struct.pack(">9i", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
        + b"\x00" * 24
        + struct.pack(">I", 2)
    )

    def box(boxType: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", 8 + len(payload)) + boxType + payload

    return (
        box(b"ftyp", b"isom" + struct.pack(">I", 0) + b"isommp41")
        + box(b"moov", box(b"mvhd", mvhdPayload))
        + box(b"mdat", b"")
    )


def cardTreeBuild(
    root: Path,
    *,
    withThm: bool = True,
    withDji: bool = True,
    jpegCapture: datetime | None = None,
    mp4Capture: datetime | None = None,
) -> Path:
    """Create a mixed GoPro/DJI card tree under *root* and return *root*."""

    jpegCapture = jpegCapture or datetime(2024, 4, 20, 12, 0, 0)
    mp4Capture = mp4Capture or datetime(2024, 4, 18, 9, 0, 0, tzinfo=timezone.utc)
    jpeg = jpegWithExif(jpegCapture)
    mp4 = mp4WithCreation(mp4Capture)
    gopro = root / "DCIM" / "100GOPRO"
    gopro.mkdir(parents=True)
    (gopro / "GH010111.MP4").write_bytes(mp4)
    (gopro / "GH010111.LRV").write_bytes(b"lrv-preview")
    (gopro / "G0010111.JPG").write_bytes(jpeg)
    if withThm:
        (gopro / "GH010111.THM").write_bytes(jpeg)
    (gopro / "._GH010111.MP4").write_bytes(b"appledouble")
    misc = root / "MISC"
    misc.mkdir()
    (misc / "info.txt").write_text("ignore-me", encoding="utf-8")
    (misc / "version.txt").write_text(
        json.dumps(
            {
                "info version": "2.0",
                "firmware version": "H24.03.02.30.00",
                "camera type": "HERO",
                "camera serial number": "C3544225115979",
            }
        ),
        encoding="utf-8",
    )
    if withDji:
        dji = root / "DCIM" / "101MEDIA"
        dji.mkdir()
        (dji / "DJI_0021.MP4").write_bytes(mp4)
        (dji / "DJI_0021.SRT").write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n", encoding="utf-8"
        )
    return root


def cardVolumeFake(monkeypatch, totalBytes: int, freeBytes: int) -> None:
    """Make inventory treat the scanned path as an SD card of *totalBytes*."""

    class Stats:
        f_frsize = 1
        f_blocks = totalBytes
        f_bavail = freeBytes

    monkeypatch.setattr(
        "organiseMyVideo.cameraInventory.os.statvfs",
        lambda path: Stats(),
    )


def dashcamTreeBuild(root: Path, layout: str = "viofo") -> Path:
    """Create a synthetic dash-cam card tree under *root*."""

    if layout == "blackvue":
        record = root / "Record"
        record.mkdir(parents=True)
        (record / "20250722_110221_NF.mp4").write_bytes(b"front")
        (record / "20250722_110221_NR.mp4").write_bytes(b"rear")
        return root
    if layout == "transcend":
        # DrivePro 250 stores clips as YYYY_MMDD_HHMMSS_sequence.mp4
        # under DP250/N_VIDEO (underscores, not hyphenated N-Video).
        normal = root / "DP250" / "N_VIDEO"
        parking = root / "DP250" / "P_VIDEO"
        event = root / "DP250" / "EVENT"
        system = root / "DP250" / "SYSTEM"
        normal.mkdir(parents=True)
        parking.mkdir(parents=True)
        event.mkdir(parents=True)
        system.mkdir(parents=True)
        (normal / "2026_0513_120237_012.mp4").write_bytes(b"normal")
        (normal / "2026_0513_120537_013.mp4").write_bytes(b"normal-next")
        (parking / "2026_0513_130000_001.mp4").write_bytes(b"park")
        (event / "2026_0513_121000_014.mp4").write_bytes(b"event")
        (system / "DP250.bin").write_bytes(b"firmware")
        return root
    if layout == "garmin":
        eventDir = root / "DCIM" / "100EVENT"
        parkDir = root / "DCIM" / "103PARKM"
        eventDir.mkdir(parents=True)
        parkDir.mkdir(parents=True)
        (eventDir / "clip1.mp4").write_bytes(b"event")
        (parkDir / "park1.mp4").write_bytes(b"park")
        return root
    movie = root / "DCIM" / "Movie"
    parking = movie / "Parking"
    parking.mkdir(parents=True)
    (movie / "2024_0418_090000_0001F.MP4").write_bytes(b"front")
    (movie / "2024_0418_090000_0001R.MP4").write_bytes(b"rear")
    (parking / "2024_0418_100000_0002F.MP4").write_bytes(b"park")
    return root
