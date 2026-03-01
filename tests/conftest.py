"""
Stub the optional organiseMyProjects package so organiseMyVideo can be
imported in environments where that package is not installed.
"""

import logging
import sys
import types


class _StubLogger:
    """
    Minimal stand-in for the organiseMyProjects custom logger.

    Supports the standard methods (info, warning, error, debug) plus the
    custom message-type methods used by organiseMyVideo.py:
      - value(msg)  — key-value informational message
      - doing(msg)  — "starting X" step message
      - done(msg)   — "X complete" step message
    """

    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._log.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._log.error(msg, *args, **kwargs)

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log.debug(msg, *args, **kwargs)

    def value(self, msg: str, *args, **kwargs) -> None:
        self._log.info(msg, *args, **kwargs)

    def doing(self, msg: str, *args, **kwargs) -> None:
        self._log.info(msg, *args, **kwargs)

    def done(self, msg: str, *args, **kwargs) -> None:
        self._log.info(msg, *args, **kwargs)


def _getStubLogger(name: str, **kwargs) -> _StubLogger:
    return _StubLogger(name)


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
