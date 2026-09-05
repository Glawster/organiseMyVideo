"""
Stub the optional organiseMyProjects package so organiseMyVideo can be
imported in environments where that package is not installed.

The stub mirrors the real _OrganiseLoggerAdapter from organiseMyProjects.logUtils
(copilot/introduce-logger-levels branch).  Key contract:
  - doing / done / info / value  — no dry-run prefix
  - action(msg)                  — prefixed with '[] ' when dryRun=True
"""

import logging
import sys
import types
from pathlib import Path

import pytest

_DRY_RUN_PREFIX = "[] "

# Ensure the project root is importable during test discovery (VS Code can invoke
# pytest from a path alias where root isn't first on sys.path).
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TESTS_DIR = Path(__file__).resolve().parent
for _path in (_PROJECT_ROOT, _TESTS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


class _StubLogger:
    """Lightweight stand-in for organiseMyProjects._OrganiseLoggerAdapter."""

    def __init__(
        self, name: str = "OrganiseMyTool", dryRun: bool = False, **kwargs
    ) -> None:
        self._log = logging.getLogger(name)
        self._log.setLevel(kwargs.get("level", logging.INFO))
        if kwargs.get("includeConsole") and not any(
            type(handler) is logging.StreamHandler for handler in self._log.handlers
        ):
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._log.addHandler(handler)
        self._prefix = _DRY_RUN_PREFIX if dryRun else ""
        # Expose .logger so the console-handler workaround in main() can access
        # the underlying logging.Logger via logger.logger.handlers
        self.logger = self._log

    def doing(self, message: str) -> None:
        self._log.info(f"{message}...")

    def done(self, message: str) -> None:
        self._log.info(f"...{message}")

    def info(self, message: str) -> None:
        self._log.info(f"...{message}")

    def value(self, message: str, variable) -> None:
        self._log.info(f"...{message}: {variable}")

    def action(self, message: str, *args, **kwargs) -> None:
        """Only method that carries the [] dry-run prefix."""
        self._log.info(f"...{self._prefix}{message}", *args, **kwargs)

    def multiline(
        self, message: str | list[str] | tuple[str, ...], *lines: str
    ) -> None:
        # Support both logger.multiline("header", "line1", ...) and
        # logger.multiline(["header", "line1", ...]) call styles.
        if lines:
            header = str(message)
            bodyLines = [str(line) for line in lines]
        elif isinstance(message, (list, tuple)):
            if not message:
                return
            header = str(message[0])
            bodyLines = [str(line) for line in message[1:]]
        else:
            header = str(message)
            bodyLines = []

        formattedLines = [f"...{self._prefix}{header}:"]
        formattedLines.extend(f"     {line}" for line in bodyLines)
        self._log.info("\n".join(formattedLines))

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log.debug(msg, *args, **kwargs)


def _getStubLogger(name: str = "OrganiseMyTool", **kwargs) -> _StubLogger:
    return _StubLogger(name, **kwargs)


def _stubOrganiseMyProjects() -> None:
    """Insert lightweight stubs for organiseMyProjects and its sub-modules."""
    if "organiseMyProjects" in sys.modules:
        return

    pkg = types.ModuleType("organiseMyProjects")
    logUtils = types.ModuleType("organiseMyProjects.logUtils")
    logUtils.getLogger = _getStubLogger
    logUtils.setApplication = lambda name, *args, **kwargs: None
    logUtils.drawBox = lambda text: None

    pkg.logUtils = logUtils
    sys.modules["organiseMyProjects"] = pkg
    sys.modules["organiseMyProjects.logUtils"] = logUtils


_stubOrganiseMyProjects()


@pytest.fixture(autouse=True)
def applicationStateIsolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep application configuration and cache writes inside the test sandbox."""
    from organiseMyVideo import (
        cameraInventory,
        constants,
        grok,
        grokGallery,
        mediaCatalogue,
        metadata,
        video,
        videoRescan,
    )
    from organiseMyVideo import __main__ as applicationMain

    configDir = tmp_path / "config"
    applicationPaths = {
        "APP_CONFIG_FILE": configDir / "config.json",
        "CAMERA_INVENTORY_DATABASE": tmp_path / "state" / "mediaCatalogue.sqlite",
        "MEDIA_CATALOGUE_DATABASE": tmp_path / "state" / "mediaCatalogue.sqlite",
        "GROK_CATALOG_FILE": configDir / "grokCatalog.json",
        "GROK_CREDENTIALS_FILE": configDir / "grokCredentials.json",
        "GROK_DOWNLOAD_DIR": tmp_path / "downloads" / "Grok",
        "GROK_SESSION_FILE": configDir / "grokSession.json",
        "METADATA_LIBRARY_FILE": configDir / "metadataLibrary.json",
    }
    modulesByPath = {
        "APP_CONFIG_FILE": (constants, applicationMain, video, videoRescan),
        "CAMERA_INVENTORY_DATABASE": (constants, cameraInventory),
        "MEDIA_CATALOGUE_DATABASE": (constants, mediaCatalogue),
        "GROK_CATALOG_FILE": (constants, grok),
        "GROK_CREDENTIALS_FILE": (constants, grokGallery),
        "GROK_DOWNLOAD_DIR": (constants, grok, grokGallery),
        "GROK_SESSION_FILE": (constants, grokGallery),
        "METADATA_LIBRARY_FILE": (constants, metadata),
    }

    for pathName, pathValue in applicationPaths.items():
        for module in modulesByPath[pathName]:
            monkeypatch.setattr(module, pathName, pathValue)
