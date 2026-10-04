"""Console-script wrapper for catalogue-only media commands."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from . import __main__ as legacyCli
from .mediaLocate import MediaLocation, locateMovie, locateTvShow


def _locateParser() -> argparse.ArgumentParser:
    """Return the parser for ``media locate``."""

    parser = argparse.ArgumentParser(
        prog="organiseMyVideo media locate",
        description="Locate movie or TV show folders recorded in the media catalogue",
    )
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument(
        "--show",
        help=(
            "TV show to locate (case-insensitive exact or partial match); "
            "omit to list every catalogued show"
        ),
    )
    selectors.add_argument(
        "--movie",
        help="Movie title to locate (case-insensitive exact or partial match)",
    )
    return parser


def _printLocatedShows(matches: list[MediaLocation]) -> None:
    """Print each media title once, with the freshness of every stored folder."""

    previous = None
    for match in matches:
        if match.name != previous:
            print(match.name)
            previous = match.name
        print(f"  {match.folderPath}    {match.state}")


def _runMediaLocate(argv: Sequence[str]) -> int:
    """Run a catalogue-only movie or TV show location query."""

    args = _locateParser().parse_args(list(argv))
    # Preserve the default TV listing while selecting movies explicitly.
    requested = args.movie if args.movie is not None else args.show
    kind = "Movie" if args.movie is not None else "TV show"
    matches = (
        locateMovie(args.movie) if args.movie is not None else locateTvShow(args.show)
    )
    if requested is not None and not matches:
        print(f"{kind} not found in media catalogue: {requested}", file=sys.stderr)
        return 1
    _printLocatedShows(matches)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the public CLI through the canonical parser."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    return legacyCli.main(arguments)
