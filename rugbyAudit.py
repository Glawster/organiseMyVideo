#!/usr/bin/env python3
"""Interactive audit and tagging tool for rugby match MP4 files.

Purpose
- scan a folder recursively for MP4/M4V/MOV files
- read existing MP4 tags
- show current title/comment values as defaults
- prompt the user to confirm or replace title and score
- derive teams from title
- derive season and episode from folder/year and match ordering
- optionally write updated metadata back to files
- write a CSV audit report

User interaction rule
- pressing Enter accepts the shown default
- entering q quits the session
- entering p plays the current video so you can inspect it
- if there is no default, pressing Enter leaves the field blank

Recommended title format
    Home Team vs Away Team
or
    Home Team v Away Team

Recommended comment format
    33-31

Notes
- folder year is treated as the season start year
  example: folder 2024 => seasonLabel 2024/25
- episode is assigned by ordering matches within a season folder
  after sorting by file path

Dependencies
    pip install mutagen
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mutagen.mp4 import MP4, MP4FreeForm  # type: ignore

logger = logging.getLogger("mp4MatchAudit")
SUPPORTED_SUFFIXES = {".mp4", ".m4v", ".mov"}
FREEFORM_PREFIX = "----:com.apple.iTunes:"

ATOM_TO_FIELD = {
    "©nam": "title",
    "tvsh": "show",
    "tvsn": "season",
    "tves": "episode",
    "©day": "date",
    "desc": "description",
    "ldes": "longDescription",
    "©cmt": "comment",
    "©grp": "grouping",
    "©gen": "genre",
    "aART": "albumArtist",
    "©ART": "artist",
    "©alb": "album",
}

FIELD_TO_ATOM = {
    "title": "©nam",
    "show": "tvsh",
    "season": "tvsn",
    "episode": "tves",
    "date": "©day",
    "description": "desc",
    "comment": "©cmt",
    "grouping": "©grp",
    "genre": "©gen",
    "albumArtist": "aART",
    "artist": "©ART",
    "album": "©alb",
}


@dataclass
class SeasonInfo:
    seasonKey: int
    seasonLabel: str
    seasonStartYear: int
    seasonEndYear: int


@dataclass
class MatchInfo:
    title: str | None
    comment: str | None
    homeTeam: str | None
    awayTeam: str | None
    homeScore: int | None
    awayScore: int | None
    winner: str | None
    seasonInfo: SeasonInfo | None
    episode: int | None


class Mp4TagHelper:
    """Read and write MP4/M4V metadata tags using mutagen."""

    def readTags(self, filePath: Path) -> dict[str, object]:
        """Return a normalised dict of tag field-name → value for *filePath*."""
        try:
            mp4File = MP4(str(filePath))
        except Exception as exc:
            logger.warning("...failed to read tags: %s | %s", filePath, exc)
            return {"_readError": str(exc)}

        if mp4File.tags is None:
            return {}

        result: dict[str, object] = {}
        for key, rawValue in mp4File.tags.items():
            fieldName = ATOM_TO_FIELD.get(key, self._mapFreeformFieldName(key))
            result[fieldName] = self._normaliseTagValue(rawValue)
        return result

    def writeTags(self, filePath: Path, values: dict[str, object]) -> None:
        """Write *values* as MP4 tags to *filePath*, skipping blank/None entries."""
        mp4File = MP4(str(filePath))
        if mp4File.tags is None:
            mp4File.add_tags()

        for fieldName, value in values.items():
            if value is None or value == "":
                continue

            atom = FIELD_TO_ATOM.get(fieldName)
            if atom:
                mp4File.tags[atom] = self._encodeStandardValue(fieldName, value)
            else:
                freeformKey = f"{FREEFORM_PREFIX}{fieldName}"
                mp4File.tags[freeformKey] = [MP4FreeForm(str(value).encode("utf-8"))]

        mp4File.save()

    @staticmethod
    def _mapFreeformFieldName(key: str) -> str:
        if key.startswith(FREEFORM_PREFIX):
            return key[len(FREEFORM_PREFIX) :]
        return key

    def _normaliseTagValue(self, value: object) -> object:
        if isinstance(value, list):
            if len(value) == 1:
                return self._normaliseSingleValue(value[0])
            return [self._normaliseSingleValue(item) for item in value]
        return self._normaliseSingleValue(value)

    def _normaliseSingleValue(self, value: object) -> object:
        if isinstance(value, MP4FreeForm):
            return bytes(value).decode("utf-8", errors="replace").strip("\x00")
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").strip("\x00")
        if isinstance(value, tuple):
            return [self._normaliseSingleValue(item) for item in value]
        return value

    @staticmethod
    def _encodeStandardValue(fieldName: str, value: object) -> list[object]:
        if fieldName in {"season", "episode"}:
            return [int(value)]
        return [str(value)]


class MatchParser:
    """Parse match titles and scores from free-text strings."""

    TITLE_PATTERN = re.compile(
        r"^(?P<home>.+?)\s+(?:vs\.?|v)\s+(?P<away>.+?)$", re.IGNORECASE
    )
    SCORE_PATTERN = re.compile(r"^(?P<home>\d{1,3})\s*[-:]\s*(?P<away>\d{1,3})$")

    def parseTitle(self, title: str | None) -> tuple[str | None, str | None]:
        if not title:
            return None, None
        cleaned = self._cleanTitle(title)
        match = self.TITLE_PATTERN.match(cleaned)
        if not match:
            return None, None
        return match.group("home").strip(), match.group("away").strip()

    def parseScore(self, scoreText: str | None) -> tuple[int | None, int | None]:
        if not scoreText:
            return None, None
        match = self.SCORE_PATTERN.match(scoreText.strip())
        if not match:
            return None, None
        return int(match.group("home")), int(match.group("away"))

    def determineWinner(
        self,
        homeTeam: str | None,
        awayTeam: str | None,
        homeScore: int | None,
        awayScore: int | None,
    ) -> str | None:
        if homeScore is None or awayScore is None:
            return None
        if homeScore > awayScore:
            return homeTeam
        if awayScore > homeScore:
            return awayTeam
        return "draw"

    @staticmethod
    def _cleanTitle(title: str) -> str:
        text = title.strip()
        text = re.sub(r"\s+", " ", text)
        return text


class InteractivePrompter:
    """Prompt the user for match metadata values and optionally play the video."""

    def __init__(self) -> None:
        self.playerPath = self._findPlayer()

    def prompt(
        self, label: str, default: str | None = None, filePath: Path | None = None
    ) -> str | None:
        while True:
            if default is None:
                promptText = f"{label} [enter=blank, q=quit, p=play]: "
            else:
                promptText = f"{label} [{default}] (enter=accept, q=quit, p=play): "

            response = input(promptText)
            stripped = response.strip().lower()

            if stripped == "q":
                raise UserQuitRequested()

            if stripped == "p":
                self.playVideo(filePath)
                continue

            if response == "":
                return default

            return response.strip()

    def playVideo(self, filePath: Path | None) -> None:
        if filePath is None:
            logger.info("...no file available to play")
            return
        if self.playerPath is None:
            logger.info("...no supported video player found on PATH")
            return

        try:
            subprocess.run([self.playerPath, str(filePath)], check=False)
        except Exception as exc:
            logger.warning("...failed to play video: %s | %s", filePath, exc)

    @staticmethod
    def _findPlayer() -> str | None:
        for candidate in ("mpv", "vlc", "xdg-open"):
            path = shutil.which(candidate)
            if path:
                return path
        return None


class UserQuitRequested(Exception):
    """Raised when the user chooses to quit the interactive session."""


def configureLogging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO, format="%(message)s"
    )


def parseArgs(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Interactively audit and tag rugby match videos."
    )
    parser.add_argument("--source", required=True, help="root folder to scan")
    parser.add_argument(
        "--confirm",
        dest="confirm",
        action="store_true",
        help="execute changes — write metadata back to files (default is dry-run)",
    )
    parser.add_argument(
        "--outputCsv", default="mp4_match_prompt_audit.csv", help="CSV report path"
    )
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    return parser.parse_args(argv)


def iterMediaFiles(inputRoot: Path) -> Iterable[Path]:
    for filePath in sorted(inputRoot.rglob("*")):
        if filePath.is_file() and filePath.suffix.lower() in SUPPORTED_SUFFIXES:
            yield filePath


def determineSeasonInfo(filePath: Path, inputRoot: Path) -> SeasonInfo | None:
    try:
        relativePath = filePath.relative_to(inputRoot)
    except ValueError:
        relativePath = filePath

    if not relativePath.parts:
        return None

    folderName = relativePath.parts[0]
    if not re.fullmatch(r"\d{4}", folderName):
        return None

    startYear = int(folderName)
    endYear = startYear + 1
    return SeasonInfo(
        seasonKey=startYear,
        seasonLabel=f"{startYear}/{str(endYear)[-2:]}",
        seasonStartYear=startYear,
        seasonEndYear=endYear,
    )


def buildSeasonEpisodes(inputRoot: Path) -> dict[Path, int]:
    seasonBuckets: dict[str, list[Path]] = {}
    for filePath in iterMediaFiles(inputRoot):
        try:
            relativePath = filePath.relative_to(inputRoot)
            seasonKey = relativePath.parts[0]
        except Exception:
            seasonKey = "unknown"
        seasonBuckets.setdefault(seasonKey, []).append(filePath)

    result: dict[Path, int] = {}
    for _, files in seasonBuckets.items():
        for index, filePath in enumerate(sorted(files), start=1):
            result[filePath] = index
    return result


def getDefaultText(tags: dict[str, object], fieldName: str) -> str | None:
    value = tags.get(fieldName)
    if value is None:
        return None
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


def promptForFile(
    filePath: Path,
    inputRoot: Path,
    episodeMap: dict[Path, int],
    tagHelper: Mp4TagHelper,
    parser: MatchParser,
    prompter: InteractivePrompter,
    writeChanges: bool,
) -> dict[str, object]:
    tags = tagHelper.readTags(filePath)
    seasonInfo = determineSeasonInfo(filePath, inputRoot)
    episode = episodeMap.get(filePath)

    defaultTitle = getDefaultText(tags, "title")
    defaultComment = getDefaultText(tags, "comment")

    logger.info("")
    logger.info("...file: %s", filePath)
    if seasonInfo:
        logger.info("...season: %s", seasonInfo.seasonLabel)
    if episode is not None:
        logger.info("...episode: %s", episode)
    logger.info("...score: %s", defaultComment or "")

    if defaultComment:
        logger.info("...skipping file with existing score")
        title = defaultTitle
        comment = defaultComment
    else:
        homeTeam = prompter.prompt("home team", None, filePath=filePath)
        if homeTeam == "g":
            homeTeam = "Gloucester-Hartpury"

        awayTeam = prompter.prompt("away team", None, filePath=filePath)
        if awayTeam == "g":
            awayTeam = "Gloucester-Hartpury"

        title = None
        if homeTeam and awayTeam:
            title = f"{homeTeam} vs. {awayTeam}"

        comment = prompter.prompt("score/comment", defaultComment, filePath=filePath)

    if title is None:
        title = defaultTitle
    if comment is None:
        comment = defaultComment

    homeTeam, awayTeam = parser.parseTitle(title)

    # enforce canonical title format
    if homeTeam and awayTeam:
        title = f"{homeTeam} vs. {awayTeam}"
    homeScore, awayScore = parser.parseScore(comment)
    winner = parser.determineWinner(homeTeam, awayTeam, homeScore, awayScore)

    valuesToWrite: dict[str, object] = {
        "artist": "Gloucester-Hartpury",  # fixed per user rule
        "title": title or "",
        "comment": comment or "",
        "season": seasonInfo.seasonKey if seasonInfo else "",
        "episode": episode or "",
        "seasonLabel": seasonInfo.seasonLabel if seasonInfo else "",
        "seasonStartYear": seasonInfo.seasonStartYear if seasonInfo else "",
        "seasonEndYear": seasonInfo.seasonEndYear if seasonInfo else "",
        "homeTeam": homeTeam or "",
        "awayTeam": awayTeam or "",
        "homeScore": homeScore if homeScore is not None else "",
        "awayScore": awayScore if awayScore is not None else "",
        "winner": winner or "",
    }

    if writeChanges:
        tagHelper.writeTags(filePath, valuesToWrite)
        logger.info("...updated tags")
    else:
        logger.info("...dry run values prepared")

    return {
        "filePath": str(filePath),
        "seasonKey": seasonInfo.seasonKey if seasonInfo else "",
        "seasonLabel": seasonInfo.seasonLabel if seasonInfo else "",
        "episode": episode or "",
        "title": title or "",
        "comment": comment or "",
        "homeTeam": homeTeam or "",
        "awayTeam": awayTeam or "",
        "homeScore": homeScore if homeScore is not None else "",
        "awayScore": awayScore if awayScore is not None else "",
        "winner": winner or "",
        "writeMode": "write" if writeChanges else "dry-run",
    }


def writeCsv(outputPath: Path, rows: list[dict[str, object]]) -> None:
    fieldNames = [
        "filePath",
        "seasonKey",
        "seasonLabel",
        "episode",
        "title",
        "comment",
        "homeTeam",
        "awayTeam",
        "homeScore",
        "awayScore",
        "winner",
        "writeMode",
    ]

    with outputPath.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldNames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parseArgs(argv or sys.argv[1:])
    configureLogging(args.verbose)
    dryRun = not args.confirm

    inputRoot = Path(args.source).expanduser().resolve()
    if not inputRoot.exists() or not inputRoot.is_dir():
        logger.error("Input folder is invalid: %s", inputRoot)
        return 2

    tagHelper = Mp4TagHelper()
    parser = MatchParser()
    prompter = InteractivePrompter()
    episodeMap = buildSeasonEpisodes(inputRoot)

    rows: list[dict[str, object]] = []
    try:
        for filePath in iterMediaFiles(inputRoot):
            rows.append(
                promptForFile(
                    filePath=filePath,
                    inputRoot=inputRoot,
                    episodeMap=episodeMap,
                    tagHelper=tagHelper,
                    parser=parser,
                    prompter=prompter,
                    writeChanges=not dryRun,
                )
            )
    except UserQuitRequested:
        logger.info("...user requested quit")

    outputCsv = Path(args.outputCsv).expanduser().resolve()
    writeCsv(outputCsv, rows)

    logger.info("")
    logger.info("...files processed: %s", len(rows))
    logger.info("...csv report: %s", outputCsv)
    logger.info("...mode: %s", "write" if not dryRun else "dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
