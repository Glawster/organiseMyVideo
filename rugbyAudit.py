#!/usr/bin/env python3
"""Audit MP4 rugby match files by comparing filename-derived data with MP4 tags.

Features
- scans a folder recursively for MP4/M4V/MOV files
- extracts match data from filenames where possible
- reads MP4/iTunes-style tags using mutagen
- optionally runs ffprobe for container/stream details
- compares filename-derived values with tag values
- writes a CSV audit report and a JSON detail report

Suggested filename pattern
    YYYY-MM-DD - Home Team vs Away Team - 33-31.mp4

Also supports looser variants such as:
    Gloucester-Hartpury vs Ealing Trailfinders 33-31.mp4
    2025-01-18 Gloucester-Hartpury v Ealing Trailfinders 33-31.mp4

Dependencies
    pip install mutagen

Optional
    ffprobe from FFmpeg on PATH
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from mutagen.mp4 import MP4, MP4FreeForm  # type: ignore


LOGGER = logging.getLogger("mp4MatchAudit")
SUPPORTED_SUFFIXES = {".mp4", ".m4v", ".mov"}
FREEFORM_PREFIX = "----:com.apple.iTunes:"

# Common MP4/iTunes atoms that are likely useful for sports match cataloguing.
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


@dataclass
class FilenameMatchData:
    sourceStem: str
    matchDate: str | None = None
    homeTeam: str | None = None
    awayTeam: str | None = None
    homeScore: int | None = None
    awayScore: int | None = None
    title: str | None = None
    winner: str | None = None
    parsePattern: str | None = None


@dataclass
class AuditIssue:
    field: str
    severity: str
    filenameValue: str | None = None
    tagValue: str | None = None
    message: str = ""


@dataclass
class FileAudit:
    filePath: str
    fileName: str
    suffix: str
    sizeBytes: int
    modifiedUtc: str
    filenameData: FilenameMatchData
    tags: dict[str, Any] = field(default_factory=dict)
    ffprobe: dict[str, Any] | None = None
    issues: list[AuditIssue] = field(default_factory=list)

    @property
    def issueCount(self) -> int:
        return len(self.issues)

    @property
    def status(self) -> str:
        return "ok" if not self.issues else "issues"


@dataclass
class Summary:
    scannedFiles: int = 0
    parsedFilenames: int = 0
    filesWithTags: int = 0
    filesWithIssues: int = 0
    filesWithoutTags: int = 0
    filesWithFfprobe: int = 0


class MatchFilenameParser:
    """Extract structured match data from fairly loose sports-video filenames."""

    def __init__(self) -> None:
        team_expr = r"(?P<home>.+?)\s+(?:vs|v)\s+(?P<away>.+?)"
        score_expr = r"(?P<homeScore>\d{1,3})\s*[-_]\s*(?P<awayScore>\d{1,3})"
        date_expr = r"(?P<date>\d{4}-\d{2}-\d{2})"

        self.patterns: list[tuple[str, re.Pattern[str]]] = [
            (
                "date-team-score-dashed",
                re.compile(
                    rf"^{date_expr}\s*[-–—]\s*{team_expr}\s*[-–—]\s*{score_expr}$",
                    re.IGNORECASE,
                ),
            ),
            (
                "date-team-score-spaced",
                re.compile(
                    rf"^{date_expr}\s+{team_expr}\s+{score_expr}$",
                    re.IGNORECASE,
                ),
            ),
            (
                "team-score",
                re.compile(rf"^{team_expr}\s+{score_expr}$", re.IGNORECASE),
            ),
            (
                "date-team",
                re.compile(
                    rf"^{date_expr}\s*[-–—]?\s*{team_expr}$",
                    re.IGNORECASE,
                ),
            ),
            (
                "team-only",
                re.compile(rf"^{team_expr}$", re.IGNORECASE),
            ),
        ]

    def parse(self, filePath: Path) -> FilenameMatchData:
        stem = self._normaliseStem(filePath.stem)
        for patternName, pattern in self.patterns:
            match = pattern.match(stem)
            if not match:
                continue

            groups = match.groupdict()
            homeTeam = self._cleanTeam(groups.get("home"))
            awayTeam = self._cleanTeam(groups.get("away"))
            matchDate = self._normaliseDate(groups.get("date"))
            homeScore = self._toInt(groups.get("homeScore"))
            awayScore = self._toInt(groups.get("awayScore"))

            winner = None
            if homeScore is not None and awayScore is not None and homeTeam and awayTeam:
                if homeScore > awayScore:
                    winner = homeTeam
                elif awayScore > homeScore:
                    winner = awayTeam
                else:
                    winner = "draw"

            title = None
            if homeTeam and awayTeam:
                title = f"{homeTeam} vs {awayTeam}"

            return FilenameMatchData(
                sourceStem=filePath.stem,
                matchDate=matchDate,
                homeTeam=homeTeam,
                awayTeam=awayTeam,
                homeScore=homeScore,
                awayScore=awayScore,
                title=title,
                winner=winner,
                parsePattern=patternName,
            )

        return FilenameMatchData(sourceStem=filePath.stem)

    @staticmethod
    def _normaliseStem(stem: str) -> str:
        text = stem.replace("_", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _cleanTeam(value: str | None) -> str | None:
        if not value:
            return None
        value = re.sub(r"\s+", " ", value).strip(" -–—")
        return value.strip() or None

    @staticmethod
    def _toInt(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _normaliseDate(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return value


class Mp4TagReader:
    def readTags(self, filePath: Path) -> dict[str, Any]:
        try:
            mp4File = MP4(str(filePath))
        except Exception as exc:  # pragma: no cover - depends on file content
            LOGGER.warning("...failed to read mp4 tags: %s | %s", filePath, exc)
            return {"_readError": str(exc)}

        if mp4File.tags is None:
            return {}

        result: dict[str, Any] = {}
        for key, rawValue in mp4File.tags.items():
            fieldName = ATOM_TO_FIELD.get(key, self._mapFreeformFieldName(key))
            result[fieldName] = self._normaliseTagValue(rawValue)

        return result

    @staticmethod
    def _mapFreeformFieldName(key: str) -> str:
        if key.startswith(FREEFORM_PREFIX):
            return key[len(FREEFORM_PREFIX):]
        return key

    def _normaliseTagValue(self, value: Any) -> Any:
        if isinstance(value, list):
            if len(value) == 1:
                return self._normaliseSingleValue(value[0])
            return [self._normaliseSingleValue(item) for item in value]
        return self._normaliseSingleValue(value)

    def _normaliseSingleValue(self, value: Any) -> Any:
        if isinstance(value, MP4FreeForm):
            return self._decodeBytes(bytes(value))
        if isinstance(value, bytes):
            return self._decodeBytes(value)
        if isinstance(value, tuple):
            return [self._normaliseSingleValue(item) for item in value]
        return value

    @staticmethod
    def _decodeBytes(value: bytes) -> str:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return value.decode(encoding).strip("\x00")
            except UnicodeDecodeError:
                continue
        return value.hex()


class FfprobeReader:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.ffprobePath = shutil.which("ffprobe") if enabled else None

    def isAvailable(self) -> bool:
        return bool(self.ffprobePath)

    def read(self, filePath: Path) -> dict[str, Any] | None:
        if not self.ffprobePath:
            return None

        command = [
            self.ffprobePath,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(filePath),
        ]

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)
            return self._trimPayload(payload)
        except Exception as exc:  # pragma: no cover - depends on runtime tools
            LOGGER.warning("...ffprobe failed: %s | %s", filePath, exc)
            return {"_readError": str(exc)}

    @staticmethod
    def _trimPayload(payload: dict[str, Any]) -> dict[str, Any]:
        formatSection = payload.get("format", {})
        streams = payload.get("streams", [])
        videoStream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
        audioStream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})

        return {
            "formatName": formatSection.get("format_name"),
            "duration": formatSection.get("duration"),
            "bitRate": formatSection.get("bit_rate"),
            "probeTags": formatSection.get("tags", {}),
            "video": {
                "codec": videoStream.get("codec_name"),
                "width": videoStream.get("width"),
                "height": videoStream.get("height"),
                "avgFrameRate": videoStream.get("avg_frame_rate"),
            },
            "audio": {
                "codec": audioStream.get("codec_name"),
                "channels": audioStream.get("channels"),
                "sampleRate": audioStream.get("sample_rate"),
            },
        }


class AuditEngine:
    def __init__(self, includeFfprobe: bool) -> None:
        self.filenameParser = MatchFilenameParser()
        self.tagReader = Mp4TagReader()
        self.ffprobeReader = FfprobeReader(enabled=includeFfprobe)

    def auditFiles(self, inputRoot: Path) -> tuple[list[FileAudit], Summary]:
        audits: list[FileAudit] = []
        summary = Summary()

        for filePath in self._iterMediaFiles(inputRoot):
            summary.scannedFiles += 1
            audits.append(self._auditSingleFile(filePath, summary))

        summary.filesWithIssues = sum(1 for audit in audits if audit.issues)
        return audits, summary

    def _auditSingleFile(self, filePath: Path, summary: Summary) -> FileAudit:
        stat = filePath.stat()
        filenameData = self.filenameParser.parse(filePath)
        if filenameData.parsePattern:
            summary.parsedFilenames += 1

        tags = self.tagReader.readTags(filePath)
        if tags and "_readError" not in tags:
            summary.filesWithTags += 1
        else:
            summary.filesWithoutTags += 1

        ffprobeData = self.ffprobeReader.read(filePath)
        if ffprobeData and "_readError" not in ffprobeData:
            summary.filesWithFfprobe += 1

        audit = FileAudit(
            filePath=str(filePath),
            fileName=filePath.name,
            suffix=filePath.suffix.lower(),
            sizeBytes=stat.st_size,
            modifiedUtc=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            filenameData=filenameData,
            tags=tags,
            ffprobe=ffprobeData,
        )

        audit.issues.extend(self._compareFilenameToTags(filenameData, tags))
        return audit

    @staticmethod
    def _iterMediaFiles(inputRoot: Path) -> Iterable[Path]:
        for filePath in sorted(inputRoot.rglob("*")):
            if filePath.is_file() and filePath.suffix.lower() in SUPPORTED_SUFFIXES:
                yield filePath

    def _compareFilenameToTags(
        self,
        filenameData: FilenameMatchData,
        tags: dict[str, Any],
    ) -> list[AuditIssue]:
        issues: list[AuditIssue] = []

        checks = [
            ("title", filenameData.title, self._getTagText(tags, "title")),
            ("date", filenameData.matchDate, self._getTagText(tags, "date")),
            ("homeTeam", filenameData.homeTeam, self._getTagText(tags, "homeTeam")),
            ("awayTeam", filenameData.awayTeam, self._getTagText(tags, "awayTeam")),
            ("homeScore", self._toText(filenameData.homeScore), self._getTagText(tags, "homeScore")),
            ("awayScore", self._toText(filenameData.awayScore), self._getTagText(tags, "awayScore")),
            ("winner", filenameData.winner, self._getTagText(tags, "winner")),
        ]

        for fieldName, filenameValue, tagValue in checks:
            if filenameValue and not tagValue:
                issues.append(
                    AuditIssue(
                        field=fieldName,
                        severity="warning",
                        filenameValue=filenameValue,
                        tagValue=tagValue,
                        message="value found in filename but missing from tags",
                    )
                )
            elif filenameValue and tagValue and not self._equivalent(filenameValue, tagValue):
                issues.append(
                    AuditIssue(
                        field=fieldName,
                        severity="error",
                        filenameValue=filenameValue,
                        tagValue=tagValue,
                        message="filename value and tag value differ",
                    )
                )

        if not filenameData.parsePattern:
            issues.append(
                AuditIssue(
                    field="filename",
                    severity="warning",
                    message="filename did not match a known match pattern",
                )
            )

        if tags.get("_readError"):
            issues.append(
                AuditIssue(
                    field="tags",
                    severity="error",
                    tagValue=str(tags.get("_readError")),
                    message="failed to read tags",
                )
            )

        return issues

    @staticmethod
    def _getTagText(tags: dict[str, Any], fieldName: str) -> str | None:
        value = tags.get(fieldName)
        if value is None:
            return None
        if isinstance(value, list):
            return " | ".join(str(item) for item in value)
        return str(value)

    @staticmethod
    def _toText(value: Any) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def _equivalent(left: str, right: str) -> bool:
        return AuditEngine._normaliseCompare(left) == AuditEngine._normaliseCompare(right)

    @staticmethod
    def _normaliseCompare(value: str) -> str:
        value = value.strip().lower()
        value = value.replace("–", "-").replace("—", "-")
        value = re.sub(r"\s+", " ", value)
        return value


def configureLogging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def parseArgs(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit MP4 match files and tags.")
    parser.add_argument("inputRoot", help="root folder to scan")
    parser.add_argument(
        "--outputCsv",
        default="mp4_match_audit.csv",
        help="path to CSV report",
    )
    parser.add_argument(
        "--outputJson",
        default="mp4_match_audit.json",
        help="path to JSON detail report",
    )
    parser.add_argument(
        "--noFfprobe",
        action="store_true",
        help="skip ffprobe even if it is installed",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable debug logging",
    )
    return parser.parse_args(argv)


def writeCsv(outputPath: Path, audits: list[FileAudit]) -> None:
    fieldNames = [
        "filePath",
        "fileName",
        "status",
        "issueCount",
        "parsePattern",
        "matchDate",
        "homeTeam",
        "awayTeam",
        "homeScore",
        "awayScore",
        "winner",
        "tagTitle",
        "tagDate",
        "tagHomeTeam",
        "tagAwayTeam",
        "tagHomeScore",
        "tagAwayScore",
        "tagWinner",
        "issueSummary",
    ]

    with outputPath.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldNames)
        writer.writeheader()
        for audit in audits:
            writer.writerow(
                {
                    "filePath": audit.filePath,
                    "fileName": audit.fileName,
                    "status": audit.status,
                    "issueCount": audit.issueCount,
                    "parsePattern": audit.filenameData.parsePattern,
                    "matchDate": audit.filenameData.matchDate,
                    "homeTeam": audit.filenameData.homeTeam,
                    "awayTeam": audit.filenameData.awayTeam,
                    "homeScore": audit.filenameData.homeScore,
                    "awayScore": audit.filenameData.awayScore,
                    "winner": audit.filenameData.winner,
                    "tagTitle": audit.tags.get("title"),
                    "tagDate": audit.tags.get("date"),
                    "tagHomeTeam": audit.tags.get("homeTeam"),
                    "tagAwayTeam": audit.tags.get("awayTeam"),
                    "tagHomeScore": audit.tags.get("homeScore"),
                    "tagAwayScore": audit.tags.get("awayScore"),
                    "tagWinner": audit.tags.get("winner"),
                    "issueSummary": " | ".join(issue.message for issue in audit.issues),
                }
            )


def writeJson(outputPath: Path, audits: list[FileAudit], summary: Summary) -> None:
    payload = {
        "generatedUtc": datetime.now(tz=timezone.utc).isoformat(),
        "summary": asdict(summary),
        "files": [
            {
                **asdict(audit),
                "status": audit.status,
                "issueCount": audit.issueCount,
            }
            for audit in audits
        ],
    }

    with outputPath.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    args = parseArgs(argv or sys.argv[1:])
    configureLogging(args.verbose)

    inputRoot = Path(args.inputRoot).expanduser().resolve()
    outputCsv = Path(args.outputCsv).expanduser().resolve()
    outputJson = Path(args.outputJson).expanduser().resolve()

    if not inputRoot.exists():
        LOGGER.error("Input folder does not exist: %s", inputRoot)
        return 2

    if not inputRoot.is_dir():
        LOGGER.error("Input path is not a directory: %s", inputRoot)
        return 2

    engine = AuditEngine(includeFfprobe=not args.noFfprobe)
    audits, summary = engine.auditFiles(inputRoot)

    writeCsv(outputCsv, audits)
    writeJson(outputJson, audits, summary)

    LOGGER.info("...scanned files: %s", summary.scannedFiles)
    LOGGER.info("...parsed filenames: %s", summary.parsedFilenames)
    LOGGER.info("...files with tags: %s", summary.filesWithTags)
    LOGGER.info("...files with issues: %s", summary.filesWithIssues)
    LOGGER.info("...csv report: %s", outputCsv)
    LOGGER.info("...json report: %s", outputJson)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
