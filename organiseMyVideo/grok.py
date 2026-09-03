"""Official xAI Imagine archive: generate with storage_options, list, download."""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from .constants import (
    GROK_CATALOG_FILE,
    GROK_DOWNLOAD_DIR,
    GROK_IMAGE_MODEL,
    GROK_MEDIA_EXTENSIONS,
    GROK_VIDEO_MODEL,
)
from organiseMyProjects.logUtils import getLogger  # type: ignore

logger = getLogger()

_IMAGE_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class ImagineArchive:
    """Generate, list, and download Imagine media through the xAI API."""

    def __init__(
        self,
        dryRun: bool = True,
        client: Any = None,
        apiKey: Optional[str] = None,
        catalogPath: Optional[Path] = None,
        downloadDir: Optional[Path] = None,
        pageSize: int = 100,
    ):
        """Initialise the archive client.

        Args:
            dryRun: When True, log planned generate/download work without doing it.
            client: Optional injected xAI client. Tests pass a fake here.
            apiKey: Optional API key. Defaults to ``XAI_API_KEY``.
            catalogPath: Local JSON catalog of generated assets.
            downloadDir: Directory that receives downloaded media files.
            pageSize: Files API page size used while listing stored media.
        """
        self.dryRun = dryRun
        self._client = client
        self._apiKey = apiKey
        self.catalogPath = Path(catalogPath) if catalogPath else GROK_CATALOG_FILE
        self.downloadDir = Path(downloadDir) if downloadDir else GROK_DOWNLOAD_DIR
        self.pageSize = pageSize

    ## download

    def fileDownload(self, fileId: Optional[str] = None) -> dict:
        """Download stored Imagine media into the download directory.

        Args:
            fileId: Download only this Files API id. When omitted, download every
                listed image and video.

        Returns:
            Counts for downloaded, skipped, and error items.
        """
        stats = {"downloaded": 0, "skipped": 0, "errors": 0}
        records = self.fileList()
        if fileId:
            records = [record for record in records if record["fileId"] == fileId]
            if not records:
                raise RuntimeError(f"no stored imagine media matched file id {fileId}")

        logger.doing("downloading imagine media")
        logger.value("download directory", self.downloadDir)
        logger.value("files", len(records))

        if not self.dryRun:
            self.downloadDir.mkdir(parents=True, exist_ok=True)

        client = None if self.dryRun else self._clientGet()
        for record in records:
            dest = self._downloadDestination(record)
            if dest.exists():
                logger.value("imagine media already exists, skipping", dest)
                stats["skipped"] += 1
                continue

            logger.action(f"download imagine media: {record['fileId']} -> {dest}")
            if self.dryRun:
                stats["downloaded"] += 1
                continue

            try:
                dest.write_bytes(client.files.content(record["fileId"]))
                self._catalogLocalPathUpdate(record["fileId"], dest)
                stats["downloaded"] += 1
            except Exception as error:
                logger.error("failed downloading %s: %s", record["fileId"], error)
                stats["errors"] += 1

        logger.done("imagine download complete")
        return stats

    ## generate

    def imageGenerate(
        self,
        prompt: str,
        filename: Optional[str] = None,
        imagePath: Optional[str] = None,
    ) -> dict:
        """Generate an image and persist it with storage_options.

        Args:
            prompt: Text prompt.
            filename: Optional Files API filename. A timestamped name is used
                when omitted.
            imagePath: Optional local path or URL used as an edit reference.

        Returns:
            Catalog record for the stored file. In dry-run the file id is empty.
        """
        return self._mediaGenerate(
            kind="image",
            prompt=prompt,
            filename=filename,
            imagePath=imagePath,
        )

    def videoGenerate(
        self,
        prompt: str,
        filename: Optional[str] = None,
        imagePath: Optional[str] = None,
        duration: int = 6,
    ) -> dict:
        """Generate a video and persist it with storage_options.

        Args:
            prompt: Text prompt.
            filename: Optional Files API filename.
            imagePath: Optional still image path or URL for image-to-video.
            duration: Clip length in seconds.

        Returns:
            Catalog record for the stored file. In dry-run the file id is empty.
        """
        return self._mediaGenerate(
            kind="video",
            prompt=prompt,
            filename=filename,
            imagePath=imagePath,
            duration=duration,
        )

    ## list

    def fileList(self) -> list[dict]:
        """Return stored Imagine image and video files from the Files API."""
        self._apiKeyRequire()
        client = self._clientGet()
        logger.doing("listing stored imagine media")
        records: list[dict] = []
        token = None
        while True:
            kwargs: dict[str, Any] = {
                "limit": self.pageSize,
                "order": "desc",
                "sort_by": "created_at",
            }
            if token:
                kwargs["pagination_token"] = token
            response = client.files.list(**kwargs)
            page = list(getattr(response, "data", None) or [])
            for item in page:
                record = _fileRecord(item)
                if _isMediaFile(record):
                    records.append(record)
            if len(page) < self.pageSize:
                break
            token = getattr(response, "pagination_token", None)
            if not token:
                break
        logger.value("imagine media files", len(records))
        logger.done("imagine list complete")
        return records

    ## catalog

    def _catalogLoad(self) -> dict:
        """Return the local catalog object, or an empty catalog when missing."""
        if not self.catalogPath.exists():
            return {"version": 1, "items": []}
        try:
            loaded = json.loads(self.catalogPath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            logger.warning(
                "could not read grok catalog %s: %s", self.catalogPath, error
            )
            return {"version": 1, "items": []}
        if not isinstance(loaded, dict):
            return {"version": 1, "items": []}
        items = loaded.get("items")
        if not isinstance(items, list):
            loaded["items"] = []
        loaded.setdefault("version", 1)
        return loaded

    def _catalogLocalPathUpdate(self, fileId: str, dest: Path) -> None:
        """Record the local download path for *fileId* when the catalog has it."""
        catalog = self._catalogLoad()
        changed = False
        for item in catalog["items"]:
            if item.get("fileId") == fileId:
                item["localPath"] = str(dest)
                changed = True
                break
        if changed:
            self._catalogSave(catalog)

    def _catalogRecord(self, record: dict) -> None:
        """Append *record* to the local catalog."""
        catalog = self._catalogLoad()
        catalog["items"].append(record)
        self._catalogSave(catalog)

    def _catalogSave(self, catalog: dict) -> None:
        """Write *catalog* JSON to disk."""
        self.catalogPath.parent.mkdir(parents=True, exist_ok=True)
        self.catalogPath.write_text(
            json.dumps(catalog, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    ## client

    def _apiKeyRequire(self) -> None:
        """Fail fast when no client was injected and XAI_API_KEY is missing."""
        if self._client is not None:
            return
        apiKey = (self._apiKey or os.environ.get("XAI_API_KEY") or "").strip()
        if not apiKey:
            raise RuntimeError(
                "XAI_API_KEY is not set; create a key at https://console.x.ai"
            )
        self._apiKey = apiKey

    def _clientGet(self) -> Any:
        """Return the injected client or construct one from XAI_API_KEY."""
        if self._client is not None:
            return self._client
        self._apiKeyRequire()
        apiKey = self._apiKey
        try:
            from xai_sdk import Client
        except ImportError as error:
            raise RuntimeError(
                "xai-sdk is required for grok commands: pip install xai-sdk"
            ) from error
        self._client = Client(api_key=apiKey)
        return self._client

    ## generate internals

    def _mediaGenerate(
        self,
        kind: str,
        prompt: str,
        filename: Optional[str] = None,
        imagePath: Optional[str] = None,
        duration: int = 6,
    ) -> dict:
        """Run one persisted image or video generation."""
        cleanedPrompt = prompt.strip()
        if not cleanedPrompt:
            raise RuntimeError("prompt is required for grok generate")
        if kind not in {"image", "video"}:
            raise RuntimeError(f"unsupported imagine kind: {kind}")
        if duration < 1 or duration > 15:
            raise RuntimeError("video duration must be between 1 and 15 seconds")

        model = GROK_IMAGE_MODEL if kind == "image" else GROK_VIDEO_MODEL
        suffix = ".jpg" if kind == "image" else ".mp4"
        storedName = (
            filename.strip() if filename else _filenameFromPrompt(cleanedPrompt, suffix)
        )
        record = {
            "fileId": "",
            "filename": storedName,
            "prompt": cleanedPrompt,
            "kind": kind,
            "model": model,
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "localPath": None,
        }

        logger.doing(f"generating imagine {kind}")
        logger.value("model", model)
        logger.value("filename", storedName)
        logger.action(f"generate imagine {kind}: {cleanedPrompt}")
        self._apiKeyRequire()

        if self.dryRun:
            logger.done(f"imagine {kind} generation skipped")
            return record

        client = self._clientGet()
        storageOptions = {"filename": storedName}
        imageUrl = _imageUrlFromPath(imagePath) if imagePath else None
        if kind == "image":
            sampleKwargs: dict[str, Any] = {
                "prompt": cleanedPrompt,
                "model": model,
                "storage_options": storageOptions,
            }
            if imageUrl:
                sampleKwargs["image_url"] = imageUrl
            response = client.image.sample(**sampleKwargs)
        else:
            generateKwargs: dict[str, Any] = {
                "prompt": cleanedPrompt,
                "model": model,
                "duration": duration,
                "storage_options": storageOptions,
            }
            if imageUrl:
                generateKwargs["image_url"] = imageUrl
            response = client.video.generate(**generateKwargs)

        storageError = getattr(response, "storage_error", None)
        if storageError:
            raise RuntimeError(f"imagine storage failed: {storageError}")
        fileOutput = getattr(response, "file_output", None)
        fileId = (
            getattr(fileOutput, "file_id", None) if fileOutput is not None else None
        )
        if not fileId:
            raise RuntimeError(
                "generation succeeded but no file_output was returned; "
                "storage_options may have failed"
            )
        record["fileId"] = fileId
        record["filename"] = getattr(fileOutput, "filename", None) or storedName
        self._catalogRecord(record)
        logger.value("file id", fileId)
        logger.done(f"imagine {kind} generation complete")
        return record

    ## utilities

    def _downloadDestination(self, record: dict) -> Path:
        """Return the local path for *record*."""
        filename = Path(record.get("filename") or record["fileId"]).name
        return self.downloadDir / filename


def grokCommandRun(args: Any, dryRun: bool) -> dict:
    """Dispatch a parsed ``grok`` CLI action.

    Args:
        args: argparse namespace from ``buildParser``.
        dryRun: When True, generate and download do not change remote or local
            state. List still reads the Files API.

    Returns:
        Action result payload (catalog record, file list, or download stats).
    """
    archive = ImagineArchive(dryRun=dryRun)
    action = getattr(args, "grokAction", None)
    if action == "generate":
        kind = getattr(args, "kind", "image") or "image"
        prompt = getattr(args, "prompt", "") or ""
        filename = getattr(args, "filename", None)
        imagePath = getattr(args, "image", None)
        if kind == "video":
            duration = getattr(args, "duration", 6) or 6
            return archive.videoGenerate(
                prompt=prompt,
                filename=filename,
                imagePath=imagePath,
                duration=duration,
            )
        return archive.imageGenerate(
            prompt=prompt,
            filename=filename,
            imagePath=imagePath,
        )
    if action == "list":
        records = archive.fileList()
        _listPrint(records)
        return {"files": records}
    if action == "download":
        return archive.fileDownload(fileId=getattr(args, "file_id", None))
    raise RuntimeError(f"unknown grok action: {action}")


def _filenameFromPrompt(prompt: str, suffix: str) -> str:
    """Build a filesystem-safe storage filename from *prompt* and *suffix*."""
    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:48]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{slug or 'imagine'}{suffix}"


def _fileRecord(item: Any) -> dict:
    """Normalise a Files API object or fake into a plain record."""
    fileId = getattr(item, "id", None) or getattr(item, "file_id", "") or ""
    filename = getattr(item, "filename", "") or ""
    sizeBytes = getattr(item, "size", None)
    if sizeBytes is None:
        sizeBytes = getattr(item, "bytes", 0) or 0
    contentType = (
        getattr(item, "content_type", None) or getattr(item, "mime_type", None) or ""
    )
    createdAt = getattr(item, "created_at", None)
    return {
        "fileId": fileId,
        "filename": filename,
        "sizeBytes": int(sizeBytes or 0),
        "contentType": str(contentType),
        "createdAt": str(createdAt) if createdAt is not None else "",
    }


def _imageUrlFromPath(imagePath: str) -> str:
    """Return a URL or data URL for a local image path."""
    cleaned = imagePath.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https", "data"}:
        return cleaned
    path = Path(cleaned).expanduser()
    if not path.is_file():
        raise RuntimeError(f"image file not found: {path}")
    mime = _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _isMediaFile(record: dict) -> bool:
    """Return True when *record* looks like an image or video file."""
    contentType = (record.get("contentType") or "").lower()
    if contentType.startswith("image/") or contentType.startswith("video/"):
        return True
    suffix = Path(record.get("filename") or "").suffix.lower()
    return suffix in GROK_MEDIA_EXTENSIONS


def _listPrint(records: list[dict]) -> None:
    """Write a simple file listing to the logger."""
    if not records:
        logger.info("no stored imagine media files")
        return
    for record in records:
        logger.info(
            f"{record['fileId']}  {record['filename']}  {record['sizeBytes']} bytes"
        )
