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
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

# Playwright is an optional dependency used only by --grok.  We import it at
# module level so tests can patch ``organiseMyVideo.grok.sync_playwright``.
try:
    from playwright.sync_api import sync_playwright  # type: ignore
except ImportError:
    sync_playwright = None  # type: ignore

from .constants import (
    GROK_MEDIA_EXTENSIONS,
    GROK_USER_CONTENT_DOMAINS,
    GROK_CREDENTIALS_FILE,
    GROK_SESSION_FILE,
    _GROK_SAVED_URL,
    _PLAYWRIGHT_INIT_SCRIPT,
)

logger = getLogger("organiseMyVideo")


class GrokMixin:
    """Methods for authenticating with Grok and scraping saved Imagine media."""

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
        return ext in GROK_MEDIA_EXTENSIONS or contentType.startswith(("image/", "video/"))

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
        destDir = Path.home() / "Downloads" / "Grok"
        destDir.mkdir(parents=True, exist_ok=True)

        for mediaUrl in mediaUrls:
            parsed = urllib.parse.urlparse(mediaUrl)
            filename = Path(parsed.path).name or f"grok_media_{stats['downloaded'] + stats['errors'] + 1}"
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
        cookie / no expiry) or a **positive integer** (Unix timestamp in
        seconds).  Values that are invalid — ``0``, ``null``, other negative
        numbers, or non-integer floats — cause ``new_context()`` to raise:

        ``Error setting storage state: Cookie should have a valid expires``

        This helper reads the file, normalises every cookie's ``expires``
        in-place, and writes the file back.  It is called immediately after
        writing any session file and again just before loading it, so that
        sessions written by an older version of Playwright (which emitted
        ``0`` for session cookies) are also fixed transparently.

        Args:
            sessionFile: Path to the Playwright storage-state JSON file to fix.
        """
        try:
            data = json.loads(sessionFile.read_text())
        except Exception:
            return  # file missing or unparseable — caller will handle the error
        changed = False
        for cookie in data.get("cookies", []):
            raw = cookie.get("expires")
            if raw is None or raw == 0 or (isinstance(raw, (int, float)) and raw < 0 and raw != -1):
                cookie["expires"] = -1
                changed = True
            elif isinstance(raw, float):
                # Convert any float (whole-number or fractional) to int.
                # json.dumps serialises 1742000000.0 as "1742000000.0" which
                # Playwright rejects — it requires a plain JSON integer.
                cookie["expires"] = int(raw)
                changed = True
        if changed:
            sessionFile.write_text(json.dumps(data, indent=2))

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
                ("executable" in msg_lower and ("exist" in msg_lower or "found" in msg_lower))
                or "playwright install" in msg_lower
            ):
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

    def _findFirefoxProfile(self, _firefoxBase: Optional[Path] = None) -> Optional[Path]:
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
                "expires": int(expiry) if expiry > 0 else -1,
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
        logger.value(f"imported {len(cookies)} cookies from Firefox to", str(sessionFile))
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
        """Scrape saved Imagine media from Grok, downloading to ~/Downloads/Grok.

        Authentication uses Playwright Firefox ``storage_state`` (cookies +
        localStorage) persisted at *sessionFile*.  When no valid session is
        available the user's system Firefox browser is opened at
        ``grok.com/imagine/saved`` so the user can log in without being blocked
        by Cloudflare verification; cookies are then imported from the Firefox
        profile and used to run the headless scrape.

        *credentialsFile* is retained for API compatibility but is no longer
        used in the authentication flow — login is now always handled via the
        user's system Firefox browser.

        Authentication priority:

        1. Load saved session from *sessionFile*.
        2. Import cookies from the user's Firefox profile.
        3. Open system Firefox at ``grok.com/imagine/saved`` and wait for the
           user to log in, then import the resulting cookies.

        After authentication the scrape runs in two phases:

        1. **Gallery phase** — navigates to ``grok.com/imagine/saved`` and
           scrolls to the bottom so that all post thumbnails are rendered.
           Collects every ``/imagine/post/{uuid}`` link found in the DOM.

        2. **Post phase** — visits each post page in turn and collects media
           via two complementary strategies:

           a. Network-response interception (fires for any resource the browser
              actually fetches from :data:`GROK_USER_CONTENT_DOMAINS`).

           b. DOM query (:meth:`_extractMediaUrlsFromPage`) reads ``<video
              src>`` and ``<source src>`` attributes directly — essential
              because video elements only fetch their media when they play, so
              the response listener alone misses them.

        All captured media URLs are then downloaded to ``~/Downloads/Grok``.
        """
        if sync_playwright is None:
            raise RuntimeError(
                "Playwright is required for --grok: "
                "pip install playwright && playwright install firefox"
            )

        logger.doing("starting Grok scrape for saved Imagine media")
        with sync_playwright() as playwright:
            browser = None
            context = None

            # ------------------------------------------------------------------
            # Authentication — prefer a saved session so that the full login
            # flow is only required once.
            # ------------------------------------------------------------------
            if sessionFile.exists():
                try:
                    logger.info("loading saved Grok session")
                    self._sanitizeStorageState(sessionFile)
                    browser = self._firefoxLaunch(playwright)
                    context = browser.new_context(storage_state=str(sessionFile))
                    context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                except RuntimeError:
                    raise  # Firefox not installed — propagate immediately
                except Exception as e:
                    logger.warning(
                        f"saved session could not be loaded ({e}); "
                        "falling back to Firefox import"
                    )
                    if browser:
                        browser.close()
                    sessionFile.unlink(missing_ok=True)
                    context = None
                    browser = None

            if context is None:
                # No saved session — try importing cookies from the user's
                # Firefox profile.  This avoids any Cloudflare challenge because
                # the cookies were issued to a real Firefox browser.
                if self.importFirefoxSession(sessionFile=sessionFile):
                    try:
                        self._sanitizeStorageState(sessionFile)
                        browser = self._firefoxLaunch(playwright)
                        context = browser.new_context(storage_state=str(sessionFile))
                        context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                    except RuntimeError:
                        raise  # Firefox not installed — propagate immediately
                    except Exception as e:
                        logger.warning(
                            f"imported Firefox session could not be loaded ({e}); "
                            "falling back to manual Firefox login"
                        )
                        if browser:
                            browser.close()
                        sessionFile.unlink(missing_ok=True)
                        context = None
                        browser = None

            if context is None:
                # No valid session at all — open the user's system Firefox so
                # they can log in without Cloudflare blocking the browser.
                self._openFirefoxWindow(_GROK_SAVED_URL)
                print(
                    "\nFirefox has been opened at grok.com/imagine/saved.\n"
                    "Please log in and navigate to the saved Imagine page.\n"
                    "Press Enter here when you are logged in and on that page...",
                    flush=True,
                )
                input()

                if not self.importFirefoxSession(sessionFile=sessionFile):
                    logger.warning(
                        "could not import Grok cookies from Firefox; "
                        "make sure you are logged in to grok.com in Firefox first"
                    )
                    raise SystemExit(1)

                self._sanitizeStorageState(sessionFile)
                browser = self._firefoxLaunch(playwright)
                context = browser.new_context(storage_state=str(sessionFile))
                context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)

            capturedUrls: set = set()

            def _onResponse(response) -> None:
                contentType = response.headers.get("content-type", "")
                if self._isGrokMediaResponse(response.url, contentType):
                    capturedUrls.add(response.url)

            def _navigateToSaved(pg) -> None:
                """Attach the response listener and navigate to /imagine/saved."""
                pg.on("response", _onResponse)
                pg.goto(_GROK_SAVED_URL, wait_until="domcontentloaded")
                pg.wait_for_timeout(2000)

            # ------------------------------------------------------------------
            # Phase 1: Gallery — scroll /imagine/saved to render all post cards
            # and collect their individual post-page links.
            #
            # Stall detection tracks the number of post links visible in the
            # DOM (not capturedUrls) because gallery thumbnails may not come
            # from GROK_USER_CONTENT_DOMAINS, so capturedUrls could stay at
            # zero and cause the scroll to abort after just two passes.
            # ------------------------------------------------------------------
            page = context.new_page()
            _navigateToSaved(page)

            # Detect session expiry: an expired (or invalid) session causes
            # Grok to redirect the browser to the login page instead of loading
            # /imagine/saved.  Open system Firefox for re-login and import fresh
            # cookies.
            if urllib.parse.urlparse(page.url).path != "/imagine/saved":
                logger.warning(
                    f"session appears expired (redirected to {page.url!r}); "
                    "opening Firefox for re-login"
                )
                context.close()
                browser.close()
                sessionFile.unlink(missing_ok=True)

                self._openFirefoxWindow(_GROK_SAVED_URL)
                print(
                    "\nYour Grok session has expired. Firefox has been opened.\n"
                    "Please log in and navigate to grok.com/imagine/saved.\n"
                    "Press Enter here when you are ready...",
                    flush=True,
                )
                input()

                if not self.importFirefoxSession(sessionFile=sessionFile):
                    logger.warning(
                        "could not import Grok cookies from Firefox after re-login"
                    )
                    raise SystemExit(1)

                self._sanitizeStorageState(sessionFile)
                browser = self._firefoxLaunch(playwright)
                context = browser.new_context(storage_state=str(sessionFile))
                context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                page = context.new_page()
                _navigateToSaved(page)

                if urllib.parse.urlparse(page.url).path != "/imagine/saved":
                    logger.warning(
                        f"still not authenticated after re-login "
                        f"(redirected to {page.url!r}); aborting"
                    )
                    raise SystemExit(1)

                # Persist the refreshed session.
                sessionFile.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(sessionFile))
                if sessionFile.exists():
                    sessionFile.chmod(0o600)
                    self._sanitizeStorageState(sessionFile)
                logger.value("saved refreshed Grok session to", str(sessionFile))

            previousLinkCount = 0
            stallCount = 0
            for _ in range(20):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(900)
                currentLinkCount = len(self._collectPostUrls(page))
                if currentLinkCount == previousLinkCount:
                    stallCount += 1
                    if stallCount >= 2:
                        break
                else:
                    stallCount = 0
                previousLinkCount = currentLinkCount

            postUrls = self._collectPostUrls(page)
            logger.value("found Grok post pages", len(postUrls))

            # ------------------------------------------------------------------
            # Phase 2: Post pages — visit each post and collect media via two
            # complementary strategies:
            #
            # a) Network-response listener (_onResponse, already active) fires
            #    for any resource that the browser fetches from
            #    GROK_USER_CONTENT_DOMAINS while the page loads.
            #
            # b) DOM query (_extractMediaUrlsFromPage) reads <video src> and
            #    <source src> attributes directly.  This is essential because
            #    <video> elements do not start fetching their media until they
            #    play, so the response listener alone misses them.
            #
            # We wait for "networkidle" (not just "domcontentloaded") so that
            # the React app has time to finish its API call and render the
            # video elements into the DOM before we query them.
            # ------------------------------------------------------------------
            for i, postUrl in enumerate(postUrls, 1):
                logger.doing(f"scraping post {i}/{len(postUrls)}: {postUrl}")
                page.goto(postUrl, wait_until="networkidle")
                page.wait_for_timeout(1000)
                for url in self._extractMediaUrlsFromPage(page):
                    capturedUrls.add(url)

            page.remove_listener("response", _onResponse)
            mediaUrls = sorted(capturedUrls)
            logger.value("found Grok media URLs", len(mediaUrls))

            # Refresh the session on disk so it stays current.
            context.storage_state(path=str(sessionFile))
            if sessionFile.exists():
                self._sanitizeStorageState(sessionFile)

            if not postUrls:
                logger.warning(
                    "no posts found — check that you are logged in; "
                    f"if the session has expired, delete {sessionFile} and re-run"
                )

            downloadStats = self._downloadMediaFiles(mediaUrls, playwrightContext=context)
            browser.close()

        logger.done("Grok scrape complete")
        return {
            "postsFound": len(postUrls),
            "urlsFound": len(mediaUrls),
            **downloadStats,
        }
