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

_DRY_RUN_PREFIX = "[] "


class _StubLogger:
    """Lightweight stand-in for organiseMyProjects._OrganiseLoggerAdapter."""

    def __init__(self, name: str = "OrganiseMyTool", dryRun: bool = False, **kwargs) -> None:
        self._log = logging.getLogger(name)
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
