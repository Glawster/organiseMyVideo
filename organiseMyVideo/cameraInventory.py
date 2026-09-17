"""Catalogue a numbered camera SD card into application local-state SQLite."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .cameraMetadata import metadataCaptureRead
from .constants import (
    CAMERA_CARD_LABEL_LEGACY_FILENAME,
    CAMERA_INVENTORY_DATABASE,
    GROK_VISION_MODEL,
    cameraCardLabelFilename,
)
from .filesystemOperations import FilesystemOperations
from .mediaCatalogue import catalogueSchemaApply

logger = getLogger()

VISION_PROMPT = (
    "These JPEG thumbnails are from one camera SD card. Describe the overall "
    "content in 2-3 sentences: setting, activities, and notable subjects. "
    "Say if it looks like one outing or mixed events."
)
THUMBNAIL_SAMPLE_LIMIT = 8
IGNORED_DIRECTORY_NAMES = {
    "misc",
    "lost.dir",
    "system volume information",
    "_gsdata_",
    "system",
}
IGNORED_FILE_NAMES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    CAMERA_CARD_LABEL_LEGACY_FILENAME.lower(),
}
CARD_LABEL_NAME = re.compile(r"^organiseMyVideo\.(\d{3,})$")
CID_BRANDS = {
    0x01: "Panasonic",
    0x02: "Toshiba",
    0x03: "SanDisk",
    0x11: "Toshiba",
    0x13: "Kingmax",
    0x1B: "Samsung",
    0x1D: "AData",
    0x27: "Phison",
    0x28: "Lexar",
    0x31: "Silicon Power",
    0x41: "Kingston",
    0x6F: "SK Hynix",
    0x73: "Western Digital",
    0x74: "Transcend",
    0x76: "Patriot",
    0x82: "Sony",
    0x9C: "Amazon",
}
MARKETED_GIGABYTES = (32, 64, 128, 256)
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".cr3"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".m4v"}
JPEG_SUFFIXES = {".jpg", ".jpeg"}
KIND_BY_SUFFIX = {
    ".thm": "thumbnail",
    ".lrv": "preview",
    ".srt": "sidecar",
    ".nmea": "sidecar",
    ".gps": "sidecar",
    **{suffix: "photo" for suffix in PHOTO_SUFFIXES},
    **{suffix: "video" for suffix in VIDEO_SUFFIXES},
}
DASHCAM_DIRECTORY_NAMES = {
    "movie",
    "nbdvr",
    "record",
    "rec",
    "parking",
    "event",
    "normal",
    "front",
    "rear",
    "protected",
    "n-video",
    "p-video",
    "n_video",
    "p_video",
    "e_video",
    "video",
    "snapshot",
    "jpeg",
    "dpb10",
    "drivepro",
}
DASHCAM_NUMBERED_FOLDER = re.compile(
    r"^\d{3}(EVENT|PHOTO|SAVED|PARKM|TLPSE|UNSVD)$", re.IGNORECASE
)
DASHCAM_MODEL_FOLDER = re.compile(r"^DPB?\d{2,4}[A-Z]*$", re.IGNORECASE)
DASHCAM_FILENAME = re.compile(
    r"""^(?:
        (?:TS)?\d{14}
      | \d{8}_\d{6}
      | \d{6}_\d{6}_\d{3}_[FR]
      | \d{4}_\d{4}_\d{6}(?:_\d{2,4})?
      | \d{4}_\d{2}_\d{2}_\d{6}
      | \d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}
    )""",
    re.IGNORECASE | re.VERBOSE,
)
GOPRO_STEM = re.compile(r"^(GH|GL|GX|GOPR|GPFR|GPBK|G\d)", re.IGNORECASE)
DJI_MEDIA_FOLDER = re.compile(r"^\d+MEDIA$", re.IGNORECASE)
CANON_FOLDER = re.compile(r"^\d{3}CANON$", re.IGNORECASE)
CANON_STEM = re.compile(r"^(IMG|MVI)_", re.IGNORECASE)


@dataclass(frozen=True)
class CardCapacity:
    totalBytes: Optional[int]
    usedBytes: int
    freeBytes: Optional[int]
    contentBytes: int


@dataclass(frozen=True)
class CardFileRecord:
    relativePath: str
    sizeBytes: int
    modifiedAt: Optional[str]
    captureAt: Optional[str]
    kind: str
    cameraKind: str


@dataclass(frozen=True)
class CameraIdentity:
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    firmware: Optional[str] = None
    wifiMac: Optional[str] = None


@dataclass(frozen=True)
class CardInventoryRecord:
    cardId: int
    sourcePath: str
    inventoriedAt: str
    volumeLabel: str
    filesystemId: Optional[str]
    capacity: CardCapacity
    dateStart: Optional[str]
    dateEnd: Optional[str]
    dateSource: str
    cameraKinds: tuple[str, ...]
    fileCounts: dict[str, int] = field(default_factory=dict)
    contentSummary: str = ""
    visionStatus: str = "unavailable"
    thumbnailSampled: int = 0
    files: tuple[CardFileRecord, ...] = ()
    cardLabelPath: Optional[str] = None
    previousCardId: Optional[int] = None
    previousLabelPaths: tuple[str, ...] = ()
    manufacturer: Optional[str] = None
    cameraModel: Optional[str] = None
    cameraSerial: Optional[str] = None
    firmwareVersion: Optional[str] = None
    cardBrand: Optional[str] = None
    cardProduct: Optional[str] = None
    cardRatedGigabytes: Optional[int] = None
    volumeKind: str = "sd"
    cameraWifiMac: Optional[str] = None
    goproCardId: Optional[str] = None


class CameraInventory:
    def __init__(
        self,
        dryRun: bool = True,
        databasePath: Optional[Path] = None,
        visionDescribe: Optional[Callable[[list[Path]], str]] = None,
        apiKey: Optional[str] = None,
    ):
        self.dryRun = dryRun
        self.databasePath = (
            Path(databasePath) if databasePath else CAMERA_INVENTORY_DATABASE
        )
        self._visionDescribe = visionDescribe
        self._apiKey = apiKey
        self.filesystem = FilesystemOperations(dryRun=dryRun)

    def inventoryPersist(self, record: CardInventoryRecord) -> CardInventoryRecord:
        logger.action(
            f"write camera inventory snapshot: card {record.cardId} -> {self.databasePath}"
        )
        if record.cardLabelPath:
            logger.action(f"write card label file: {record.cardLabelPath}")
        for oldLabel in record.previousLabelPaths:
            if oldLabel != record.cardLabelPath:
                logger.action(f"remove previous card label: {oldLabel}")
        if self.dryRun:
            return record
        if record.cardLabelPath:
            self._cardLabelWrite(record)
            self._cardLabelRemovePrevious(record)
        self.databasePath.parent.mkdir(parents=True, exist_ok=True)
        with self._databaseConnect() as connection:
            self._databaseInitialize(connection)
            inventoryId = self._databaseSnapshotInsert(connection, record)
            self._databaseFilesInsert(connection, inventoryId, record.files)
            connection.commit()
        logger.done("camera inventory snapshot written")
        return record

    def inventoryScan(
        self,
        source: Path,
        cardId: Optional[int] = None,
        *,
        reassign: bool = False,
        brand: Optional[str] = None,
    ) -> CardInventoryRecord:
        source = Path(source).expanduser().resolve()
        if not source.is_dir():
            raise ValueError(f"source directory does not exist: {source}")
        mountedChildren = sorted(
            child for child in source.iterdir() if os.path.ismount(str(child))
        )
        if mountedChildren:
            choices = ", ".join(str(child) for child in mountedChildren)
            raise ValueError(
                f"source is a parent of mounted volumes: {source}; "
                f"select the card mount itself: {choices}"
            )
        labelRoot = _cardLabelRoot(source)
        existingLabel, storedId = _cardLabelLocate(labelRoot)
        cardId = self._cardIdResolve(cardId, storedId, existingLabel, reassign=reassign)
        labelPath = labelRoot / cameraCardLabelFilename(cardId)
        previousLabels = tuple(
            str(path) for path in _cardLabelFiles(labelRoot) if path != labelPath
        )

        logger.doing("scanning camera card")
        logger.value("card id", cardId)
        logger.value("source", source)
        logger.value("card label", labelPath)
        if storedId not in {None, cardId}:
            logger.value("reassign from", storedId)
            logger.value("reassign to", cardId)

        files = tuple(self._cardFilesCollect(source))
        capacity = self._cardCapacityMeasure(
            source, sum(item.sizeBytes for item in files)
        )
        dateStart, dateEnd, dateSource = self._cardDateRange(files)
        cameraKinds = tuple(
            sorted({item.cameraKind for item in files if item.cameraKind != "unknown"})
        )
        samplePaths = self._contentThumbnailsSample(files, source)
        contentSummary, visionStatus = self._contentDescribe(samplePaths)
        identity = _cameraIdentityCollect(labelRoot, cameraKinds)
        existingPayload = _cardLabelPayloadRead(existingLabel)
        cid = _cidDecode(_cidHexForPath(labelRoot) or "")
        cardBrand = (
            _identityText(brand)
            or cid.get("brand")
            or _identityText(existingPayload.get("cardBrand"))
        )
        cardProduct = cid.get("product") or _identityText(
            existingPayload.get("cardProduct")
        )
        cardRatedGigabytes = _ratedGigabytesResolve(
            capacity.totalBytes, existingPayload.get("cardRatedGigabytes")
        )
        logger.value("card size GB", cardRatedGigabytes)
        logger.value("free bytes", capacity.freeBytes)

        record = CardInventoryRecord(
            cardId=cardId,
            sourcePath=str(source),
            inventoriedAt=_timestampNow(),
            volumeLabel=source.name,
            filesystemId=_filesystemIdRead(source),
            capacity=capacity,
            dateStart=dateStart,
            dateEnd=dateEnd,
            dateSource=dateSource,
            cameraKinds=cameraKinds,
            fileCounts=_fileCounts(files),
            contentSummary=contentSummary,
            visionStatus=visionStatus,
            thumbnailSampled=len(samplePaths),
            files=files,
            cardLabelPath=str(labelPath),
            previousCardId=storedId if storedId not in {None, cardId} else None,
            previousLabelPaths=previousLabels,
            manufacturer=identity.manufacturer,
            cameraModel=identity.model,
            cameraSerial=identity.serial,
            firmwareVersion=identity.firmware,
            cameraWifiMac=identity.wifiMac,
            goproCardId=_goproCardIdRead(labelRoot),
            cardBrand=cardBrand,
            cardProduct=cardProduct,
            cardRatedGigabytes=cardRatedGigabytes,
        )
        logger.value("date range", _dateRangeFormat(dateStart, dateEnd, dateSource))
        logger.value("content bytes", capacity.contentBytes)
        logger.done("camera card scan complete")
        return record

    def inventoryShow(self, cardId: int) -> Optional[CardInventoryRecord]:
        cardId = self._cardIdValidate(cardId)
        if not self.databasePath.is_file():
            return None
        with self._databaseConnect() as connection:
            self._databaseInitialize(connection)
            row = connection.execute(
                """
                SELECT * FROM cardInventory
                WHERE cardId = ?
                ORDER BY inventoriedAt DESC, inventoryId DESC
                LIMIT 1
                """,
                (cardId,),
            ).fetchone()
            if row is None:
                return None
            files = connection.execute(
                """
                SELECT relativePath, sizeBytes, modifiedAt, captureAt, kind, cameraKind
                FROM cardInventoryFile
                WHERE inventoryId = ?
                ORDER BY relativePath
                """,
                (row["inventoryId"],),
            ).fetchall()
        return _recordFromRow(row, files)

    def _cardCapacityMeasure(self, source: Path, contentBytes: int) -> CardCapacity:
        try:
            stats = os.statvfs(source)
        except OSError:
            return CardCapacity(None, contentBytes, None, contentBytes)
        totalBytes = stats.f_frsize * stats.f_blocks
        freeBytes = stats.f_frsize * stats.f_bavail
        usedBytes = max(totalBytes - freeBytes, contentBytes)
        return CardCapacity(totalBytes, usedBytes, freeBytes, contentBytes)

    def _cardDateRange(
        self, files: tuple[CardFileRecord, ...]
    ) -> tuple[Optional[str], Optional[str], str]:
        captureTimes = [item.captureAt for item in files if item.captureAt]
        if captureTimes:
            return min(captureTimes), max(captureTimes), "capture-metadata"
        modifiedTimes = [item.modifiedAt for item in files if item.modifiedAt]
        if modifiedTimes:
            return min(modifiedTimes), max(modifiedTimes), "filesystem-mtime"
        return None, None, "unavailable"

    def _cardFilesCollect(self, source: Path) -> list[CardFileRecord]:
        records: list[CardFileRecord] = []
        for directory, dirNames, fileNames in os.walk(source):
            dirNames[:] = [
                name
                for name in dirNames
                if name.lower() not in IGNORED_DIRECTORY_NAMES
                and not name.startswith("._")
            ]
            current = Path(directory)
            for fileName in fileNames:
                if _fileIgnored(fileName):
                    continue
                path = current / fileName
                if not path.is_file():
                    continue
                relative = path.relative_to(source).as_posix()
                stat = path.stat()
                captureAt = metadataCaptureRead(path)
                records.append(
                    CardFileRecord(
                        relativePath=relative,
                        sizeBytes=stat.st_size,
                        modifiedAt=_datetimeFormat(
                            datetime.fromtimestamp(stat.st_mtime)
                        ),
                        captureAt=_datetimeFormat(captureAt) if captureAt else None,
                        kind=_fileKind(path),
                        cameraKind=_fileCameraKind(relative),
                    )
                )
        records.sort(key=lambda item: item.relativePath)
        return records

    def _cardIdsStored(self) -> set[int]:
        """Return inventoried or explicitly registered card IDs without writing."""

        if not self.databasePath.is_file():
            return set()
        try:
            connection = sqlite3.connect(f"file:{self.databasePath}?mode=ro", uri=True)
        except sqlite3.Error:
            return set()
        used: set[int] = set()
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "cardInventory" in tables:
                used.update(
                    int(row[0])
                    for row in connection.execute(
                        "SELECT DISTINCT cardId FROM cardInventory WHERE cardId >= 1"
                    ).fetchall()
                )
            if "cardLocation" in tables:
                used.update(
                    int(row[0])
                    for row in connection.execute(
                        "SELECT cardId FROM cardLocation WHERE cardId >= 1"
                    ).fetchall()
                )
        except sqlite3.Error:
            return used
        finally:
            connection.close()
        return used

    def _cardIdNextAvailable(self) -> int:
        used = self._cardIdsStored()
        candidate = 1
        while candidate in used:
            candidate += 1
        return candidate

    def _cardIdResolve(
        self,
        cardId: Optional[int],
        storedId: Optional[int],
        labelPath: Optional[Path],
        *,
        reassign: bool = False,
    ) -> int:
        if cardId is None:
            if reassign:
                raise ValueError("--reassign requires --card with the new ID")
            if storedId is None:
                suggested = self._cardIdNextAvailable()
                existing = sorted(self._cardIdsStored())
                existingText = ", ".join(str(value) for value in existing) or "none"
                raise ValueError(
                    "no card ID found on this card; "
                    f"existing card IDs: {existingText}; "
                    f"suggested card ID: {suggested}; "
                    f"re-run with --card {suggested} "
                    "(add --confirm to write the card label)"
                )
            return storedId
        resolved = self._cardIdValidate(cardId)
        if storedId is not None and storedId != resolved and not reassign:
            location = labelPath or "card"
            raise ValueError(
                f"card label {location} records ID {storedId}, not {resolved}; "
                "pass --reassign --confirm to change it"
            )
        if reassign and storedId is None:
            raise ValueError(
                "no card label to reassign; omit --reassign for a first bind"
            )
        return resolved

    def _cardIdValidate(self, cardId: int) -> int:
        if isinstance(cardId, bool) or not isinstance(cardId, int) or cardId < 1:
            raise ValueError("card ID must be a positive integer")
        return cardId

    def _cardLabelRemovePrevious(self, record: CardInventoryRecord) -> None:
        for oldLabel in record.previousLabelPaths:
            if oldLabel != record.cardLabelPath:
                Path(oldLabel).unlink(missing_ok=True)

    def _cardLabelWrite(self, record: CardInventoryRecord) -> None:
        if not record.cardLabelPath:
            return
        payload = json.dumps(_cardLabelPayload(record), indent=2, sort_keys=True)
        self.filesystem.writeText(
            Path(record.cardLabelPath),
            payload + "\n",
            encoding="utf-8",
            stateKind="application-state",
        )

    def _contentDescribe(self, thumbnailPaths: list[Path]) -> tuple[str, str]:
        if not thumbnailPaths:
            return "", "no-thumbnails"
        logger.value("thumbnail samples", len(thumbnailPaths))
        if self.dryRun:
            logger.action("describe card thumbnails with grok vision")
            return "", "dry-run"
        try:
            summary = self._contentDescribeLive(thumbnailPaths).strip()
        except Exception as error:
            logger.warning("card content summary unavailable: %s", error)
            return "", "unavailable"
        return summary, "described" if summary else "unavailable"

    def _contentDescribeLive(self, thumbnailPaths: list[Path]) -> str:
        if self._visionDescribe is not None:
            return self._visionDescribe(thumbnailPaths)
        apiKey = (self._apiKey or os.environ.get("XAI_API_KEY") or "").strip()
        if not apiKey:
            raise RuntimeError("XAI_API_KEY is not set")
        from xai_sdk import Client
        from xai_sdk.chat import image, user

        images = []
        for path in thumbnailPaths:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            images.append(image(f"data:image/jpeg;base64,{encoded}", detail="low"))
        client = Client(api_key=apiKey)
        chat = client.chat.create(model=GROK_VISION_MODEL)
        chat.append(user(VISION_PROMPT, *images))
        response = chat.sample()
        return getattr(response, "content", "") or ""

    def _contentThumbnailsSample(
        self, files: tuple[CardFileRecord, ...], source: Path
    ) -> list[Path]:
        candidates = [item for item in files if item.kind == "thumbnail"]
        if not candidates:
            candidates = [
                item
                for item in files
                if item.kind == "photo"
                and Path(item.relativePath).suffix.lower() in JPEG_SUFFIXES
            ]
        if not candidates:
            return []
        ordered = sorted(
            candidates,
            key=lambda item: item.captureAt or item.modifiedAt or item.relativePath,
        )
        if len(ordered) <= THUMBNAIL_SAMPLE_LIMIT:
            chosen = ordered
        else:
            lastIndex = len(ordered) - 1
            indexes = sorted(
                {
                    round(index * lastIndex / (THUMBNAIL_SAMPLE_LIMIT - 1))
                    for index in range(THUMBNAIL_SAMPLE_LIMIT)
                }
            )
            chosen = [ordered[index] for index in indexes]
        return [source / item.relativePath for item in chosen]

    def _databaseConnect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.databasePath)
        connection.row_factory = sqlite3.Row
        return connection

    def _databaseFilesInsert(
        self,
        connection: sqlite3.Connection,
        inventoryId: int,
        files: tuple[CardFileRecord, ...],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO cardInventoryFile (
                inventoryId, relativePath, sizeBytes, modifiedAt, captureAt,
                kind, cameraKind
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    inventoryId,
                    item.relativePath,
                    item.sizeBytes,
                    item.modifiedAt,
                    item.captureAt,
                    item.kind,
                    item.cameraKind,
                )
                for item in files
            ],
        )

    def _databaseInitialize(self, connection: sqlite3.Connection) -> None:
        catalogueSchemaApply(connection)

    def _databaseSnapshotInsert(
        self, connection: sqlite3.Connection, record: CardInventoryRecord
    ) -> int:
        counts = record.fileCounts
        cursor = connection.execute(
            """
            INSERT INTO cardInventory (
                cardId, inventoriedAt, sourcePath, volumeLabel, filesystemId,
                cardSizeBytes, usedBytes, freeBytes, contentBytes,
                cardRatedGigabytes,
                dateStart, dateEnd, dateSource, cameraKinds,
                videoCount, photoCount, thumbnailCount, previewCount,
                sidecarCount, otherCount, thumbnailSampled, contentSummary,
                visionStatus, volumeKind,
                manufacturer, cameraModel, cameraSerial, firmwareVersion, cameraWifiMac, goproCardId, cardBrand
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.cardId,
                record.inventoriedAt,
                record.sourcePath,
                record.volumeLabel,
                record.filesystemId,
                record.capacity.totalBytes,
                record.capacity.usedBytes,
                record.capacity.freeBytes,
                record.capacity.contentBytes,
                record.cardRatedGigabytes,
                record.dateStart,
                record.dateEnd,
                record.dateSource,
                ",".join(record.cameraKinds),
                counts.get("video", 0),
                counts.get("photo", 0),
                counts.get("thumbnail", 0),
                counts.get("preview", 0),
                counts.get("sidecar", 0),
                counts.get("other", 0),
                record.thumbnailSampled,
                record.contentSummary,
                record.visionStatus,
                record.volumeKind,
                record.manufacturer,
                record.cameraModel,
                record.cameraSerial,
                record.firmwareVersion,
                record.cameraWifiMac,
                record.goproCardId,
                record.cardBrand,
            ),
        )
        return int(cursor.lastrowid)


def cameraInventoryRun(
    *,
    cardId: Optional[int] = None,
    source: Optional[Path] = None,
    dryRun: bool = True,
    databasePath: Optional[Path] = None,
    visionDescribe: Optional[Callable[[list[Path]], str]] = None,
    reassign: bool = False,
    brand: Optional[str] = None,
) -> CardInventoryRecord:
    service = CameraInventory(
        dryRun=dryRun, databasePath=databasePath, visionDescribe=visionDescribe
    )
    if source is None:
        if reassign:
            raise ValueError("--reassign requires SOURCE")
        if cardId is None:
            raise ValueError("card ID is required when SOURCE is omitted")
        record = service.inventoryShow(cardId)
        if record is None:
            raise RuntimeError(f"no inventory stored for card {cardId}")
        return record
    record = service.inventoryScan(source, cardId, reassign=reassign, brand=brand)
    if not dryRun:
        service.inventoryPersist(record)
    return record


def cameraInventorySummary(
    record: CardInventoryRecord,
    *,
    persisted: bool,
    databasePath: Path,
) -> str:
    persistedLabel = "yes" if persisted else "no (dry-run)"
    reassignLine = ""
    if record.previousCardId is not None:
        reassignLine = (
            f"  Reassign:         {record.previousCardId} -> {record.cardId}\n"
        )
    return f"""{_cardVolumeSummary(record, extra=reassignLine)}
  Card label:       {record.cardLabelPath or "none"}
  Database:         {databasePath}
  Persisted:        {persistedLabel}
"""


def _cardLabelFiles(root: Path) -> list[Path]:
    found: list[Path] = []
    try:
        children = list(root.iterdir())
    except OSError:
        return found
    for child in children:
        if not child.is_file():
            continue
        if (
            CARD_LABEL_NAME.fullmatch(child.name)
            or child.name == CAMERA_CARD_LABEL_LEGACY_FILENAME
        ):
            found.append(child)
    return found


def _cardLabelLocate(root: Path) -> tuple[Optional[Path], Optional[int]]:
    found: list[tuple[Path, int]] = []
    for path in _cardLabelFiles(root):
        match = CARD_LABEL_NAME.fullmatch(path.name)
        fileId = int(match.group(1)) if match else None
        jsonId = _cardLabelRead(path)
        if jsonId is None and fileId is None:
            continue
        if jsonId is not None and fileId is not None and jsonId != fileId:
            raise ValueError(
                f"card label {path} name is {fileId} but contents are {jsonId}"
            )
        found.append((path, jsonId if jsonId is not None else fileId))
    if not found:
        return None, None
    ids = {item[1] for item in found}
    if len(ids) > 1:
        names = ", ".join(path.name for path, _ in found)
        raise ValueError(f"multiple card labels at {root}: {names}")
    return found[0]


def _cardLabelPayload(record: CardInventoryRecord) -> dict:
    counts = record.fileCounts
    return {
        "application": "organiseMyVideo",
        "cameraKinds": list(record.cameraKinds),
        "cameraModel": record.cameraModel,
        "cameraSerial": record.cameraSerial,
        "cameraWifiMac": record.cameraWifiMac,
        "goproCardId": record.goproCardId,
        "cardBrand": record.cardBrand,
        "cardId": record.cardId,
        "cardProduct": record.cardProduct,
        "cardRatedGigabytes": record.cardRatedGigabytes,
        "cardSizeBytes": record.capacity.totalBytes,
        "contentBytes": record.capacity.contentBytes,
        "contentSummary": record.contentSummary,
        "dateEnd": record.dateEnd,
        "dateSource": record.dateSource,
        "dateStart": record.dateStart,
        "fileCounts": counts,
        "firmwareVersion": record.firmwareVersion,
        "freeBytes": record.capacity.freeBytes,
        "inventoriedAt": record.inventoriedAt,
        "manufacturer": record.manufacturer,
        "photoCount": counts.get("photo", 0),
        "sourcePath": record.sourcePath,
        "summary": _cardVolumeSummary(record).strip(),
        "thumbnailCount": counts.get("thumbnail", 0),
        "usedBytes": record.capacity.usedBytes,
        "videoCount": counts.get("video", 0),
        "visionStatus": record.visionStatus,
        "volumeLabel": record.volumeLabel,
    }


def _cardLabelPayloadRead(path: Optional[Path]) -> dict:
    if path is None or not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _cidDecode(hexCid: str) -> dict:
    cleaned = hexCid.strip().replace(" ", "")
    if len(cleaned) < 32:
        return {}
    try:
        raw = bytes.fromhex(cleaned[:32])
    except ValueError:
        return {}
    if len(raw) < 8:
        return {}
    product = raw[3:8].decode("ascii", errors="ignore").strip("\x00 ")
    return {"brand": CID_BRANDS.get(raw[0]), "product": product or None}


def _cidHexForPath(path: Path) -> Optional[str]:
    block = _mountBlockDevice(path)
    if block is None:
        return None
    current = block
    for _ in range(8):
        for candidate in (current / "cid", current / "device" / "cid"):
            if candidate.is_file():
                try:
                    value = candidate.read_text(encoding="ascii").strip()
                except OSError:
                    continue
                if value:
                    return value
        if current.parent == current:
            break
        current = current.parent
    return None


def _marketedGigabytes(totalBytes: Optional[int]) -> Optional[int]:
    if not totalBytes:
        return None
    for gigabytes in MARKETED_GIGABYTES:
        ratio = totalBytes / (gigabytes * 1_000_000_000)
        if 0.92 <= ratio <= 1.01:
            return gigabytes
    return None


def _ratedGigabytesResolve(totalBytes: Optional[int], stored: object) -> Optional[int]:
    derived = _marketedGigabytes(totalBytes)
    if derived:
        return derived
    if isinstance(stored, int) and stored in MARKETED_GIGABYTES:
        return stored
    return None


def _mountBlockDevice(path: Path) -> Optional[Path]:
    resolved = str(path.resolve())
    bestMinor = None
    bestLength = -1
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            left, _right = line.split(" - ", 1)
        except ValueError:
            continue
        fields = left.split()
        if len(fields) < 5:
            continue
        mountPoint = fields[4].replace("\\040", " ")
        if resolved == mountPoint or resolved.startswith(mountPoint.rstrip("/") + "/"):
            if len(mountPoint) > bestLength:
                bestMinor = fields[2]
                bestLength = len(mountPoint)
    if not bestMinor:
        return None
    sysBlock = Path("/sys/dev/block") / bestMinor
    return sysBlock if sysBlock.exists() else None


def _cardLabelRead(labelPath: Path) -> Optional[int]:
    if not labelPath.is_file():
        return None
    try:
        raw = labelPath.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        loaded = raw
    if isinstance(loaded, dict):
        loaded = loaded.get("cardId")
    try:
        cardId = int(loaded)
    except (TypeError, ValueError):
        raise ValueError(f"card label {labelPath} does not contain a numeric card ID")
    if cardId < 1:
        raise ValueError(f"card label {labelPath} does not contain a positive card ID")
    return cardId


def _cardLabelRoot(source: Path) -> Path:
    current = source.resolve()
    seen: list[Path] = []
    while True:
        seen.append(current)
        existing, _storedId = _cardLabelLocate(current)
        if existing is not None:
            return current
        parent = current.parent
        if parent == current or os.path.ismount(str(current)):
            break
        current = parent
    for path in reversed(seen):
        if _cardLooksLikeVolumeRoot(path):
            return path
    return source


def _cameraIdentityCollect(root: Path, cameraKinds: tuple[str, ...]) -> CameraIdentity:
    gopro = _goproIdentityRead(root)
    if gopro.manufacturer:
        return gopro
    transcend = _transcendIdentityRead(root)
    if transcend.manufacturer:
        return transcend
    if "gopro" in cameraKinds:
        return CameraIdentity(manufacturer="GoPro")
    if "dji" in cameraKinds:
        return CameraIdentity(manufacturer="DJI")
    if "slr" in cameraKinds:
        return CameraIdentity(manufacturer="Canon")
    return CameraIdentity()


def _goproCardIdRead(root: Path) -> Optional[str]:
    try:
        return _identityText((root / "MISC" / "card").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _goproIdentityRead(root: Path) -> CameraIdentity:
    path = root / "MISC" / "version.txt"
    if not path.is_file():
        if (root / "Get_started_with_GoPro.url").is_file():
            return CameraIdentity(manufacturer="GoPro")
        return CameraIdentity()
    try:
        raw = path.read_text(encoding="utf-8-sig")
        data = json.loads(re.sub(r",(\s*})\s*$", r"\1", raw))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return CameraIdentity(manufacturer="GoPro")
    if not isinstance(data, dict):
        return CameraIdentity(manufacturer="GoPro")
    return CameraIdentity(
        manufacturer="GoPro",
        model=_identityText(data.get("camera type")),
        serial=_identityText(data.get("camera serial number")),
        firmware=_identityText(data.get("firmware version")),
        wifiMac=_identityText(data.get("wifi mac")),
    )


def _identityText(value: object) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _transcendIdentityRead(root: Path) -> CameraIdentity:
    try:
        names = [child.name for child in root.iterdir() if child.is_dir()]
    except OSError:
        return CameraIdentity()
    for name in names:
        if not DASHCAM_MODEL_FOLDER.fullmatch(name):
            continue
        upper = name.upper()
        if upper.startswith("DPB"):
            return CameraIdentity(
                manufacturer="Transcend", model=f"DrivePro Body {name[3:]}"
            )
        if upper.startswith("DP"):
            return CameraIdentity(
                manufacturer="Transcend", model=f"DrivePro {name[2:]}"
            )
    return CameraIdentity()


def _cardLooksLikeVolumeRoot(path: Path) -> bool:
    try:
        names = {child.name.lower() for child in path.iterdir()}
    except OSError:
        return False
    if "dcim" in names:
        return True
    if names & {"n_video", "n-video", "p_video", "p-video", "record", "system"}:
        return True
    return any(DASHCAM_MODEL_FOLDER.fullmatch(name) for name in names)


def _cardVolumeSummary(record: CardInventoryRecord, extra: str = "") -> str:
    counts = record.fileCounts
    content = record.contentSummary or record.visionStatus
    identity = ""
    camera = " ".join(
        part for part in (record.manufacturer, record.cameraModel) if part
    )
    if camera:
        identity += f"  Camera:           {camera}\n"
    if record.cameraSerial:
        identity += f"  Serial:           {record.cameraSerial}\n"
    if record.firmwareVersion:
        identity += f"  Firmware:         {record.firmwareVersion}\n"
    if record.cameraWifiMac:
        identity += f"  Camera Wi-Fi MAC: {record.cameraWifiMac}\n"
    if record.goproCardId:
        identity += f"  GoPro card token: {record.goproCardId}\n"
    cardSize = (
        f"  Card size:        {record.cardRatedGigabytes} GB\n"
        if record.cardRatedGigabytes
        else ""
    )
    return f"""CAMERA CARD INVENTORY
  Card ID:          {record.cardId}
  Brand:            {record.cardBrand or "unknown"}
{extra}  Source:           {record.sourcePath}
  Volume:           {record.volumeLabel}
{cardSize}  Free space:       {_bytesFormat(record.capacity.freeBytes)}
  Content size:     {_bytesFormat(record.capacity.contentBytes)}
  Volume size:      {_bytesFormat(record.capacity.totalBytes)}
  Date range:       {_dateRangeFormat(record.dateStart, record.dateEnd, record.dateSource)}
{identity}  Videos:           {counts.get("video", 0)}
  Photos:           {counts.get("photo", 0)}
{_suffixCountLines(record)}  Thumbnails:       {counts.get("thumbnail", 0)}
  Content:          {content}
"""


def _bytesFormat(value: Optional[int]) -> str:
    if value is None:
        return "unknown"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(value)} B"


def _dateRangeFormat(
    dateStart: Optional[str], dateEnd: Optional[str], dateSource: str
) -> str:
    if not dateStart:
        return f"unknown ({dateSource})"
    startDay = dateStart[:10]
    endDay = (dateEnd or dateStart)[:10]
    if startDay == endDay:
        return f"{startDay} ({dateSource})"
    return f"{startDay} to {endDay} ({dateSource})"


def _datetimeFormat(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.replace(microsecond=0).isoformat()


def _suffixCountLines(record: CardInventoryRecord) -> str:
    """Return CR3/JPEG/MP4 count lines when those media types are present."""

    from .cameraDetect import cameraMediaSuffixCounts

    mediaPaths = tuple(
        item.relativePath for item in record.files if item.kind in {"photo", "video"}
    )
    counts = cameraMediaSuffixCounts(mediaPaths)
    if "slr" not in record.cameraKinds and counts["cr3"] == 0:
        return ""
    return (
        f"  CR3:              {counts['cr3']}\n"
        f"  JPEG:             {counts['jpeg']}\n"
        f"  MP4:              {counts['mp4']}\n"
    )


def _fileCameraKind(relativePath: str) -> str:
    posix = relativePath.replace("\\", "/")
    name = posix.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0]
    if name.upper().startswith("DJI_"):
        return "dji"
    for part in posix.split("/"):
        if part.upper().endswith("GOPRO"):
            return "gopro"
        if DJI_MEDIA_FOLDER.fullmatch(part):
            return "dji"
    if GOPRO_STEM.match(stem):
        return "gopro"
    suffix = f".{name.rsplit('.', 1)[-1].lower()}" if "." in name else ""
    if suffix in {".cr3", ".jpg", ".jpeg", ".mp4"} and (
        suffix == ".cr3"
        or CANON_STEM.match(stem)
        or any(CANON_FOLDER.fullmatch(part) for part in posix.split("/")[:-1])
    ):
        return "slr"
    if _fileDashcamMatch(posix, name):
        return "dashcam"
    return "unknown"


def _fileDashcamMatch(posixPath: str, fileName: str) -> bool:
    if DASHCAM_FILENAME.match(fileName):
        return True
    for part in posixPath.split("/"):
        if part.lower() in DASHCAM_DIRECTORY_NAMES:
            return True
        if DASHCAM_NUMBERED_FOLDER.fullmatch(part) or DASHCAM_MODEL_FOLDER.fullmatch(
            part
        ):
            return True
    return False


def _fileCounts(files: tuple[CardFileRecord, ...]) -> dict[str, int]:
    counts = {
        "video": 0,
        "photo": 0,
        "thumbnail": 0,
        "preview": 0,
        "sidecar": 0,
        "other": 0,
    }
    for item in files:
        counts[item.kind if item.kind in counts else "other"] += 1
    return counts


def _fileIgnored(fileName: str) -> bool:
    lowered = fileName.lower()
    return (
        fileName.startswith("._")
        or lowered in IGNORED_FILE_NAMES
        or CARD_LABEL_NAME.fullmatch(fileName) is not None
        or lowered.endswith(".log")
    )


def _fileKind(path: Path) -> str:
    return KIND_BY_SUFFIX.get(path.suffix.lower(), "other")


def _filesystemIdRead(source: Path) -> Optional[str]:
    try:
        return str(source.stat().st_dev)
    except OSError:
        return None


def _recordFromRow(row: sqlite3.Row, files: list[sqlite3.Row]) -> CardInventoryRecord:
    cameraKinds = tuple(part for part in (row["cameraKinds"] or "").split(",") if part)
    return CardInventoryRecord(
        cardId=row["cardId"],
        sourcePath=row["sourcePath"],
        inventoriedAt=row["inventoriedAt"],
        volumeLabel=row["volumeLabel"] or "",
        filesystemId=row["filesystemId"],
        capacity=CardCapacity(
            totalBytes=row["cardSizeBytes"],
            usedBytes=row["usedBytes"],
            freeBytes=row["freeBytes"],
            contentBytes=row["contentBytes"],
        ),
        dateStart=row["dateStart"],
        dateEnd=row["dateEnd"],
        dateSource=row["dateSource"],
        cameraKinds=cameraKinds,
        fileCounts={
            "video": row["videoCount"],
            "photo": row["photoCount"],
            "thumbnail": row["thumbnailCount"],
            "preview": row["previewCount"],
            "sidecar": row["sidecarCount"],
            "other": row["otherCount"],
        },
        contentSummary=row["contentSummary"] or "",
        visionStatus=row["visionStatus"],
        volumeKind=row["volumeKind"],
        manufacturer=row["manufacturer"],
        cameraModel=row["cameraModel"],
        cameraSerial=row["cameraSerial"],
        firmwareVersion=row["firmwareVersion"],
        cardBrand=row["cardBrand"],
        cameraWifiMac=row["cameraWifiMac"],
        goproCardId=row["goproCardId"],
        thumbnailSampled=row["thumbnailSampled"],
        cardRatedGigabytes=(
            row["cardRatedGigabytes"] if "cardRatedGigabytes" in row.keys() else None
        ),
        files=tuple(
            CardFileRecord(
                relativePath=item["relativePath"],
                sizeBytes=item["sizeBytes"],
                modifiedAt=item["modifiedAt"],
                captureAt=item["captureAt"],
                kind=item["kind"],
                cameraKind=item["cameraKind"],
            )
            for item in files
        ),
    )


def _timestampNow() -> str:
    return _datetimeFormat(datetime.now(timezone.utc))
