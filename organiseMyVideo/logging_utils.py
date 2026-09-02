"""Lazy application logging with no filesystem work during package import."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional


class ApplicationLogger:
    """Stable logger proxy initialized explicitly by an executable entry point."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Restore the side-effect-free adapter, primarily between test runs."""
        fallback = logging.getLogger("organiseMyVideo")
        fallback.addHandler(logging.NullHandler())
        self._adapter: Any = _StandardLoggerAdapter(fallback)

    @property
    def logger(self) -> logging.Logger:
        """Return the underlying standard-library logger."""
        return self._adapter.logger

    def configure(
        self,
        *,
        dryRun: bool,
        level: int,
        includeConsole: bool = True,
        logDir: Optional[Path] = None,
    ) -> None:
        """Initialize the shared application logger for executable use."""
        from organiseMyProjects.logUtils import getLogger, setApplication

        setApplication("organiseMyVideo", logDir=logDir)
        self._adapter = getLogger(
            includeConsole=includeConsole,
            dryRun=dryRun,
            level=level,
        )

    def __getattr__(self, name: str) -> Any:
        """Delegate semantic logging methods to the configured adapter."""
        return getattr(self._adapter, name)


class _StandardLoggerAdapter:
    """Side-effect-free fallback used when the package is imported as a library."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def doing(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.info(f"{message}...", *args, **kwargs)

    def done(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.info(f"...{message}", *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.info(f"...{message}", *args, **kwargs)

    def value(self, message: str, value: Any) -> None:
        self.logger.info("...%s: %s", message, value)

    def action(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.info(f"...{message}", *args, **kwargs)

    def multiline(self, message: Any, *lines: str) -> None:
        values = list(message) if isinstance(message, (list, tuple)) else [message, *lines]
        if not values:
            return
        rendered = [f"...{values[0]}:", *(f"     {value}" for value in values[1:])]
        self.logger.info("\n".join(rendered))

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.error(message, *args, **kwargs)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.logger.debug(message, *args, **kwargs)


logger = ApplicationLogger()


def initializeLogging(
    *,
    dryRun: bool,
    level: int = logging.INFO,
    includeConsole: bool = True,
    logDir: Optional[Path] = None,
) -> ApplicationLogger:
    """Configure and return the process-wide application logger."""
    logger.configure(
        dryRun=dryRun,
        level=level,
        includeConsole=includeConsole,
        logDir=logDir,
    )
    return logger


def resetLogging() -> None:
    """Restore side-effect-free library logging."""
    logger.reset()
