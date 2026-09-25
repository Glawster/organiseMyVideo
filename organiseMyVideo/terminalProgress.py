"""Reusable single-line terminal progress display."""

from __future__ import annotations

import shutil
import sys
from typing import Optional, TextIO

_PROGRESS_BAR_WIDTH = 24


class TerminalProgress:
    """Render one in-place terminal progress line for long-running scans."""

    def __init__(self, total: int, label: str, stream: Optional[TextIO] = None):
        self.total = max(total, 0)
        self.label = label
        self.stream = stream if stream is not None else sys.stderr
        isatty = getattr(self.stream, "isatty", None)
        self.enabled = bool(callable(isatty) and isatty())
        self.displayWidth = 0

    def render(self, completed: int, name: str = "") -> None:
        """Render current progress without adding a scrolling log line."""
        if not self.enabled:
            return
        if self.total:
            fraction = min(completed / self.total, 1.0)
            filled = int(fraction * _PROGRESS_BAR_WIDTH)
            percent = f"{fraction * 100:3.0f}%"
            totalText = str(self.total)
        else:
            filled = 0
            percent = " --%"
            totalText = "?"
        bar = "#" * filled + "-" * (_PROGRESS_BAR_WIDTH - filled)
        prefix = f"{self.label}: [{bar}] {percent} ({completed}/{totalText})"
        columns = max(shutil.get_terminal_size(fallback=(80, 24)).columns, 20)
        available = columns - len(prefix) - 1
        suffix = ""
        if name and available > 0:
            suffix = " " + self._truncate(name, available)
        line = prefix + suffix
        padding = max(self.displayWidth - len(line), 0)
        self.stream.write(f"\r{line}{' ' * padding}")
        self.stream.flush()
        self.displayWidth = len(line)

    def finish(self) -> None:
        """Finish the live progress line before normal logger output resumes."""
        if self.enabled and self.displayWidth:
            self.stream.write("\n")
            self.stream.flush()
            self.displayWidth = 0

    @staticmethod
    def _truncate(text: str, maxWidth: int) -> str:
        """Return text shortened to the available terminal width."""
        if len(text) <= maxWidth:
            return text
        if maxWidth <= 3:
            return text[:maxWidth]
        return text[: maxWidth - 3] + "..."
