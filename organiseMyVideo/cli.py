"""Console-script wrapper for catalogue-only media commands."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import __main__ as legacyCli
from .mediaLocate import MediaLocation, locateMedia


def _locateParser() -> argparse.ArgumentParser:
    """Return the parser for ``media locate``."""

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo media locate",
        description="Locate movie or TV show folders recorded in the media catalogue",
    )
    parser.add_argument(
        "search",
        metavar="SEARCH",
        help="movie or TV title to locate (case-insensitive exact or partial match)",
    )
    return parser


def _printLocatedMedia(matches: list[MediaLocation]) -> None:
    """Print each media title once, with type and freshness of every location."""

    previous = None
    for match in matches:
        identity = (match.mediaType, match.name)
        if identity != previous:
            print(f"{match.mediaType}: {match.name}")
            previous = identity
        print(f"  {match.folderPath}    {match.state}")


def _runMediaLocate(argv: Sequence[str]) -> int:
    """Run one catalogue-only movie/TV location query."""

    args = _locateParser().parse_args(list(argv))
    matches = locateMedia(args.search)
    if not matches:
        print(f"Media not found in media catalogue: {args.search}", file=sys.stderr)
        return 1
    _printLocatedMedia(matches)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the public CLI through the canonical parser."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:2] == ["media", "locate"]:
        return _runMediaLocate(arguments[2:])
    return legacyCli.main(arguments)
