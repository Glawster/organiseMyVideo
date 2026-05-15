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

User interaction rule (team picker)
- up/down arrows (or j/k when not filtering) navigate the team list
- typing any character filters the list to matching team names
- pressing Enter selects the highlighted team, or submits the typed text as a new name
- pressing Escape skips the field (leaves it blank)
- pressing g (when not filtering) instantly selects Gloucester-Hartpury
- pressing q (when not filtering) quits the session
- pressing Backspace removes the last filter character

User interaction rule (score/comment prompt)
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
- the team list is built automatically from existing title tags before
  the interactive loop starts; new names entered during the session are
  added to the list immediately

Dependencies
    pip install mutagen
"""

from __future__ import annotations

import argparse
import csv
import curses
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
class FileContext:
    """Context shown in the curses info panel while picking team names.

    All fields are optional so the panel degrades gracefully when info
    is not yet available (e.g. picking the home team before the away
    team is known).
    """

    filePath: Path | None = None
    seasonLabel: str | None = None
    episode: int | None = None
    existingTitle: str | None = None
    existingScore: str | None = None
    homeTeam: str | None = None


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
            logger.warning("failed to read tags: %s | %s", filePath, exc)
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
            logger.info("no file available to play")
            return
        if self.playerPath is None:
            logger.info("no supported video player found on PATH")
            return

        try:
            subprocess.run([self.playerPath, str(filePath)], check=False)
        except Exception as exc:
            logger.warning("failed to play video: %s | %s", filePath, exc)

    @staticmethod
    def _findPlayer() -> str | None:
        for candidate in ("mpv", "vlc", "xdg-open"):
            path = shutil.which(candidate)
            if path:
                return path
        return None


class UserQuitRequested(Exception):
    """Raised when the user chooses to quit the interactive session."""


class TeamPicker:
    """Curses-based interactive team picker with a plain-text numbered fallback.

    Usage::

        picker = TeamPicker()
        team = picker.pick("Home team", knownTeams)
    """

    GLOUCESTER = "Gloucester-Hartpury"

    def pick(
        self,
        label: str,
        knownTeams: list[str],
        context: FileContext | None = None,
        default: str | None = None,
    ) -> str | None:
        """Return a team name chosen interactively.

        Tries a full-screen curses picker first.  Falls back to a numbered
        plain-text list when curses is unavailable (e.g. no TTY).

        *context* is displayed in an info panel at the top of the curses
        window showing the current file, season, episode, existing title,
        score, and already-chosen home team.

        *default* pre-positions the cursor on the matching entry so the user
        can accept it immediately by pressing Enter.

        - Raises *UserQuitRequested* if the user presses ``q``.
        - Returns ``None`` if the user presses Escape (skip / leave blank).
        - Appends any new name to *knownTeams* (sorted in place) so that
          subsequent calls benefit from it immediately.
        """
        try:
            return curses.wrapper(self._cursesPick, label, knownTeams, context, default)
        except UserQuitRequested:
            raise
        except Exception as exc:
            logger.debug("curses picker unavailable (%s), using text fallback", exc)
            return self._fallbackPick(label, knownTeams, context, default)

    # ------------------------------------------------------------------
    # Curses implementation
    # ------------------------------------------------------------------

    def _cursesPick(
        self,
        stdscr,
        label: str,
        knownTeams: list[str],
        context: FileContext | None,
        default: str | None,
    ) -> str | None:

        curses.curs_set(0)
        try:
            curses.use_default_colors()
        except curses.error:
            pass

        # Pre-position the cursor on the default team when one is supplied.
        if default:
            lower = default.casefold()
            defaultIdx = next(
                (i for i, t in enumerate(knownTeams) if t.casefold() == lower), 0
            )
        else:
            defaultIdx = 0

        selected = defaultIdx
        filterText = ""

        while True:
            if filterText:
                filtered = [t for t in knownTeams if filterText.lower() in t.lower()]
            else:
                filtered = list(knownTeams)

            if filtered:
                selected = max(0, min(selected, len(filtered) - 1))

            stdscr.erase()
            height, width = stdscr.getmaxyx()

            # ----------------------------------------------------------
            # Info panel
            # ----------------------------------------------------------
            panelLines = self._buildInfoLines(context, width)
            for row, line in enumerate(panelLines):
                self._addstrSafe(stdscr, row, 0, line, width)
            panelHeight = len(panelLines)

            # Separator after panel
            sepAfterPanel = panelHeight
            self._addstrSafe(stdscr, sepAfterPanel, 0, "-" * (width - 1), width)

            # Label and filter bar
            labelRow = sepAfterPanel + 1
            filterRow = labelRow + 1
            self._addstrSafe(stdscr, labelRow, 0, f"{label}:", width)
            self._addstrSafe(stdscr, filterRow, 0, f"  Filter: {filterText}", width)
            self._addstrSafe(stdscr, filterRow + 1, 0, "-" * (width - 1), width)

            listTop = filterRow + 2
            statusRows = 2
            listHeight = max(1, height - listTop - statusRows)

            # Team list
            if filtered:
                scrollOffset = max(0, selected - listHeight // 2)
                scrollOffset = min(scrollOffset, max(0, len(filtered) - listHeight))
                for i in range(listHeight):
                    idx = scrollOffset + i
                    if idx >= len(filtered):
                        break
                    rowY = listTop + i
                    if rowY >= height - statusRows:
                        break
                    text = f"  {filtered[idx]}"
                    if idx == selected:
                        stdscr.attron(curses.A_REVERSE)
                        self._addstrSafe(stdscr, rowY, 0, text, width)
                        stdscr.attroff(curses.A_REVERSE)
                    else:
                        self._addstrSafe(stdscr, rowY, 0, text, width)
            else:
                if filterText:
                    msg = f"  (no matches - press Enter to use '{filterText}')"
                else:
                    msg = "  (no teams known yet - type a name and press Enter)"
                self._addstrSafe(stdscr, listTop, 0, msg, width)

            # Status bar
            sepRow = height - statusRows
            if sepRow >= 0:
                self._addstrSafe(stdscr, sepRow, 0, "-" * (width - 1), width)
            if filterText:
                hint = "up/down navigate  Enter=select/new  Backspace=clear  Esc=skip"
            else:
                hint = "up/down/jk navigate  g=Gloucester  Esc=skip  q=quit  type to filter"
            self._addstrSafe(stdscr, height - 1, 0, hint, width)

            stdscr.refresh()
            key = stdscr.getch()

            # Universal navigation
            if key == curses.KEY_UP and filtered:
                selected = max(0, selected - 1)
            elif key == curses.KEY_DOWN and filtered:
                selected = min(len(filtered) - 1, selected + 1)
            # Enter: select highlighted, submit typed text, or skip
            elif key in (curses.KEY_ENTER, 10, 13):
                if filtered:
                    result = filtered[selected]
                elif filterText:
                    result = filterText
                else:
                    result = None
                if result:
                    self._addToKnownTeams(result, knownTeams)
                return result
            # Backspace removes last filter character
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                filterText = filterText[:-1]
                selected = 0
            # Escape skips the field
            elif key == 27:
                return None
            # Browse-mode shortcuts (only when no filter text is active)
            elif key == ord("g") and not filterText:
                self._addToKnownTeams(self.GLOUCESTER, knownTeams)
                return self.GLOUCESTER
            elif key == ord("q") and not filterText:
                raise UserQuitRequested()
            elif key == ord("j") and not filterText and filtered:
                selected = min(len(filtered) - 1, selected + 1)
            elif key == ord("k") and not filterText and filtered:
                selected = max(0, selected - 1)
            # Any printable character extends the filter
            elif 32 <= key <= 126:
                filterText += chr(key)
                selected = 0

    @staticmethod
    def _buildInfoLines(context: FileContext | None, width: int) -> list[str]:
        """Return a list of fixed-width strings for the info panel.

        Always returns at least one line so the panel separator is visible.
        Each field is shown only when it contains useful data.
        """
        if context is None:
            return [" (no file context)"]

        lines: list[str] = []

        if context.filePath is not None:
            fileName = context.filePath.name
            lines.append(f" File   : {fileName}"[: width - 1])

        parts: list[str] = []
        if context.seasonLabel:
            parts.append(f"Season: {context.seasonLabel}")
        if context.episode is not None:
            parts.append(f"Ep: {context.episode}")
        if parts:
            lines.append(f" {('   '.join(parts))}"[: width - 1])

        if context.existingTitle:
            lines.append(f" Title  : {context.existingTitle}"[: width - 1])

        score = context.existingScore or "(none)"
        lines.append(f" Score  : {score}"[: width - 1])

        if context.homeTeam:
            lines.append(f" Home   : {context.homeTeam}"[: width - 1])

        return lines if lines else [" (no file context)"]

    @staticmethod
    def _addstrSafe(stdscr, y: int, x: int, text: str, width: int) -> None:
        """Write *text* at (*y*, *x*) clipped to *width*, ignoring boundary errors."""
        try:
            stdscr.addstr(y, x, text[: max(0, width - x)])
        except curses.error:
            pass

    @staticmethod
    def _addToKnownTeams(name: str, knownTeams: list[str]) -> None:
        """Add *name* to *knownTeams* if not already present, keeping it sorted."""
        if name not in knownTeams:
            knownTeams.append(name)
            knownTeams.sort(key=str.casefold)

    # ------------------------------------------------------------------
    # Plain-text fallback
    # ------------------------------------------------------------------

    def _fallbackPick(
        self,
        label: str,
        knownTeams: list[str],
        context: FileContext | None = None,
        default: str | None = None,
    ) -> str | None:
        """Numbered plain-text list used when curses is unavailable."""
        if context is not None:
            infoLines = self._buildInfoLines(context, width=72)
            print("\n" + "\n".join(infoLines))

        if knownTeams:
            print(f"\n{label}:")
            for i, team in enumerate(knownTeams, start=1):
                marker = (
                    " *" if default and team.casefold() == default.casefold() else ""
                )
                print(f"  {i:2}. {team}{marker}")
            print()

        defaultHint = f" Enter={default}" if default else " Enter=skip"
        while True:
            prompt = f"{label} [number, new name, g=Gloucester, q=quit,{defaultHint}]: "
            response = input(prompt).strip()
            if not response:
                if default:
                    self._addToKnownTeams(default, knownTeams)
                    return default
                return None
            if response.lower() == "q":
                raise UserQuitRequested()
            if response.lower() == "g":
                self._addToKnownTeams(self.GLOUCESTER, knownTeams)
                return self.GLOUCESTER
            if response.isdigit():
                idx = int(response) - 1
                if 0 <= idx < len(knownTeams):
                    return knownTeams[idx]
                print(f"  invalid number, choose 1-{len(knownTeams)}")
                continue
            self._addToKnownTeams(response, knownTeams)
            return response


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


# Trailing noise that occasionally contaminates team names extracted from file
# titles (e.g. "Bristol Bears SF", "Gloucester-Hartpury Full Match Allianz…").
# The pattern is anchored to the end of the string and applied repeatedly until
# no further match is found, so stacked suffixes are stripped cleanly.
_TEAM_NOISE_RE = re.compile(
    r"\s+(?:SF|Final|Full\s+Match\b.*|Allianz\b.*)$",
    re.IGNORECASE,
)


def _cleanTeamName(name: str) -> str:
    """Strip known trailing noise from a raw team name extracted from a title tag.

    Applies *_TEAM_NOISE_RE* repeatedly until the name stabilises, so that
    compound suffixes such as "Full Match Allianz Premi-01" are fully removed
    in one call.
    """
    while True:
        cleaned = _TEAM_NOISE_RE.sub("", name).strip()
        if cleaned == name:
            return cleaned
        name = cleaned


def buildKnownTeams(
    inputRoot: Path, tagHelper: Mp4TagHelper, parser: MatchParser
) -> list[str]:
    """Pre-scan media files and extract unique team names from existing title tags.

    Returns a case-insensitively sorted list of distinct team names found in
    the ``title`` atoms of all media files under *inputRoot*.  Known trailing
    noise (e.g. "SF", "Final", "Full Match …") is stripped before the name is
    added to the list.
    """
    teamSet: set[str] = set()
    for filePath in iterMediaFiles(inputRoot):
        tags = tagHelper.readTags(filePath)
        title = getDefaultText(tags, "title")
        homeTeam, awayTeam = parser.parseTitle(title)
        if homeTeam:
            teamSet.add(_cleanTeamName(homeTeam.strip()))
        if awayTeam:
            teamSet.add(_cleanTeamName(awayTeam.strip()))
    return sorted(teamSet, key=str.casefold)


def promptForFile(
    filePath: Path,
    inputRoot: Path,
    episodeMap: dict[Path, int],
    tagHelper: Mp4TagHelper,
    parser: MatchParser,
    prompter: InteractivePrompter,
    teamPicker: TeamPicker,
    knownTeams: list[str],
    writeChanges: bool,
) -> dict[str, object]:
    tags = tagHelper.readTags(filePath)
    seasonInfo = determineSeasonInfo(filePath, inputRoot)
    episode = episodeMap.get(filePath)

    defaultTitle = getDefaultText(tags, "title")
    defaultComment = getDefaultText(tags, "comment")

    logger.info("")
    logger.info("file: %s", filePath)
    if seasonInfo:
        logger.info("season: %s", seasonInfo.seasonLabel)
    if episode is not None:
        logger.info("episode: %s", episode)
    logger.info("score: %s", defaultComment or "")

    if defaultComment:
        logger.info("skipping file with existing score")
        title = defaultTitle
        comment = defaultComment
    else:
        # Derive default team names from the filename stem so the picker can
        # pre-position the cursor and the user can simply press Enter.
        fileHomeTeam, fileAwayTeam = parser.parseTitle(filePath.stem)
        if fileHomeTeam:
            fileHomeTeam = _cleanTeamName(fileHomeTeam)
        if fileAwayTeam:
            fileAwayTeam = _cleanTeamName(fileAwayTeam)

        baseContext = FileContext(
            filePath=filePath,
            seasonLabel=seasonInfo.seasonLabel if seasonInfo else None,
            episode=episode,
            existingTitle=defaultTitle,
            existingScore=defaultComment,
        )
        homeTeam = teamPicker.pick(
            "Home team", knownTeams, context=baseContext, default=fileHomeTeam
        )
        awayContext = FileContext(
            filePath=filePath,
            seasonLabel=seasonInfo.seasonLabel if seasonInfo else None,
            episode=episode,
            existingTitle=defaultTitle,
            existingScore=defaultComment,
            homeTeam=homeTeam,
        )
        awayTeam = teamPicker.pick(
            "Away team", knownTeams, context=awayContext, default=fileAwayTeam
        )

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
        logger.info("updated tags")
    else:
        logger.info("dry run values prepared")

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
    teamPicker = TeamPicker()
    episodeMap = buildSeasonEpisodes(inputRoot)

    logger.info("building known teams from existing tags")
    knownTeams = buildKnownTeams(inputRoot, tagHelper, parser)
    logger.info("found %d known team(s)", len(knownTeams))

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
                    teamPicker=teamPicker,
                    knownTeams=knownTeams,
                    writeChanges=not dryRun,
                )
            )
    except UserQuitRequested:
        logger.info("user requested quit")

    outputCsv = Path(args.outputCsv).expanduser().resolve()
    writeCsv(outputCsv, rows)

    logger.info("")
    logger.info("files processed: %s", len(rows))
    logger.info("csv report: %s", outputCsv)
    logger.info("mode: %s", "write" if not dryRun else "dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
