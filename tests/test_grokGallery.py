"""Tests for grok.com saved-gallery download."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from organiseMyVideo.grokGallery import GrokGallery, _PLAYWRIGHT_MAX_COOKIE_EXPIRES


@pytest.fixture()
def gallery() -> GrokGallery:
    return GrokGallery(dryRun=True)


@pytest.fixture()
def confirmedGallery() -> GrokGallery:
    return GrokGallery(dryRun=False)


def testExtractMediaUrlsFromHtmlFindsSupportedExtensions(gallery: GrokGallery):
    html = (
        '<img src="https://example.com/image01.png">'
        '<video src="https://example.com/clip01.mp4"></video>'
        '<a href="https://example.com/readme.txt">ignore</a>'
    )
    urls = gallery._extractMediaUrlsFromHtml(html)
    assert urls == ["https://example.com/clip01.mp4", "https://example.com/image01.png"]


def testExtractMediaUrlsFromPageFiltersToUserContentDomains(gallery: GrokGallery):
    """Only URLs from known Grok user-content CDN domains are returned."""
    userImage = "https://imagine-public.x.ai/imagine-public/images/abc123.png"
    userImageFromImagesPublic = (
        "https://images-public.x.ai/xai-images-public/mj/images/def456.jpg"
    )
    systemImage = "https://x.ai/images/news/grok-4-1.webp"
    promoVideo = "https://data.x.ai/grok-4-fast-side-by-side.mp4"
    nonMedia = "https://imagine-public.x.ai/imagine-public/images/page.html"

    fakePage = MagicMock()
    fakePage.eval_on_selector_all.return_value = [
        userImage,
        userImageFromImagesPublic,
        systemImage,
        promoVideo,
        nonMedia,
        "",
        None,
    ]

    urls = gallery._extractMediaUrlsFromPage(fakePage)

    assert userImage in urls
    assert userImageFromImagesPublic in urls
    assert systemImage not in urls
    assert promoVideo not in urls
    assert nonMedia not in urls


# ---------------------------------------------------------------------------
# _collectPostUrls
# ---------------------------------------------------------------------------


def testCollectPostUrlsExtractsPostLinks(gallery: GrokGallery):
    """Links matching /imagine/post/ are extracted from the page DOM."""
    post1 = "https://grok.com/imagine/post/9a826579-a4c4-4b44-b29c-e2a20d316c92"
    post2 = "https://grok.com/imagine/post/1b2c3d4e-0000-1111-2222-333344445555"

    fakePage = MagicMock()
    # The CSS selector a[href*='/imagine/post/'] already excludes non-post hrefs;
    # the mock returns only what the selector would yield.
    fakePage.eval_on_selector_all.return_value = [post1, post2, ""]

    urls = gallery._collectPostUrls(fakePage)

    assert post1 in urls
    assert post2 in urls
    assert "" not in urls
    assert len(urls) == 2
    fakePage.eval_on_selector_all.assert_called_once_with(
        "a[href*='/imagine/post/']",
        "els => els.map(el => el.href)",
    )


def testCollectPostUrlsDeduplicates(gallery: GrokGallery):
    """Duplicate hrefs (same post linked twice on the gallery page) are collapsed."""
    post = "https://grok.com/imagine/post/9a826579-a4c4-4b44-b29c-e2a20d316c92"

    fakePage = MagicMock()
    fakePage.eval_on_selector_all.return_value = [post, post, post]

    urls = gallery._collectPostUrls(fakePage)

    assert urls == [post]


def testCollectPostUrlsReturnsEmptyWhenNoLinks(gallery: GrokGallery):
    """An empty gallery page yields an empty list without raising."""
    fakePage = MagicMock()
    fakePage.eval_on_selector_all.return_value = []

    assert gallery._collectPostUrls(fakePage) == []


def testIsGrokMediaResponseMatchesByExtension(gallery: GrokGallery):
    """Media extension in URL path is sufficient when the host is a known user-content CDN."""
    for domain in ("imagine-public.x.ai", "images-public.x.ai"):
        assert gallery._isGrokMediaResponse(f"https://{domain}/user/abc.png", "")
        assert gallery._isGrokMediaResponse(f"https://{domain}/user/abc.jpg", "")
        assert gallery._isGrokMediaResponse(f"https://{domain}/user/abc.mp4", "")
        assert gallery._isGrokMediaResponse(f"https://{domain}/user/abc.webp", "")
        assert not gallery._isGrokMediaResponse(f"https://{domain}/user/abc.js", "")
        assert not gallery._isGrokMediaResponse(f"https://{domain}/user/abc.html", "")


def testIsGrokMediaResponseMatchesByContentType(gallery: GrokGallery):
    """image/* and video/* content-types are captured from known user-content CDN domains."""
    for domain in ("imagine-public.x.ai", "images-public.x.ai"):
        assert gallery._isGrokMediaResponse(f"https://{domain}/image", "image/png")
        assert gallery._isGrokMediaResponse(f"https://{domain}/image", "image/jpeg")
        assert gallery._isGrokMediaResponse(f"https://{domain}/video", "video/mp4")
        assert gallery._isGrokMediaResponse(f"https://{domain}/video", "video/webm")
        assert not gallery._isGrokMediaResponse(
            f"https://{domain}/api", "application/json"
        )
        assert not gallery._isGrokMediaResponse(
            f"https://{domain}/js", "text/javascript"
        )


def testIsGrokMediaResponseExcludesGrokComDomain(gallery: GrokGallery):
    """Responses from grok.com itself are never captured — it is not a user-content CDN."""
    assert not gallery._isGrokMediaResponse(
        "https://grok.com/images/logo.png", "image/png"
    )
    assert not gallery._isGrokMediaResponse(
        "https://www.grok.com/promo.jpg", "image/jpeg"
    )
    assert not gallery._isGrokMediaResponse("https://grok.com/clip.mp4", "video/mp4")


def testIsGrokMediaResponseExcludesUnknownCdnDomains(gallery: GrokGallery):
    """Images from third-party or unknown CDN domains are excluded by the allowlist."""
    # Profile pictures, analytics pixels, ad networks, etc. must all be rejected.
    assert not gallery._isGrokMediaResponse(
        "https://cdn.example.ai/user/abc.png", "image/png"
    )
    assert not gallery._isGrokMediaResponse(
        "https://pbs.twimg.com/profile_img/photo.jpg", "image/jpeg"
    )
    assert not gallery._isGrokMediaResponse(
        "https://ads.tracker.com/pixel.gif", "image/gif"
    )
    # Only the known user-content CDN domain should pass through.
    assert gallery._isGrokMediaResponse(
        "https://imagine-public.x.ai/user/abc.png", "image/png"
    )


def testDownloadMediaFilesDryRunDoesNotWrite(gallery: GrokGallery, tmp_path: Path):
    destDir = tmp_path / "Downloads" / "Grok"
    gallery.downloadDir = destDir
    stats = gallery._downloadMediaFiles(["https://example.com/image01.png"])
    assert stats == {"downloaded": 1, "skipped": 0, "errors": 0}
    assert not (destDir / "image01.png").exists()


def testDownloadMediaFilesSkipsExisting(confirmedGallery: GrokGallery, tmp_path: Path):
    destDir = tmp_path / "Downloads" / "Grok"
    destDir.mkdir(parents=True)
    target = destDir / "image01.png"
    target.write_bytes(b"exists")
    confirmedGallery.downloadDir = destDir
    stats = confirmedGallery._downloadMediaFiles(["https://example.com/image01.png"])
    assert stats == {"downloaded": 0, "skipped": 1, "errors": 0}


def testDownloadMediaFilesUsesPlaywrightContext(
    confirmedGallery: GrokGallery, tmp_path: Path
):
    """When a playwright context is supplied the authenticated request path is used."""
    fakeResponse = MagicMock()
    fakeResponse.ok = True
    fakeResponse.body.return_value = b"image-data"

    fakeContext = MagicMock()
    fakeContext.request.get.return_value = fakeResponse
    destDir = tmp_path / "Downloads" / "Grok"
    confirmedGallery.downloadDir = destDir

    stats = confirmedGallery._downloadMediaFiles(
        ["https://example.com/image01.png"], playwrightContext=fakeContext
    )

    assert stats == {"downloaded": 1, "skipped": 0, "errors": 0}
    fakeContext.request.get.assert_called_once_with(
        "https://example.com/image01.png", headers={"Referer": "https://grok.com/"}
    )
    assert (destDir / "image01.png").read_bytes() == b"image-data"


def testDownloadMediaFilesPlaywrightContextNonOkResponse(
    confirmedGallery: GrokGallery, tmp_path: Path
):
    """A non-OK playwright response is counted as an error."""
    fakeResponse = MagicMock()
    fakeResponse.ok = False
    fakeResponse.status = 403

    fakeContext = MagicMock()
    fakeContext.request.get.return_value = fakeResponse
    confirmedGallery.downloadDir = tmp_path / "Downloads" / "Grok"

    stats = confirmedGallery._downloadMediaFiles(
        ["https://example.com/image01.png"], playwrightContext=fakeContext
    )

    assert stats == {"downloaded": 0, "skipped": 0, "errors": 1}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# _sanitizeStorageState
# ---------------------------------------------------------------------------


def testSanitizeStorageStateConvertsZeroExpiresToMinusOne(
    tmp_path, gallery: GrokGallery
):
    """expires: 0 must be normalised to -1 (Playwright rejects 0)."""
    f = tmp_path / "session.json"
    f.write_text(json.dumps({"cookies": [{"name": "a", "expires": 0}], "origins": []}))
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == -1


def testSanitizeStorageStateConvertsNullExpiresToMinusOne(
    tmp_path, gallery: GrokGallery
):
    """expires: null must be normalised to -1."""
    f = tmp_path / "session.json"
    f.write_text(
        json.dumps({"cookies": [{"name": "a", "expires": None}], "origins": []})
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == -1


def testSanitizeStorageStateConvertsNegativeExpiresToMinusOne(
    tmp_path, gallery: GrokGallery
):
    """expires: -999 must be normalised to -1 (only -1 is a valid sentinel)."""
    f = tmp_path / "session.json"
    f.write_text(
        json.dumps({"cookies": [{"name": "a", "expires": -999}], "origins": []})
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == -1


def testSanitizeStorageStateTruncatesFloatExpires(tmp_path, gallery: GrokGallery):
    """expires with a fractional part should be truncated to int."""
    f = tmp_path / "session.json"
    f.write_text(
        json.dumps({"cookies": [{"name": "a", "expires": 1700000000.9}], "origins": []})
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == 1700000000


def testSanitizeStorageStateConvertsWholeNumberFloatToInt(
    tmp_path, gallery: GrokGallery
):
    """expires as a whole-number float (e.g. 1742000000.0) must be converted to int.

    SQLite may return INTEGER columns as Python floats; json.dumps then writes
    '1742000000.0' which Playwright rejects even though the numeric value is
    valid.  The sanitizer must convert ALL floats, not just fractional ones.
    """
    f = tmp_path / "session.json"
    # Write the raw float string directly so json.loads returns a float
    f.write_text('{"cookies": [{"name": "a", "expires": 1742000000.0}], "origins": []}')
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert isinstance(data["cookies"][0]["expires"], int)
    assert data["cookies"][0]["expires"] == 1742000000


def testSanitizeStorageStatePreservesValidExpires(tmp_path, gallery: GrokGallery):
    """Valid expires (-1 or positive integer) must be left unchanged."""
    f = tmp_path / "session.json"
    f.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "a", "expires": -1},
                    {"name": "b", "expires": 1700000000},
                ],
                "origins": [],
            }
        )
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == -1
    assert data["cookies"][1]["expires"] == 1700000000


def testSanitizeStorageStatePreservesExpiresAtMaxLimit(tmp_path, gallery: GrokGallery):
    """An expires exactly equal to kMaxCookieExpiresDateInSeconds (253402300799) is valid
    and must be left unchanged."""
    f = tmp_path / "session.json"
    f.write_text(
        json.dumps({"cookies": [{"name": "a", "expires": 253402300799}], "origins": []})
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == 253402300799


def testSanitizeStorageStateClampsOverLimitInt(tmp_path, gallery: GrokGallery):
    """expires > 253402300799 is rejected by Playwright — it must be clamped to the max.

    Some sites set far-future expiry timestamps (e.g. 9999999999999) which
    exceed Playwright's internal kMaxCookieExpiresDateInSeconds limit.
    """
    f = tmp_path / "session.json"
    f.write_text(
        json.dumps(
            {"cookies": [{"name": "a", "expires": 9999999999999}], "origins": []}
        )
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == 253402300799


def testSanitizeStorageStateClampsOverLimitFloat(tmp_path, gallery: GrokGallery):
    """A float expires that exceeds the max limit must also be clamped to 253402300799."""
    f = tmp_path / "session.json"
    # Write raw float string so json.loads returns a float
    f.write_text(
        '{"cookies": [{"name": "a", "expires": 9999999999999.0}], "origins": []}'
    )
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == 253402300799


def testSanitizeStorageStateConvertsBooleanToMinusOne(tmp_path, gallery: GrokGallery):
    """expires: True (Python bool) serialises to JSON true which Playwright cannot use
    as a numeric expires.  It must be normalised to -1."""
    f = tmp_path / "session.json"
    # json.dumps writes True as JSON true
    f.write_text('{"cookies": [{"name": "a", "expires": true}], "origins": []}')
    gallery._sanitizeStorageState(f)
    data = json.loads(f.read_text())
    assert data["cookies"][0]["expires"] == -1


def testSanitizeStorageStateHandlesMissingFile(tmp_path, gallery: GrokGallery):
    """A missing file must not raise — caller will handle the downstream error."""
    gallery._sanitizeStorageState(tmp_path / "nonexistent.json")  # should not raise


# ---------------------------------------------------------------------------
# _firefoxLaunch
# ---------------------------------------------------------------------------


def testFirefoxLaunchReturnsLaunchedBrowser(gallery: GrokGallery):
    """When launch succeeds the returned browser object is passed through."""
    fakeBrowser = MagicMock()
    fakePW = MagicMock()
    fakePW.firefox.launch.return_value = fakeBrowser

    result = gallery._firefoxLaunch(fakePW)

    fakePW.firefox.launch.assert_called_once_with(headless=True)
    assert result is fakeBrowser


def testFirefoxLaunchConvertsNotInstalledErrorToRuntimeError(gallery: GrokGallery):
    """When the Firefox binary is absent Playwright raises an error containing
    'Executable doesn't exist'.  _firefoxLaunch must convert that to RuntimeError."""
    fakePW = MagicMock()
    fakePW.firefox.launch.side_effect = Exception(
        "BrowserType.launch: Executable doesn't exist at /home/user/.cache/ms-playwright/firefox-1509/firefox/firefox"
    )

    with pytest.raises(RuntimeError, match="playwright install firefox"):
        gallery._firefoxLaunch(fakePW)


def testFirefoxLaunchConvertsPlaywrightInstallHintToRuntimeError(
    gallery: GrokGallery,
):
    """Error messages containing the 'playwright install' hint are also converted."""
    fakePW = MagicMock()
    fakePW.firefox.launch.side_effect = Exception(
        "Please run the following command to download new browsers:\n\n    playwright install\n"
    )

    with pytest.raises(RuntimeError, match="playwright install firefox"):
        gallery._firefoxLaunch(fakePW)


def testFirefoxLaunchPropagatesOtherExceptions(gallery: GrokGallery):
    """Errors unrelated to missing browser binaries are re-raised unchanged."""
    fakePW = MagicMock()
    fakePW.firefox.launch.side_effect = OSError("network error")

    with pytest.raises(OSError, match="network error"):
        gallery._firefoxLaunch(fakePW)


# ---------------------------------------------------------------------------
# _findFirefoxProfile
# ---------------------------------------------------------------------------


def _make_firefox_base(tmp_path: Path, profiles: list) -> Path:
    """Create a minimal Firefox profile directory tree under tmp_path.

    Each entry in *profiles* is a dict with keys:
        section (str): ConfigParser section name, e.g. "Profile0"
        path    (str): value for the Path key
        relative (bool): whether IsRelative should be "1" (default True)
        default  (bool): whether to add Default=1 (default False)
    """
    import configparser

    base = tmp_path / "firefox"
    base.mkdir()
    config = configparser.ConfigParser()
    for p in profiles:
        section = p["section"]
        config[section] = {"Path": p["path"]}
        if p.get("relative", True):
            config[section]["IsRelative"] = "1"
            (base / p["path"]).mkdir(parents=True, exist_ok=True)
        if p.get("default", False):
            config[section]["Default"] = "1"
    with open(base / "profiles.ini", "w") as f:
        config.write(f)
    return base


def testFindFirefoxProfileReturnsDefaultProfile(gallery: GrokGallery, tmp_path: Path):
    """The section with Default=1 is returned ahead of any other Profile section."""
    base = _make_firefox_base(
        tmp_path,
        [
            {"section": "Profile0", "path": "profiles/other"},
            {"section": "Profile1", "path": "profiles/default", "default": True},
        ],
    )
    result = gallery._findFirefoxProfile(_firefoxBase=base)
    assert result == base / "profiles/default"


def testFindFirefoxProfileReturnsFallbackProfile(gallery: GrokGallery, tmp_path: Path):
    """When no Default=1 is set, the first Profile section is returned."""
    base = _make_firefox_base(
        tmp_path,
        [{"section": "Profile0", "path": "profiles/first"}],
    )
    result = gallery._findFirefoxProfile(_firefoxBase=base)
    assert result == base / "profiles/first"


def testFindFirefoxProfileReturnsNoneWhenNoIni(gallery: GrokGallery, tmp_path: Path):
    """None is returned when profiles.ini does not exist."""
    base = tmp_path / "firefox_missing"
    result = gallery._findFirefoxProfile(_firefoxBase=base)
    assert result is None


def testFindFirefoxProfilePrefersProfileWithCookies(
    gallery: GrokGallery, tmp_path: Path
):
    """When multiple candidate bases exist, the profile that has cookies.sqlite
    is preferred over one without — even when the empty profile is the 'default'."""
    import configparser as cp

    home = tmp_path

    # Traditional install: has profiles.ini + default profile, but NO cookies.sqlite.
    tradBase = home / ".mozilla" / "firefox"
    tradBase.mkdir(parents=True, exist_ok=True)
    ini = cp.ConfigParser()
    ini["Profile0"] = {"Path": "default", "IsRelative": "1", "Default": "1"}
    tradProfileDir = tradBase / "default"
    tradProfileDir.mkdir(parents=True, exist_ok=True)
    with open(tradBase / "profiles.ini", "w") as f:
        ini.write(f)
    # No cookies.sqlite in tradProfileDir.

    # Snap install: has profiles.ini + profile WITH cookies.sqlite.
    snapBase = home / "snap" / "firefox" / "common" / ".mozilla" / "firefox"
    snapBase.mkdir(parents=True, exist_ok=True)
    ini2 = cp.ConfigParser()
    ini2["Profile0"] = {"Path": "snap-profile", "IsRelative": "1"}
    snapProfileDir = snapBase / "snap-profile"
    snapProfileDir.mkdir(parents=True, exist_ok=True)
    (snapProfileDir / "cookies.sqlite").write_bytes(b"")  # exists
    with open(snapBase / "profiles.ini", "w") as f:
        ini2.write(f)

    with patch("organiseMyVideo.grokGallery.Path.home", return_value=home):
        result = gallery._findFirefoxProfile()

    assert result == snapProfileDir, (
        "should prefer the Snap profile that has cookies.sqlite over "
        "the traditional profile that does not"
    )


def testFindFirefoxProfileFallsBackToFirstCandidateWhenNoCookies(
    gallery: GrokGallery, tmp_path: Path
):
    """When no candidate base has cookies.sqlite, the default profile from the
    first valid candidate base is returned."""
    home = tmp_path

    # Only the traditional install exists, and its profile has no cookies.sqlite.
    tradBase = home / ".mozilla" / "firefox"
    tradBase.mkdir(parents=True, exist_ok=True)
    import configparser as cp

    ini = cp.ConfigParser()
    ini["Profile0"] = {"Path": "default-profile", "IsRelative": "1", "Default": "1"}
    profileDir = tradBase / "default-profile"
    profileDir.mkdir(parents=True, exist_ok=True)
    with open(tradBase / "profiles.ini", "w") as f:
        ini.write(f)
    # No cookies.sqlite — should still return the profile.

    with patch("organiseMyVideo.grokGallery.Path.home", return_value=home):
        result = gallery._findFirefoxProfile()

    assert result == profileDir


def testFindFirefoxProfileReturnsNoneWhenNoInstallFound(
    gallery: GrokGallery, tmp_path: Path
):
    """None is returned when none of the candidate bases contain profiles.ini."""
    home = tmp_path  # empty — no Firefox directories exist
    with patch("organiseMyVideo.grokGallery.Path.home", return_value=home):
        result = gallery._findFirefoxProfile()
    assert result is None


def testFindFirefoxProfilePicksMostRecentCookies(gallery: GrokGallery, tmp_path: Path):
    """When two installs both have cookies.sqlite, the one with the most
    recently modified file is preferred (the actively-used install)."""
    import os
    import time
    import configparser as cp

    home = tmp_path

    def _makeInstall(base: Path, profile_name: str, cookies_mtime: float) -> Path:
        base.mkdir(parents=True, exist_ok=True)
        ini = cp.ConfigParser()
        ini["Profile0"] = {"Path": profile_name, "IsRelative": "1", "Default": "1"}
        profileDir = base / profile_name
        profileDir.mkdir(parents=True, exist_ok=True)
        db = profileDir / "cookies.sqlite"
        db.write_bytes(b"")
        os.utime(str(db), (cookies_mtime, cookies_mtime))
        with open(base / "profiles.ini", "w") as f:
            ini.write(f)
        return profileDir

    old_time = time.time() - 3600  # 1 hour ago
    new_time = time.time()  # now

    tradBase = home / ".mozilla" / "firefox"
    snapBase = home / "snap" / "firefox" / "common" / ".mozilla" / "firefox"

    _makeInstall(tradBase, "old-profile", old_time)
    snapProfile = _makeInstall(snapBase, "new-profile", new_time)

    with patch("organiseMyVideo.grokGallery.Path.home", return_value=home):
        result = gallery._findFirefoxProfile()

    assert (
        result == snapProfile
    ), "should pick the install with the newer cookies.sqlite"


# ---------------------------------------------------------------------------
# importFirefoxSession
# ---------------------------------------------------------------------------


def _make_firefox_cookies_db(profile_dir: Path, cookies: list) -> None:
    """Create a minimal Firefox moz_cookies SQLite database.

    Each entry in *cookies* is a tuple:
        (name, value, host, path, expiry, isSecure, isHttpOnly, sameSite)
    """
    db_path = profile_dir / "cookies.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE moz_cookies (
            name TEXT, value TEXT, host TEXT, path TEXT,
            expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER, sameSite INTEGER
        )
        """
    )
    conn.executemany("INSERT INTO moz_cookies VALUES (?,?,?,?,?,?,?,?)", cookies)
    conn.commit()
    conn.close()


def testImportFirefoxSessionWritesStorageState(gallery: GrokGallery, tmp_path: Path):
    """Cookies for grok.com are read and written as a Playwright storage-state JSON."""
    profileDir = tmp_path / "profile"
    profileDir.mkdir()
    _make_firefox_cookies_db(
        profileDir,
        [
            ("session_id", "abc123", "grok.com", "/", 9999999999, 1, 1, 1),
            ("auth_token", "tok456", ".grok.com", "/", 9999999999, 1, 0, 0),
        ],
    )
    sessionFile = tmp_path / "session.json"

    result = gallery.importFirefoxSession(
        sessionFile=sessionFile, profilePath=profileDir
    )

    assert result is True
    assert sessionFile.exists()
    state = json.loads(sessionFile.read_text())
    assert "cookies" in state
    names = {c["name"] for c in state["cookies"]}
    assert "session_id" in names
    assert "auth_token" in names
    # sameSite values should be mapped to Playwright strings
    for cookie in state["cookies"]:
        assert cookie["sameSite"] in {"None", "Lax", "Strict"}


def testImportFirefoxSessionMapsZeroExpiryToMinusOne(
    gallery: GrokGallery, tmp_path: Path
):
    """Firefox session cookies use expiry=0; Playwright requires -1 (not 0)."""
    profileDir = tmp_path / "profile"
    profileDir.mkdir()
    _make_firefox_cookies_db(
        profileDir,
        [
            # expiry=0 → session cookie (Firefox representation)
            ("session_cookie", "val1", "grok.com", "/", 0, 1, 1, 1),
            # expiry>0 → persistent cookie, must be preserved as-is
            ("persistent_cookie", "val2", "grok.com", "/", 9999999999, 1, 0, 0),
        ],
    )
    sessionFile = tmp_path / "session.json"

    result = gallery.importFirefoxSession(
        sessionFile=sessionFile, profilePath=profileDir
    )

    assert result is True
    state = json.loads(sessionFile.read_text())
    cookies = {c["name"]: c for c in state["cookies"]}
    # Session cookie: expiry=0 must be mapped to -1
    assert cookies["session_cookie"]["expires"] == -1
    # Persistent cookie: positive expiry must pass through unchanged
    assert cookies["persistent_cookie"]["expires"] == 9999999999


def testImportFirefoxSessionClampsOverLimitExpiry(gallery: GrokGallery, tmp_path: Path):
    """Cookies with expiry > 253402300799 (Playwright's kMaxCookieExpiresDateInSeconds)
    must be clamped to 253402300799.

    Some sites and auth providers set expiry in the far future (e.g.
    expiry=9999999999999).  Playwright's rewriteCookies() rejects any
    expires > 253402300799 with "Cookie should have a valid expires".
    """
    profileDir = tmp_path / "profile"
    profileDir.mkdir()
    _make_firefox_cookies_db(
        profileDir,
        [
            # Expiry far beyond year 9999 — Playwright would reject this
            ("far_future", "val", "grok.com", "/", 9999999999999, 1, 0, 0),
        ],
    )
    sessionFile = tmp_path / "session.json"

    result = gallery.importFirefoxSession(
        sessionFile=sessionFile, profilePath=profileDir
    )

    assert result is True
    state = json.loads(sessionFile.read_text())
    cookie = state["cookies"][0]
    assert (
        cookie["expires"] == 253402300799
    ), "far-future expiry must be clamped to kMaxCookieExpiresDateInSeconds"


def testImportFirefoxSessionConvertsFloatExpiryToInt(
    gallery: GrokGallery, tmp_path: Path
):
    """SQLite may return INTEGER columns as Python floats (REAL affinity).

    json.dumps serialises 1742000000.0 as '1742000000.0', which Playwright
    rejects.  importFirefoxSession must write a plain JSON integer.
    """
    profileDir = tmp_path / "profile"
    profileDir.mkdir()
    db_path = profileDir / "cookies.sqlite"
    # Use a REAL column type to force SQLite to return Python floats, simulating
    # the REAL-affinity storage that can occur even in INTEGER columns due to
    # SQLite's dynamic typing.  This reproduces the bug where json.dumps writes
    # '1742000000.0' instead of '1742000000', which Playwright rejects.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE moz_cookies (
            name TEXT, value TEXT, host TEXT, path TEXT,
            expiry REAL, isSecure INTEGER, isHttpOnly INTEGER, sameSite INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO moz_cookies VALUES (?,?,?,?,?,?,?,?)",
        ("float_cookie", "v", "grok.com", "/", 1742000000.0, 1, 0, 0),
    )
    conn.commit()
    conn.close()

    sessionFile = tmp_path / "session.json"
    result = gallery.importFirefoxSession(
        sessionFile=sessionFile, profilePath=profileDir
    )

    assert result is True
    state = json.loads(sessionFile.read_text())
    cookie = state["cookies"][0]
    assert isinstance(
        cookie["expires"], int
    ), "expires must be a plain int, not a float"
    assert cookie["expires"] == 1742000000


def testImportFirefoxSessionReturnsFalseWhenNoCookiesDbFile(
    gallery: GrokGallery, tmp_path: Path
):
    """False is returned when the profile directory has no cookies.sqlite."""
    profileDir = tmp_path / "profile"
    profileDir.mkdir()
    sessionFile = tmp_path / "session.json"

    result = gallery.importFirefoxSession(
        sessionFile=sessionFile, profilePath=profileDir
    )

    assert result is False
    assert not sessionFile.exists()


def testImportFirefoxSessionReturnsFalseWhenNoGrokCookies(
    gallery: GrokGallery, tmp_path: Path
):
    """False is returned when cookies.sqlite exists but has no grok.com/x.ai rows."""
    profileDir = tmp_path / "profile"
    profileDir.mkdir()
    _make_firefox_cookies_db(
        profileDir,
        [("unrelated", "val", "example.com", "/", 9999999999, 0, 0, 0)],
    )
    sessionFile = tmp_path / "session.json"

    result = gallery.importFirefoxSession(
        sessionFile=sessionFile, profilePath=profileDir
    )

    assert result is False
    assert not sessionFile.exists()


def testImportFirefoxSessionReturnsFalseWhenNoProfile(
    gallery: GrokGallery, tmp_path: Path
):
    """False is returned when no Firefox profile can be located."""
    sessionFile = tmp_path / "session.json"
    # Patch _findFirefoxProfile to return None (no Firefox installed)
    with patch.object(gallery, "_findFirefoxProfile", return_value=None):
        result = gallery.importFirefoxSession(sessionFile=sessionFile)

    assert result is False
    assert not sessionFile.exists()


def testResetGrokConfigDeletesBothFiles(confirmedGallery: GrokGallery, tmp_path: Path):
    sessionFile = tmp_path / "grokSession.json"
    credFile = tmp_path / "grokCredentials.json"
    sessionFile.write_text("{}")
    credFile.write_text("{}")

    result = confirmedGallery.resetGrokConfig(
        sessionFile=sessionFile, credentialsFile=credFile
    )

    assert not sessionFile.exists()
    assert not credFile.exists()
    assert str(sessionFile) in result["deleted"]
    assert str(credFile) in result["deleted"]


def testResetGrokConfigDryRunDoesNotDelete(gallery: GrokGallery, tmp_path: Path):
    sessionFile = tmp_path / "grokSession.json"
    credFile = tmp_path / "grokCredentials.json"
    sessionFile.write_text("{}")
    credFile.write_text("{}")

    result = gallery.resetGrokConfig(sessionFile=sessionFile, credentialsFile=credFile)

    assert sessionFile.exists()
    assert credFile.exists()
    assert str(sessionFile) in result["deleted"]


def _sessionWithGrokCookie(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "sso",
                        "value": "token",
                        "domain": ".grok.com",
                        "path": "/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def testDownloadGeneratedMediaListsSourceGeneratedOnly(tmp_path: Path):
    sessionFile = _sessionWithGrokCookie(tmp_path / "session.json")
    listed = [
        {
            "assetId": "img-1",
            "key": "users/me/img-1/content",
            "mimeType": "image/jpeg",
        }
    ]
    fetched = {}

    def fetchBytes(url: str) -> bytes:
        fetched["url"] = url
        return b"jpeg-bytes"

    gallery = GrokGallery(
        dryRun=False,
        downloadDir=tmp_path / "Grok",
        listAssets=lambda: listed,
        fetchBytes=fetchBytes,
    )
    stats = gallery.downloadGeneratedMedia(sessionFile=sessionFile)

    assert stats["assetsFound"] == 1
    assert stats["downloaded"] == 1
    assert (tmp_path / "Grok" / "img-1.jpg").read_bytes() == b"jpeg-bytes"
    assert "assets.grok.com/users/me/img-1/content" in fetched["url"]


def testDownloadGeneratedMediaDryRunDoesNotWrite(tmp_path: Path):
    sessionFile = _sessionWithGrokCookie(tmp_path / "session.json")
    listed = [{"assetId": "img-1", "mimeType": "image/png"}]
    gallery = GrokGallery(
        dryRun=True,
        downloadDir=tmp_path / "Grok",
        listAssets=lambda: listed,
        fetchBytes=lambda url: b"nope",
    )

    stats = gallery.downloadGeneratedMedia(sessionFile=sessionFile)

    assert stats["downloaded"] == 1
    assert not (tmp_path / "Grok").exists()


def testDownloadGeneratedMediaSkipsExisting(tmp_path: Path):
    sessionFile = _sessionWithGrokCookie(tmp_path / "session.json")
    destDir = tmp_path / "Grok"
    destDir.mkdir()
    (destDir / "img-1.png").write_bytes(b"already")
    gallery = GrokGallery(
        dryRun=False,
        downloadDir=destDir,
        listAssets=lambda: [{"assetId": "img-1", "mimeType": "image/png"}],
        fetchBytes=lambda url: b"new",
    )

    stats = gallery.downloadGeneratedMedia(sessionFile=sessionFile)

    assert stats["skipped"] == 1
    assert (destDir / "img-1.png").read_bytes() == b"already"


def testDownloadGeneratedMediaRejectsExpiredSession(tmp_path: Path):
    sessionFile = _sessionWithGrokCookie(tmp_path / "session.json")
    gallery = GrokGallery(dryRun=True, downloadDir=tmp_path / "Grok")

    def fail(url, cookieHeader, payload=None):
        del url, cookieHeader, payload
        raise RuntimeError(
            "grok.com session expired or Cloudflare blocked the request; "
            "log in with Firefox and run --import-firefox-session --confirm"
        )

    gallery._grokJsonRequest = fail  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="session expired"):
        gallery.downloadGeneratedMedia(sessionFile=sessionFile)


def testMediaFromPostCollectsNestedImageAndHdVideo():
    gallery = GrokGallery(dryRun=True)
    records: list[dict] = []
    seen: set[str] = set()
    gallery._mediaFromPost(
        {
            "id": "vid-1",
            "mediaType": "MEDIA_POST_TYPE_VIDEO",
            "mimeType": "video/mp4",
            "hd1080MediaUrl": "https://cdn.example/vid-hd.mp4",
            "mediaUrl": "https://cdn.example/vid.mp4",
            "images": [
                {
                    "id": "img-1",
                    "mediaType": "MEDIA_POST_TYPE_IMAGE",
                    "mimeType": "image/jpeg",
                    "mediaUrl": "https://cdn.example/img.jpg",
                }
            ],
            "videos": [
                {
                    "id": "vid-1",
                    "mediaType": "MEDIA_POST_TYPE_VIDEO",
                    "mimeType": "video/mp4",
                    "hd1080MediaUrl": "https://cdn.example/vid-hd.mp4",
                }
            ],
        },
        seen,
        records,
    )
    byId = {item["assetId"]: item for item in records}
    assert byId["vid-1"]["url"] == "https://cdn.example/vid-hd.mp4"
    assert byId["img-1"]["url"] == "https://cdn.example/img.jpg"


def testCookieHeaderKeepsOneGrokComValuePerName():
    gallery = GrokGallery(dryRun=True)
    header = gallery._cookieHeader(
        [
            {"name": "sso", "value": "xai", "domain": ".x.ai"},
            {"name": "sso", "value": "grok", "domain": ".grok.com"},
            {"name": "sso-rw", "value": "rw", "domain": "grok.com"},
        ],
        host="grok.com",
    )
    assert "sso=grok" in header
    assert "sso=xai" not in header
    assert header.count("sso=") == 1


def testDownloadGeneratedMediaRejectsEmptyOwnedLibrary(tmp_path: Path):
    sessionFile = _sessionWithGrokCookie(tmp_path / "session.json")
    gallery = GrokGallery(dryRun=True, downloadDir=tmp_path / "Grok")

    def empty(url, cookieHeader, payload=None):
        del url, cookieHeader, payload
        return json.dumps({"assets": [], "conversations": []})

    gallery._grokJsonRequest = empty  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="no stored Imagine generations"):
        gallery.downloadGeneratedMedia(sessionFile=sessionFile)


def testSessionCookiesLoadRequiresGrokDomain(tmp_path: Path):
    sessionFile = tmp_path / "session.json"
    sessionFile.write_text(
        json.dumps({"cookies": [{"name": "a", "value": "b", "domain": "example.com"}]}),
        encoding="utf-8",
    )
    gallery = GrokGallery(dryRun=True)
    with pytest.raises(RuntimeError, match="no grok.com cookies"):
        gallery._sessionCookiesLoad(sessionFile)
