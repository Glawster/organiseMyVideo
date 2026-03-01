"""
Stub the optional organiseMyProjects package so organiseMyVideo can be
imported in environments where that package is not installed.

The stub mirrors the real _OrganiseLoggerAdapter from organiseMyProjects.logUtils
so that tests exercise the same call signatures.
"""

import logging
import sys
import types

# Matches organiseMyProjects.logUtils._DRY_RUN_PREFIX
_DRY_RUN_PREFIX = "[] "


class _StubLogger:
    """
    Lightweight stand-in for organiseMyProjects._OrganiseLoggerAdapter.

    Output formats match the real adapter:
      doing(msg)            -> "{prefix}msg..."
      done(msg)             -> "...{prefix}msg"
      info(msg)             -> "...{prefix}msg"
      value(msg, variable)  -> "...{prefix}msg: variable"
      warning/error/debug   -> standard logging (with prefix when dryRun)
    """

    def __init__(self, name: str, dryRun: bool = False) -> None:
        self._log = logging.getLogger(name)
        self._dryRun = dryRun
        self._prefix = _DRY_RUN_PREFIX if dryRun else ""

    def doing(self, message: str) -> None:
        self._log.info(f"{self._prefix}{message}...")

    def done(self, message: str) -> None:
        self._log.info(f"...{self._prefix}{message}")

    def info(self, message: str) -> None:
        self._log.info(f"...{self._prefix}{message}")

    def value(self, message: str, variable) -> None:
        self._log.info(f"...{self._prefix}{message}: {variable}")

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log.warning(f"{self._prefix}{msg}", *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log.debug(f"{self._prefix}{msg}", *args, **kwargs)


def _getStubLogger(name: str = "OrganiseMyTool", dryRun: bool = False, **kwargs) -> _StubLogger:
    return _StubLogger(name, dryRun=dryRun)


def _stubOrganiseMyProjects() -> None:
    """Insert lightweight stubs for organiseMyProjects and its sub-modules."""
    if "organiseMyProjects" in sys.modules:
        return

    pkg = types.ModuleType("organiseMyProjects")
    logUtils = types.ModuleType("organiseMyProjects.logUtils")
    logUtils.getLogger = _getStubLogger
    logUtils.drawBox = lambda text: None

    pkg.logUtils = logUtils
    sys.modules["organiseMyProjects"] = pkg
    sys.modules["organiseMyProjects.logUtils"] = logUtils


_stubOrganiseMyProjects()
