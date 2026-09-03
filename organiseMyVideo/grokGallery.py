"""Grok scraper: authentication, Firefox session import, and media download."""

import os
import re
import json
import shutil
import platform
import sqlite3
import subprocess
import tempfile
import configparser
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, List, Optional

# Playwright is an optional dependency used only by --grok.  We import it at
# module level so tests can patch ``organiseMyVideo.grokGallery.sync_playwright``.
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except ImportError:
    sync_playwright = None  # type: ignore

from .constants import (
    GROK_CREDENTIALS_FILE,
    GROK_DOWNLOAD_DIR,
    GROK_MEDIA_EXTENSIONS,
    GROK_SESSION_FILE,
    GROK_USER_CONTENT_DOMAINS,
    _GROK_SAVED_URL,
    _PLAYWRIGHT_INIT_SCRIPT,
)
from organiseMyProjects.logUtils import getLogger  # type: ignore

logger = getLogger()

# Playwright's maximum allowed cookie expires value (from kMaxCookieExpiresDateInSeconds
# in playwright/driver/package/lib/server/network.js).  Any timestamp beyond this
# (9999-12-31 23:59:59 UTC) is rejected by Playwright's rewriteCookies() with the
# "Cookie should have a valid expires" error, even though the value is a positive integer.
_PLAYWRIGHT_MAX_COOKIE_EXPIRES = 253402300799
_GROK_ASSETS_API = "https://grok.com/rest/assets"
_GROK_ASSETS_CDN = "https://assets.grok.com/"
_GROK_POST_LIST_API = "https://grok.com/rest/media/post/list"
_GROK_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
)
_IMAGE_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
_VIDEO_MIME_TYPES = ("video/mp4",)


class GrokGallery:
    """Download the current user's grok.com Imagine generations."""

    def __init__(
        self,
        dryRun: bool = True,
        downloadDir: Optional[Path] = None,
        listAssets: Optional[Callable[..., list]] = None,
        fetchBytes: Optional[Callable[[str], bytes]] = None,
    ):
        """Initialise the gallery client.

        Args:
            dryRun: When True, log planned downloads without writing files.
            downloadDir: Directory that receives downloaded media.
            listAssets: Optional injected asset lister used by tests.
            fetchBytes: Optional injected downloader used by tests.
        """
        self.dryRun = dryRun
        self.downloadDir = Path(downloadDir) if downloadDir else GROK_DOWNLOAD_DIR
        self._listAssets = listAssets
        self._fetchBytes = fetchBytes

    ## generated library

    def downloadGeneratedMedia(
        self,
        sessionFile: Path = GROK_SESSION_FILE,
    ) -> dict:
        """Download Imagine files this account generated, not the public feed.

        Lists this account's Imagine library: generated assets in the Imagine
        workspace and Imagine-mode conversations. The public explore feed is
        never downloaded.
        """
        self._sessionEnsure(sessionFile)
        cookies = self._sessionCookiesLoad(sessionFile)
        if self._listAssets is not None:
            assets = self._listAssets()
        else:
            assets = self._generatedAssetsList(cookies)
        if not assets:
            raise RuntimeError(
                "this grok.com login has no stored Imagine generations "
                "(public explore images are not downloaded). "
                "log into the same Firefox profile you used to create them, "
                "then run --import-firefox-session --confirm"
            )
        logger.doing("downloading generated grok.com imagine media")
        logger.value("generated assets", len(assets))
        stats = self._downloadAssetFiles(assets, cookies)
        stats["assetsFound"] = len(assets)
        logger.done("generated grok.com imagine download complete")
        return stats

    def _assetBytes(self, url: str, cookieHeader: str) -> bytes:
        """Return the body of *url* using the grok.com session."""
        if self._fetchBytes is not None:
            return self._fetchBytes(url)
        request = urllib.request.Request(
            url,
            headers=self._grokHeaders(cookieHeader, jsonAccept=False),
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()

    def _assetDownloadUrl(self, asset: dict) -> str:
        """Return the CDN URL for a grok.com asset record."""
        if asset.get("url"):
            return str(asset["url"])
        assetId = asset.get("assetId") or "asset"
        key = asset.get("key") or f"users/x/{assetId}/content"
        return f"{_GROK_ASSETS_CDN}{key}?cache=1"

    def _assetFilename(self, asset: dict) -> str:
        """Return a local filename for *asset*."""
        assetId = str(asset.get("assetId") or "asset")
        urlPath = urllib.parse.urlparse(str(asset.get("url") or "")).path
        urlSuffix = Path(urlPath).suffix.lower()
        if urlSuffix in {".mp4", ".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".jpg" if urlSuffix == ".jpeg" else urlSuffix
        else:
            mime = str(asset.get("mimeType") or "").lower()
            mediaType = str(asset.get("mediaType") or "")
            if mime.startswith("video/") or "VIDEO" in mediaType:
                suffix = ".mp4"
            else:
                suffix = {
                    "image/png": ".png",
                    "image/webp": ".webp",
                }.get(mime, ".jpg")
        return f"{assetId}{suffix}"

    def _assetsJsonGet(self, url: str, cookieHeader: str) -> str:
        """GET an authenticated grok.com JSON URL."""
        return self._grokJsonRequest(url, cookieHeader)

    def _bestMediaUrl(self, post: dict) -> str:
        """Return the highest-quality media URL on *post*, or empty."""
        mediaType = str(post.get("mediaType") or "")
        mime = str(post.get("mimeType") or "")
        if "VIDEO" in mediaType or mime.startswith("video/"):
            return (
                post.get("hd1080MediaUrl")
                or post.get("hdMediaUrl")
                or post.get("mediaUrl")
                or ""
            )
        return post.get("mediaUrl") or post.get("hdMediaUrl") or ""

    def _cookieHeader(self, cookies: List[dict], host: str = "grok.com") -> str:
        """Build a Cookie header for *host*, keeping one value per name."""
        selected: dict[str, tuple[int, dict]] = {}
        for cookie in cookies:
            name = cookie.get("name")
            domain = str(cookie.get("domain") or "")
            if not name:
                continue
            domainName = domain[1:] if domain.startswith(".") else domain
            if host != domainName and not host.endswith("." + domainName):
                continue
            score = 2 if domainName == host else 1
            previous = selected.get(name)
            if previous is None or score > previous[0]:
                selected[name] = (score, cookie)
        return "; ".join(
            f"{cookie['name']}={cookie.get('value', '')}"
            for _, cookie in selected.values()
        )

    def _grokHeaders(self, cookieHeader: str, jsonAccept: bool = True) -> dict:
        """Return grok.com headers that pass Cloudflare's browser check."""
        headers = {
            "Accept": "application/json" if jsonAccept else "*/*",
            "Cookie": cookieHeader,
            "Origin": "https://grok.com",
            "Referer": "https://grok.com/imagine",
            "User-Agent": _GROK_BROWSER_USER_AGENT,
        }
        if jsonAccept:
            headers["Content-Type"] = "application/json"
        return headers

    def _grokJsonRequest(
        self,
        url: str,
        cookieHeader: str,
        payload: Optional[dict] = None,
    ) -> str:
        """GET or POST JSON on grok.com using the imported Firefox session."""
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers=self._grokHeaders(cookieHeader, jsonAccept=True),
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise RuntimeError(
                    "grok.com session expired or Cloudflare blocked the request; "
                    "log in with Firefox and run --import-firefox-session --confirm"
                ) from error
            raise RuntimeError(f"grok.com request failed: HTTP {error.code}") from error

    def _assetsQuery(
        self,
        cookies: List[dict],
        mimeTypes: tuple[str, ...],
        source: str,
    ) -> List[dict]:
        """Paginate ``/rest/assets`` for *mimeTypes* and *source*."""
        records: List[dict] = []
        token = None
        cookieHeader = self._cookieHeader(cookies, host="grok.com")
        while True:
            params: list[tuple[str, str]] = [
                ("pageSize", "100"),
                ("orderBy", "ORDER_BY_LAST_USE_TIME"),
                ("source", source),
                ("includeImagineFiles", "true"),
            ]
            for mime in mimeTypes:
                params.append(("mimeTypes", mime))
            if token:
                params.append(("pageToken", token))
            url = f"{_GROK_ASSETS_API}?{urllib.parse.urlencode(params)}"
            payload = json.loads(self._grokJsonRequest(url, cookieHeader))
            page = payload.get("assets") or []
            if not isinstance(page, list):
                page = []
            records.extend(item for item in page if isinstance(item, dict))
            token = payload.get("nextPageToken") or None
            if not token or len(page) < 100:
                break
        return records

    def _downloadAssetFiles(self, assets: List[dict], cookies: List[dict]) -> dict:
        """Download generated assets into the download directory."""
        stats = {"downloaded": 0, "skipped": 0, "errors": 0}
        if not self.dryRun:
            self.downloadDir.mkdir(parents=True, exist_ok=True)
        cookieHeader = self._cookieHeader(cookies, host="grok.com")
        for asset in assets:
            filename = self._assetFilename(asset)
            dest = self.downloadDir / filename
            url = self._assetDownloadUrl(asset)
            if dest.exists():
                logger.value("imagine media already exists, skipping", dest)
                stats["skipped"] += 1
                continue
            logger.action(f"download generated imagine media: {url} -> {dest}")
            if self.dryRun:
                stats["downloaded"] += 1
                continue
            try:
                dest.write_bytes(self._assetBytes(url, cookieHeader))
                stats["downloaded"] += 1
            except Exception as error:
                logger.error("failed downloading %s: %s", url, error)
                stats["errors"] += 1
        return stats

    def _generatedAssetsList(self, cookies: List[dict]) -> List[dict]:
        """Return Imagine files owned by this grok.com login, never the public feed."""
        cookieHeader = self._cookieHeader(cookies, host="grok.com")
        records: List[dict] = []
        seen: set[str] = set()
        for asset in self._imagineWorkspaceAssets(cookieHeader):
            record = self._assetRecordFromMetadata(asset)
            if record is None:
                continue
            assetId = record["assetId"]
            if assetId in seen:
                continue
            seen.add(assetId)
            records.append(record)
        for conversation in self._imagineConversations(cookieHeader):
            metadata = conversation.get("latestAssetMetadata")
            if not isinstance(metadata, dict):
                continue
            record = self._assetRecordFromMetadata(metadata)
            if record is None:
                continue
            assetId = record["assetId"]
            if assetId in seen:
                continue
            seen.add(assetId)
            records.append(record)
        return records

    def _assetRecordFromMetadata(self, asset: dict) -> Optional[dict]:
        """Build a download record from an Imagine asset-metadata object."""
        assetId = str(asset.get("assetId") or "")
        if not assetId:
            return None
        fileSource = str(asset.get("fileSource") or "")
        if fileSource == "SELF_UPLOAD_FILE_SOURCE":
            return None
        mime = str(asset.get("mimeType") or "")
        if mime == "application/octet-stream":
            return None
        url = asset.get("hd1080Key") or asset.get("hdKey") or asset.get("url") or ""
        if url and not str(url).startswith("http"):
            url = self._assetDownloadUrl({"key": url, "assetId": assetId})
        if not url:
            key = asset.get("key")
            if key:
                url = self._assetDownloadUrl({"key": key, "assetId": assetId})
        if not url:
            return None
        return {
            "assetId": assetId,
            "url": url,
            "mimeType": mime,
            "key": asset.get("key") or "",
        }

    def _imagineConversations(self, cookieHeader: str) -> List[dict]:
        """Return Imagine-mode conversations for this login."""
        records: List[dict] = []
        token = None
        while True:
            params: list[tuple[str, str]] = [
                ("pageSize", "40"),
                ("kind", "CONVERSATION_KIND_IMAGINE"),
                ("enableNsfw", "true"),
            ]
            if token:
                params.append(("pageToken", token))
            url = (
                "https://grok.com/rest/app-chat/conversations?"
                + urllib.parse.urlencode(params)
            )
            body = json.loads(self._grokJsonRequest(url, cookieHeader))
            page = body.get("conversations") or []
            if not isinstance(page, list):
                page = []
            records.extend(item for item in page if isinstance(item, dict))
            token = body.get("nextPageToken") or None
            if not token or not page:
                break
        return records

    def _imagineWorkspaceAssets(self, cookieHeader: str) -> List[dict]:
        """Return assets in the Imagine workspace, paginated."""
        records: List[dict] = []
        token = None
        mimeTypes = (
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "video/mp4",
        )
        while True:
            params: list[tuple[str, str]] = [
                ("pageSize", "100"),
                ("includeImagineFiles", "true"),
                ("workspaceKind", "WORKSPACE_KIND_IMAGINE_ALL"),
                ("orderBy", "ORDER_BY_CREATE_TIME"),
            ]
            for mime in mimeTypes:
                params.append(("mimeTypes", mime))
            if token:
                params.append(("pageToken", token))
            url = f"{_GROK_ASSETS_API}?{urllib.parse.urlencode(params)}"
            body = json.loads(self._grokJsonRequest(url, cookieHeader))
            page = body.get("assets") or []
            if not isinstance(page, list):
                page = []
            records.extend(item for item in page if isinstance(item, dict))
            token = body.get("nextPageToken") or None
            if not token or not page:
                break
        return records

    def _mediaFromPost(self, post: Any, seenIds: set[str], records: List[dict]) -> None:
        """Collect unique media URLs from *post* and nested image/video posts."""
        if not isinstance(post, dict):
            return
        postId = str(post.get("id") or "")
        if postId:
            if postId in seenIds:
                return
            seenIds.add(postId)
            url = self._bestMediaUrl(post)
            if url:
                records.append(
                    {
                        "assetId": postId,
                        "url": url,
                        "mimeType": post.get("mimeType") or "",
                        "mediaType": post.get("mediaType") or "",
                    }
                )
        for key in ("images", "videos", "childPosts"):
            children = post.get(key) or []
            if isinstance(children, list):
                for child in children:
                    self._mediaFromPost(child, seenIds, records)
        original = post.get("originalPost")
        if isinstance(original, dict):
            self._mediaFromPost(original, seenIds, records)

    def _sessionCookiesLoad(self, sessionFile: Path) -> List[dict]:
        """Return grok.com cookies from a Playwright storage-state file."""
        try:
            loaded = json.loads(sessionFile.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeError(
                f"could not read grok session {sessionFile}: {error}"
            ) from error
        cookies = loaded.get("cookies") if isinstance(loaded, dict) else None
        if not isinstance(cookies, list):
            raise RuntimeError(f"grok session {sessionFile} has no cookies")
        grokCookies = []
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            domain = str(cookie.get("domain") or "")
            if "grok.com" in domain or "x.ai" in domain:
                grokCookies.append(cookie)
        if not grokCookies:
            raise RuntimeError(
                "session has no grok.com cookies; log in with Firefox and run "
                "--import-firefox-session --confirm"
            )
        return grokCookies

    def _sessionEnsure(self, sessionFile: Path) -> None:
        """Create a grok.com session file from Firefox if one is missing."""
        if sessionFile.exists():
            return
        if self.importFirefoxSession(sessionFile=sessionFile):
            return
        self._openFirefoxWindow("https://grok.com/imagine")
        print(
            "\nFirefox has been opened at grok.com/imagine.\n"
            "Please log in, then press Enter here...",
            flush=True,
        )
        input()
        if not self.importFirefoxSession(sessionFile=sessionFile):
            raise RuntimeError(
                "could not import grok.com cookies from Firefox; "
                "log in at grok.com then run --import-firefox-session --confirm"
            )

    def _extractMediaUrlsFromHtml(self, html: str) -> List[str]:
        """Extract likely media URLs from Grok saved-image HTML."""
        mediaUrls = set()
        for match in re.findall(r'https?://[^\s"\']+', html, re.IGNORECASE):
            parsed = urllib.parse.urlparse(match)
            ext = Path(parsed.path).suffix.lower()
            if ext in GROK_MEDIA_EXTENSIONS:
                mediaUrls.add(match)
        return sorted(mediaUrls)

    def _extractMediaUrlsFromPage(self, page) -> List[str]:
        """Extract the user's saved Imagine media URLs from a live Playwright page.

        Uses DOM querying to read ``src`` attributes directly from ``<img>`` and
        ``<video>``/``<source>`` elements rather than regex-scanning the full HTML.
        Results are filtered to the known Grok user-content CDN domains so that
        system UI icons, marketing images, and promotional videos embedded in the
        page template are excluded.
        """
        rawUrls: List[str] = page.eval_on_selector_all(
            "img[src], video[src], source[src]",
            "els => els.map(el => el.src)",
        )
        mediaUrls = set()
        for url in rawUrls:
            if not url:
                continue
            parsed = urllib.parse.urlparse(url)
            ext = Path(parsed.path).suffix.lower()
            if ext not in GROK_MEDIA_EXTENSIONS:
                continue
            hostname = parsed.hostname or ""
            if hostname in GROK_USER_CONTENT_DOMAINS:
                mediaUrls.add(url)
        return sorted(mediaUrls)

    def _collectPostUrls(self, page) -> List[str]:
        """Return all unique ``/imagine/post/{uuid}`` URLs found on the current page.

        Queries the live DOM for anchor elements whose ``href`` contains
        ``/imagine/post/`` and returns a deduplicated, sorted list of absolute
        URLs.  Empty strings and duplicates are removed automatically.  Called
        on the saved-gallery page so that the scraper can then visit each post
        page individually to capture full-resolution media (including videos
        that are not loaded as part of the thumbnail grid).
        """
        hrefs: List[str] = page.eval_on_selector_all(
            "a[href*='/imagine/post/']",
            "els => els.map(el => el.href)",
        )
        return sorted({h for h in hrefs if h})

    def _isGrokMediaResponse(self, url: str, contentType: str) -> bool:
        """Return True when a Playwright network response should be captured as user media.

        Only responses from the known Grok user-content CDN domains
        (:data:`GROK_USER_CONTENT_DOMAINS`) are considered user-generated media.
        Everything else — the app's own domain, third-party CDNs hosting profile
        pictures, analytics pixels, ad networks, etc. — is excluded.

        A response qualifies when BOTH of the following are true:

        * The hostname is in :data:`GROK_USER_CONTENT_DOMAINS`.
        * The URL path has a recognised media extension **or** the
          ``Content-Type`` header indicates an image or video.

        This is used by the ``page.on("response", ...)`` listener inside
        :meth:`scrapeGrokSavedMedia` and is extracted here so it can be tested
        without a live Playwright session.
        """
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname or ""
        if not hostname or hostname not in GROK_USER_CONTENT_DOMAINS:
            return False
        ext = Path(parsed.path).suffix.lower()
        return ext in GROK_MEDIA_EXTENSIONS or contentType.startswith(
            ("image/", "video/")
        )

    def _downloadMediaFiles(self, mediaUrls: List[str], playwrightContext=None) -> dict:
        """Download URLs into ~/Downloads/Grok and return download stats.

        Args:
            mediaUrls: List of media URLs to download.
            playwrightContext: An active Playwright ``BrowserContext``.  When
                provided, downloads are made via the authenticated browser
                session so that session cookies are included in each request,
                avoiding 403 responses from CDN URLs that require authentication.
                Falls back to ``urllib`` when *None*.
        """
        stats = {"downloaded": 0, "skipped": 0, "errors": 0}
        destDir = self.downloadDir
        if not self.dryRun:
            destDir.mkdir(parents=True, exist_ok=True)

        for mediaUrl in mediaUrls:
            parsed = urllib.parse.urlparse(mediaUrl)
            filename = (
                Path(parsed.path).name
                or f"grok_media_{stats['downloaded'] + stats['errors'] + 1}"
            )
            dest = destDir / filename

            if dest.exists():
                logger.value("grok media already exists, skipping", dest)
                stats["skipped"] += 1
                continue

            if self.dryRun:
                logger.action(f"would download grok media: {mediaUrl} -> {dest}")
                stats["downloaded"] += 1
                continue

            try:
                if playwrightContext is not None:
                    response = playwrightContext.request.get(
                        mediaUrl,
                        headers={"Referer": "https://grok.com/"},
                    )
                    if not response.ok:
                        raise RuntimeError(f"HTTP {response.status}")
                    dest.write_bytes(response.body())
                else:
                    with urllib.request.urlopen(mediaUrl, timeout=30) as response:
                        dest.write_bytes(response.read())
                logger.action(f"downloaded grok media: {dest}")
                stats["downloaded"] += 1
            except Exception as e:
                logger.error(f"failed downloading {mediaUrl}: {e}")
                stats["errors"] += 1

        return stats

    @staticmethod
    def _sanitizeStorageState(sessionFile: Path) -> None:
        """Fix cookie ``expires`` values in a Playwright storage-state JSON file.

        Playwright requires cookie ``expires`` to be either ``-1`` (session
        cookie / no expiry) or a **positive integer no greater than
        253402300799** (9999-12-31 23:59:59 UTC, Playwright's internal maximum).
        Values outside this range cause ``new_context()`` to raise:

        ``Error setting storage state: Cookie should have a valid expires``

        Specific fixups applied:

        * ``None``, ``0``, ``False``, or any other non-numeric value → ``-1``
        * Negative numbers other than ``-1`` → ``-1``
        * Floats → truncated to ``int`` (Playwright requires a plain JSON
          integer, not ``1742000000.0``).  A float that truncates to ``0`` or a
          negative value is converted to ``-1`` instead.
        * Integers greater than ``253402300799`` → clamped to ``253402300799``

        This helper reads the file, normalises every cookie's ``expires``
        in-place, and writes the file back.  It is called immediately after
        writing any session file and again just before loading it, so that
        sessions written by an older version of Playwright (which emitted
        ``0`` for session cookies) or by sites that set far-future expiry dates
        are also fixed transparently.

        Args:
            sessionFile: Path to the Playwright storage-state JSON file to fix.
        """
        try:
            data = json.loads(sessionFile.read_text(encoding="utf-8"))
        except Exception:
            return  # file missing or unparseable — caller will handle the error
        changed = False
        for cookie in data.get("cookies", []):
            raw = cookie.get("expires")
            # ---- booleans: True/False serialize to JSON true/false, not numbers
            if isinstance(raw, bool):
                cookie["expires"] = -1
                changed = True
            # ---- None, 0, or any negative except -1 → session cookie sentinel
            elif (
                raw is None
                or raw == 0
                or (isinstance(raw, (int, float)) and raw < 0 and raw != -1)
            ):
                cookie["expires"] = -1
                changed = True
            elif isinstance(raw, float):
                # Convert any float (whole-number or fractional) to int.
                # json.dumps serialises 1742000000.0 as "1742000000.0" which
                # Playwright rejects — it requires a plain JSON integer.
                # A float that truncates to 0 or a negative is treated as a
                # session cookie.  A float beyond the max is clamped.
                int_val = int(raw)
                if int_val == 0 or int_val < -1:
                    cookie["expires"] = -1
                elif int_val > _PLAYWRIGHT_MAX_COOKIE_EXPIRES:
                    cookie["expires"] = _PLAYWRIGHT_MAX_COOKIE_EXPIRES
                else:
                    cookie["expires"] = int_val
                changed = True
            elif isinstance(raw, int) and raw > _PLAYWRIGHT_MAX_COOKIE_EXPIRES:
                # Timestamps beyond year 9999 are rejected by Playwright's
                # rewriteCookies() validation.  Clamp to the allowed maximum.
                cookie["expires"] = _PLAYWRIGHT_MAX_COOKIE_EXPIRES
                changed = True
        if changed:
            sessionFile.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _openFirefoxWindow(self, url: str) -> None:
        """Open the user's system Firefox browser at *url*.

        Uses platform-appropriate commands:

        * Linux: ``firefox`` or ``firefox-esr`` (whichever is found on PATH)
        * macOS: ``open -a Firefox``
        * Windows: ``cmd /c start <url>``

        Only ``https://`` and ``http://`` URLs are accepted; any other value
        raises ``ValueError`` to prevent command injection.

        If Firefox cannot be located on the system, a warning is logged and
        the user is expected to open Firefox manually and navigate to *url*.

        Args:
            url: The URL to open in Firefox.  Must begin with ``https://`` or
                 ``http://``.

        Raises:
            ValueError: If *url* does not start with ``https://`` or
                        ``http://``.
        """
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"refusing to open non-http URL: {url!r}")

        system = platform.system()
        if system == "Windows":
            # Use cmd /c start to avoid shell=True with a plain string.
            subprocess.Popen(["cmd", "/c", "start", "", url])
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "Firefox", url])
        else:
            for candidate in ("firefox", "firefox-esr", "firefox-bin"):
                firefox = shutil.which(candidate)
                if firefox:
                    subprocess.Popen([firefox, "--new-window", url])
                    return
            logger.warning(
                f"Firefox not found on PATH; please open Firefox manually and navigate to {url}"
            )

    @staticmethod
    def _firefoxLaunch(playwright) -> object:
        """Launch Playwright Firefox headless, raising a clear error if not installed.

        Playwright's default error for a missing browser binary contains a raw
        file path and a generic "please run playwright install" hint buried in
        an ASCII box — easy to miss.  This wrapper intercepts that specific
        error and re-raises it as a plain :class:`RuntimeError` with an
        actionable message so users see exactly what to run.

        All other exceptions are re-raised unchanged.

        Args:
            playwright: The Playwright instance from ``sync_playwright()``.

        Returns:
            A Playwright ``Browser`` instance.

        Raises:
            RuntimeError: When the Firefox browser binary has not been
                          installed via ``playwright install firefox``.
        """
        try:
            return playwright.firefox.launch(headless=True)
        except Exception as e:
            msg = str(e)
            msg_lower = msg.lower()
            if (
                "executable" in msg_lower
                and ("exist" in msg_lower or "found" in msg_lower)
            ) or "playwright install" in msg_lower:
                raise RuntimeError(
                    "Playwright Firefox browser is not installed.\n"
                    "Run: playwright install firefox"
                ) from e
            raise

    @staticmethod
    def _firefoxBaseCandidates(system: str) -> List[Path]:
        """Return candidate Firefox base directories for the given OS, in priority order.

        On Linux, multiple installation methods are covered:

        * Traditional package-manager install (``~/.mozilla/firefox``)
        * Ubuntu/Debian Snap package (``~/snap/firefox/common/.mozilla/firefox``
          and ``~/snap/firefox/current/.mozilla/firefox``)
        * Flatpak (``~/.var/app/org.mozilla.firefox/.mozilla/firefox``)
        """
        home = Path.home()
        if system == "Windows":
            appdata = os.environ.get("APPDATA")
            if not appdata:
                return []
            return [Path(appdata) / "Mozilla" / "Firefox"]
        if system == "Darwin":
            return [home / "Library" / "Application Support" / "Firefox"]
        # Linux — try all common install locations
        return [
            home / ".mozilla" / "firefox",
            home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
            home / "snap" / "firefox" / "current" / ".mozilla" / "firefox",
            home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
        ]

    @staticmethod
    def _findProfileInBase(
        firefoxBase: Path, requireCookies: bool = False
    ) -> Optional[Path]:
        """Return the best profile directory found under *firefoxBase*.

        Reads ``profiles.ini`` and returns the profile marked ``Default=1``,
        or the first ``Profile`` section if none is flagged.  When
        *requireCookies* is ``True`` the profile is only returned if it
        contains ``cookies.sqlite``.

        Args:
            firefoxBase: Firefox configuration base directory (containing
                         ``profiles.ini``).
            requireCookies: When ``True``, only return a profile that has a
                            ``cookies.sqlite`` file.

        Returns:
            Path to the profile directory, or ``None``.
        """
        profilesIni = firefoxBase / "profiles.ini"
        if not profilesIni.exists():
            return None

        config = configparser.ConfigParser()
        config.read(str(profilesIni))

        def _resolve(section: str) -> Optional[Path]:
            path = config.get(section, "Path", fallback=None)
            if not path:
                return None
            if config.get(section, "IsRelative", fallback="0") == "1":
                return firefoxBase / path
            return Path(path)

        def _accept(p: Optional[Path]) -> bool:
            if p is None:
                return False
            if requireCookies:
                return (p / "cookies.sqlite").exists()
            return True

        # Prefer the profile explicitly marked as the default.
        for section in config.sections():
            if config.get(section, "Default", fallback="0") == "1":
                resolved = _resolve(section)
                if _accept(resolved):
                    return resolved

        # Fall back to the first Profile section.
        for section in config.sections():
            if section.startswith("Profile"):
                resolved = _resolve(section)
                if _accept(resolved):
                    return resolved

        return None

    def _findFirefoxProfile(
        self, _firefoxBase: Optional[Path] = None
    ) -> Optional[Path]:
        """Locate the best Firefox profile directory on the current OS.

        When *_firefoxBase* is provided (unit-test override), that single base
        directory is searched and its profile returned.

        Otherwise, all platform-appropriate Firefox install locations are
        searched (see :meth:`_firefoxBaseCandidates`).  Within each candidate
        base the search runs in two passes:

        1. **With cookies** — prefer any profile that already has
           ``cookies.sqlite`` (meaning the user has actually browsed with it).
           The candidate with the most recently modified ``cookies.sqlite``
           wins, so if both a traditional and Snap install are present the one
           the user actively uses is selected.
        2. **Without cookies** — fall back to the default/first profile even if
           ``cookies.sqlite`` is absent, so the existing warning message in
           :meth:`importFirefoxSession` is still shown.

        Args:
            _firefoxBase: Override the candidate list with a single base
                          directory.  Intended for unit tests only.

        Returns:
            Path to the best profile directory, or ``None`` if no Firefox
            install is found.
        """
        if _firefoxBase is not None:
            # Unit-test fast path: single base, no cookies preference.
            return self._findProfileInBase(_firefoxBase)

        candidates = self._firefoxBaseCandidates(platform.system())

        # Pass 1: prefer profile that has cookies.sqlite, picking the most
        # recently modified one so the actively-used install wins.
        best: Optional[Path] = None
        bestMtime: float = -1.0
        for base in candidates:
            profile = self._findProfileInBase(base, requireCookies=True)
            if profile is not None:
                mtime = (profile / "cookies.sqlite").stat().st_mtime
                if mtime > bestMtime:
                    bestMtime = mtime
                    best = profile
        if best is not None:
            return best

        # Pass 2: no profile with cookies found — return the default/first
        # profile from the first candidate that has profiles.ini.
        for base in candidates:
            profile = self._findProfileInBase(base)
            if profile is not None:
                return profile

        return None

    def importFirefoxSession(
        self,
        sessionFile: Path = GROK_SESSION_FILE,
        profilePath: Optional[Path] = None,
    ) -> bool:
        """Import Grok cookies from the user's Firefox profile.

        Reads the cookies for ``grok.com`` and ``x.ai`` from Firefox's
        ``cookies.sqlite`` database and writes them as a Playwright
        ``storage_state`` JSON file at *sessionFile*.

        This lets you authenticate the scraper by simply logging into
        ``grok.com`` in your regular Firefox browser — no Playwright login
        flow (and no Cloudflare Turnstile challenge) is needed.

        The Firefox ``cookies.sqlite`` database is copied to a temporary file
        before being read so that the operation is safe even when Firefox is
        currently open.

        Args:
            sessionFile: Destination path for the Playwright storage-state JSON.
            profilePath: Firefox profile directory.  Auto-detected from the
                         default Firefox profile when omitted.

        Returns:
            True if cookies were found and written successfully; False otherwise.
        """
        if profilePath is None:
            profilePath = self._findFirefoxProfile()
        if profilePath is None:
            logger.warning(
                "could not locate a Firefox profile; skipping Firefox session import"
            )
            return False

        cookiesDb = profilePath / "cookies.sqlite"
        if not cookiesDb.exists():
            logger.warning(f"Firefox cookies database not found at {cookiesDb}")
            return False

        # Copy to a temp file to avoid "database is locked" errors when Firefox
        # is currently open and holding a write lock on cookies.sqlite.
        tmpPath = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
                tmpPath = Path(tmp.name)
            shutil.copy2(str(cookiesDb), str(tmpPath))

            conn = sqlite3.connect(str(tmpPath))
            cursor = conn.cursor()
            # Match exact host 'grok.com' / 'x.ai' plus any subdomain
            # (e.g. '.grok.com', 'accounts.x.ai').  The LIKE patterns use a
            # leading dot/% pair so they cannot match unrelated suffixes such
            # as 'fakegrok.com'.
            cursor.execute(
                """
                SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
                FROM moz_cookies
                WHERE host = 'grok.com'  OR host LIKE '%.grok.com'
                   OR host = 'x.ai'      OR host LIKE '%.x.ai'
                """
            )
            rows = cursor.fetchall()
            conn.close()
        finally:
            if tmpPath is not None:
                tmpPath.unlink(missing_ok=True)

        if not rows:
            logger.warning(
                "no Grok/X.ai cookies found in Firefox profile; "
                "please log into grok.com in Firefox first"
            )
            return False

        # Firefox sameSite integers → Playwright string values
        _SAMESITE = {0: "None", 1: "Lax", 2: "Strict"}
        cookies = [
            {
                "name": name,
                "value": value,
                "domain": host,
                "path": path,
                # Firefox stores session cookies (no expiry) with expiry=0.
                # Playwright requires -1 for "no expiry"; 0 is rejected.
                # SQLite may return INTEGER columns as Python floats when stored
                # as REAL affinity — always cast to int so JSON never writes
                # "1742000000.0", which Playwright also rejects.
                # Some sites set extremely far-future expiry timestamps.
                # Playwright rejects any expires > 253402300799 (year 9999).
                "expires": (
                    min(int(expiry), _PLAYWRIGHT_MAX_COOKIE_EXPIRES)
                    if expiry > 0
                    else -1
                ),
                "httpOnly": bool(isHttpOnly),
                "secure": bool(isSecure),
                "sameSite": _SAMESITE.get(sameSite, "None"),
            }
            for name, value, host, path, expiry, isSecure, isHttpOnly, sameSite in rows
        ]

        storageState = {"cookies": cookies, "origins": []}
        sessionFile.parent.mkdir(parents=True, exist_ok=True)
        sessionFile.write_text(json.dumps(storageState, indent=2))
        sessionFile.chmod(0o600)
        self._sanitizeStorageState(sessionFile)
        logger.value(
            f"imported {len(cookies)} cookies from Firefox to", str(sessionFile)
        )
        return True

    def resetGrokConfig(
        self,
        sessionFile: Path = GROK_SESSION_FILE,
        credentialsFile: Path = GROK_CREDENTIALS_FILE,
    ) -> dict:
        """Delete saved Grok session and credentials config files.

        Removes *sessionFile* and *credentialsFile* if they exist so that the
        next ``--grok`` run will prompt for a fresh manual login.

        Args:
            sessionFile: Path to the Playwright storage-state file.
            credentialsFile: Path to the JSON credentials file.

        Returns:
            Dict with keys ``deleted`` (list of deleted paths) and
            ``notFound`` (list of paths that did not exist).
        """
        deleted = []
        notFound = []
        for path in (sessionFile, credentialsFile):
            if path.exists():
                if not self.dryRun:
                    path.unlink()
                logger.action(f"deleted Grok config file: {path}")
                deleted.append(str(path))
            else:
                logger.info(f"Grok config file not found (skipping): {path}")
                notFound.append(str(path))
        return {"deleted": deleted, "notFound": notFound}

    def scrapeGrokSavedMedia(
        self,
        sessionFile: Path = GROK_SESSION_FILE,
        credentialsFile: Path = GROK_CREDENTIALS_FILE,
    ) -> dict:
        """Download this account's generated Imagine media.

        Kept as the historical ``--grok`` entry point. It no longer scrapes the
        Imagine landing page; it lists this login's Imagine workspace assets.
        """
        del credentialsFile
        stats = self.downloadGeneratedMedia(sessionFile=sessionFile)
        return {
            "postsFound": stats.get("assetsFound", 0),
            "urlsFound": stats.get("assetsFound", 0),
            "downloaded": stats.get("downloaded", 0),
            "skipped": stats.get("skipped", 0),
            "errors": stats.get("errors", 0),
            "assetsFound": stats.get("assetsFound", 0),
        }
