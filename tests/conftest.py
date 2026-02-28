"""
Stub the optional organiseMyProjects package so organiseMyVideo can be
imported in environments where that package is not installed.
"""

import logging
import sys
import types


def _stubOrganiseMyProjects() -> None:
    """Insert lightweight stubs for organiseMyProjects and its sub-modules."""
    if "organiseMyProjects" in sys.modules:
        return

    pkg = types.ModuleType("organiseMyProjects")
    logUtils = types.ModuleType("organiseMyProjects.logUtils")
    logUtils.getLogger = lambda name, **kw: logging.getLogger(name)
    logUtils.drawBox = lambda text: None

    pkg.logUtils = logUtils
    sys.modules["organiseMyProjects"] = pkg
    sys.modules["organiseMyProjects.logUtils"] = logUtils


_stubOrganiseMyProjects()
