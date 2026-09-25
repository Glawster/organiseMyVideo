"""Console-script wrapper for catalogue-only media commands."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import __main__ as legacyCli
from .mediaLocate import locateTvShow


def _locateParser() -> argparse.ArgumentParser:
    """Return the parser for ``media locate``."""

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo media locate",
        description="Locate canonical media folders recorded in the media catalogue",
    )
    parser.add_argument(
        "--show",
        required=True,
        help="TV show name to locate (case-insensitive exact or partial match)",
    )
    return parser


def _runMediaLocate(argv: Sequence[str]) -> int:
    """Run a catalogue-only TV show location query."""

    args = _locateParser().parse_args(argv)
    matches = locateTvShow(args.show)
    if not matches:
        print(f"TV show not found in media catalogue: {args.show}", file=sys.stderr)
        return 1

    for match in matches:
        print(match.name)
        print(f"  {match.folderPath}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the public CLI, handling catalogue queries before legacy dispatch."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) >= 2 and arguments[:2] == ["media", "locate"]:
        return _runMediaLocate(arguments[2:])
    return legacyCli.main(arguments)
