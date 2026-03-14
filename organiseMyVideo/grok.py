"""Grok scraper: authentication, Firefox session import, and media download."""

import os
import re
import json
import shutil
import getpass
import platform
import sqlite3
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
    _PLAYWRIGHT_BROWSER_ARGS,
    _PLAYWRIGHT_USER_AGENT,
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

    def _loadOrPromptGrokCredentials(
        self, credentialsFile: Path = GROK_CREDENTIALS_FILE
    ) -> tuple:
        """
        Load Grok credentials from a JSON file, prompting if not found.

        If the file exists and contains both ``username`` and ``password``,
        those values are returned directly.  Otherwise the user is prompted
        interactively (password entry is hidden) and the credentials are saved
        to the file for future use.

        Args:
            credentialsFile: Path to the JSON credentials file.

        Returns:
            Tuple of (username, password).
        """
        if credentialsFile.exists():
            try:
                data = json.loads(credentialsFile.read_text())
                username = data.get("username", "")
                password = data.get("password", "")
                if username and password:
                    logger.value("loaded grok credentials from", str(credentialsFile))
                    return username, password
            except Exception as e:
                logger.error(f"failed to load credentials from {credentialsFile}: {e}")

        logger.info("grok credentials not found - please enter your credentials")
        username = input("Grok username (email): ").strip()
        password = getpass.getpass("Grok password: ")

        if not username or not password:
            raise RuntimeError("username and password are required for --grok")

        credentialsFile.parent.mkdir(parents=True, exist_ok=True)
        credentialsFile.write_text(
            json.dumps({"username": username, "password": password}, indent=2)
        )
        credentialsFile.chmod(0o600)
        logger.value("saved grok credentials to", str(credentialsFile))
        return username, password

    def _autofillLoginPage(self, page, username: str) -> None:
        """Pre-fill the email field on the X.ai sign-in form.

        Only the email address is filled automatically.  Clicking Next,
        entering the password, and clicking Login are all intentionally left
        for the user so that Cloudflare Turnstile's human-verification
        challenge is triggered by real human navigation rather than automated
        page transitions — automating those clicks causes Turnstile error
        600010 (unsupported browser / bot detected).

        Silently degrades to a warning log if the email field is not found
        within the timeout so the user can still log in manually.

        Args:
            page: Playwright Page instance on the X.ai sign-in page.
            username: Email address to pre-fill.
        """
        EMAIL_SELECTOR = "input[type='email'], input[autocomplete='username'], input[name='email']"
        SELECTOR_TIMEOUT = 10_000
        try:
            page.wait_for_selector(EMAIL_SELECTOR, timeout=SELECTOR_TIMEOUT)
            page.fill(EMAIL_SELECTOR, username)
            logger.info("email pre-filled — please click Next, enter your password, and log in")
        except Exception as e:
            # Broad catch is intentional: Playwright raises various exception
            # types depending on the failure (timeout, missing element, navigation
            # error).  The helper is best-effort; any failure falls back to fully
            # manual entry so the user is never blocked.
            logger.warning(f"auto-fill of login form failed ({e}); please log in manually")

    def _awaitManualLoginInput(self, page) -> None:
        """Wait for the user to press Enter after completing manual login.

        If the browser window is closed before the user presses Enter,
        raises ``SystemExit(1)`` so the process exits cleanly instead of
        crashing with a Playwright error on the next page operation.

        Args:
            page: Playwright Page instance shown to the user.
        """
        input()
        if page.is_closed():
            logger.warning("browser window closed before login completed; aborting")
            raise SystemExit(1)

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
                "expires": expiry if expiry > 0 else -1,
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
        """Log into Grok and scrape saved Imagine media, downloading to ~/Downloads/Grok.

        Authentication uses Playwright ``storage_state`` (cookies + localStorage)
        persisted at *sessionFile* (default :data:`GROK_SESSION_FILE`).

        * **If the session file exists** the browser starts already authenticated
          and no username/password interaction is needed.

        * **If the session file is absent** a visible browser window opens, saved
          credentials from *credentialsFile* are pre-filled into the sign-in form,
          and the user just needs to complete the login (e.g. click Login and
          solve any Cloudflare challenge).  The resulting session is saved so
          subsequent runs are instant.

        * **If the saved session has expired** (detected when Grok redirects the
          browser away from ``/imagine/saved`` rather than loading the page), the
          stale session file is deleted automatically, credentials are pre-filled,
          and the user is prompted to log in again via a visible browser window.

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
                "pip install playwright && playwright install chromium"
            )

        logger.doing("starting Grok scrape for saved Imagine media")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=_PLAYWRIGHT_BROWSER_ARGS)

            # ------------------------------------------------------------------
            # Authentication — prefer a saved session so that the full login
            # flow (which may involve OAuth redirects, CAPTCHA, or 2FA) is only
            # required once.
            # ------------------------------------------------------------------
            if sessionFile.exists():
                try:
                    logger.info("loading saved Grok session")
                    context = browser.new_context(
                        storage_state=str(sessionFile),
                        user_agent=_PLAYWRIGHT_USER_AGENT,
                    )
                    context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                except Exception as e:
                    logger.warning(f"saved session could not be loaded ({e}); falling back to fresh login")
                    sessionFile.unlink(missing_ok=True)
                    context = None
            else:
                context = None

            if context is None:
                # No saved session — try importing cookies from Firefox first.
                # This avoids the Cloudflare Turnstile challenge that fires
                # when Playwright drives the login form directly.
                if self.importFirefoxSession(sessionFile=sessionFile):
                    try:
                        context = browser.new_context(
                            storage_state=str(sessionFile),
                            user_agent=_PLAYWRIGHT_USER_AGENT,
                        )
                        context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                    except Exception as e:
                        logger.warning(
                            f"imported Firefox session could not be loaded ({e}); "
                            "falling back to manual login"
                        )
                        sessionFile.unlink(missing_ok=True)
                        context = None

            if context is None:
                # No valid session at all — relaunch as non-headless and ask the
                # user to log in manually (Cloudflare challenge requires a human).
                username, password = self._loadOrPromptGrokCredentials(
                    credentialsFile=credentialsFile
                )
                browser.close()
                browser = playwright.chromium.launch(headless=False, args=_PLAYWRIGHT_BROWSER_ARGS)
                context = browser.new_context(user_agent=_PLAYWRIGHT_USER_AGENT)
                context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                page = context.new_page()
                page.goto("https://grok.com", wait_until="domcontentloaded")
                self._autofillLoginPage(page, username)
                print(
                    "\nA browser window has opened and your email has been pre-filled.\n"
                    "Please click Next, enter your password, complete any verification,\n"
                    "then press Enter here to continue...",
                    flush=True,
                )
                self._awaitManualLoginInput(page)

                # Verify login completed before saving the session.
                page.goto(_GROK_SAVED_URL, wait_until="domcontentloaded")
                page.wait_for_timeout(1000)
                if urllib.parse.urlparse(page.url).path != "/imagine/saved":
                    logger.warning(
                        f"login did not complete — still redirected to {page.url!r}; "
                        "please restart --grok and complete the login before pressing Enter"
                    )
                    raise SystemExit(1)

                # Persist session so the login form is never needed again.
                sessionFile.parent.mkdir(parents=True, exist_ok=True)
                context.storage_state(path=str(sessionFile))
                if sessionFile.exists():
                    sessionFile.chmod(0o600)
                logger.value("saved Grok session to", str(sessionFile))
            else:
                page = context.new_page()

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
            _navigateToSaved(page)

            # Detect session expiry: an expired (or invalid) session causes
            # Grok to redirect the browser to the login page instead of loading
            # /imagine/saved.  When that happens, wipe the stale session file,
            # try importing a fresh Firefox session, and fall back to manual
            # Playwright login only if the Firefox session is also unavailable.
            if urllib.parse.urlparse(page.url).path != "/imagine/saved":
                logger.warning(
                    f"session appears expired (redirected to {page.url!r}); "
                    "deleting saved session and switching to manual login"
                )
                context.close()
                browser.close()
                sessionFile.unlink(missing_ok=True)

                _ffSessionOk = False
                if self.importFirefoxSession(sessionFile=sessionFile):
                    try:
                        browser = playwright.chromium.launch(headless=True, args=_PLAYWRIGHT_BROWSER_ARGS)
                        context = browser.new_context(
                            storage_state=str(sessionFile),
                            user_agent=_PLAYWRIGHT_USER_AGENT,
                        )
                        context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                        page = context.new_page()
                        _navigateToSaved(page)
                        if urllib.parse.urlparse(page.url).path == "/imagine/saved":
                            _ffSessionOk = True
                        else:
                            context.close()
                            browser.close()
                            sessionFile.unlink(missing_ok=True)
                    except Exception as e:
                        logger.warning(
                            f"imported Firefox session could not be loaded ({e}); "
                            "falling back to manual login"
                        )
                        try:
                            browser.close()
                        except Exception:
                            pass

                if not _ffSessionOk:
                    username, password = self._loadOrPromptGrokCredentials(
                        credentialsFile=credentialsFile
                    )
                    browser = playwright.chromium.launch(headless=False, args=_PLAYWRIGHT_BROWSER_ARGS)
                    context = browser.new_context(user_agent=_PLAYWRIGHT_USER_AGENT)
                    context.add_init_script(_PLAYWRIGHT_INIT_SCRIPT)
                    page = context.new_page()
                    page.goto("https://grok.com", wait_until="domcontentloaded")
                    self._autofillLoginPage(page, username)
                    print(
                        "\nA browser window has opened.\n"
                        "Your previous Grok session has expired and your email has been pre-filled.\n"
                        "Please click Next, enter your password, complete any verification,\n"
                        "then press Enter here to continue...",
                        flush=True,
                    )
                    self._awaitManualLoginInput(page)
                    _navigateToSaved(page)
                    if urllib.parse.urlparse(page.url).path != "/imagine/saved":
                        logger.warning(
                            f"login did not complete — still redirected to {page.url!r}; "
                            "please restart --grok and complete the login before pressing Enter"
                        )
                        raise SystemExit(1)
                    sessionFile.parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(sessionFile))
                    if sessionFile.exists():
                        sessionFile.chmod(0o600)
                    logger.value("saved Grok session to", str(sessionFile))

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
