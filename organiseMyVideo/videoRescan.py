"""TV rescan/reset workflows and duplicate-folder handling."""

from contextlib import contextmanager
import errno
import difflib
import json
import re
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional, TextIO

from .constants import APP_CONFIG_FILE, VIDEO_EXTENSIONS
from organiseMyProjects.logUtils import getLogger  # type: ignore

logger = getLogger()

_IGNORED_TV_SHOW_DUPLICATES_CONFIG_KEY = "ignored_tv_show_duplicates"
_SCAN_PROGRESS_BAR_WIDTH = 24


class _ResetScanProgress:
    """Single-line terminal progress display for movie/TV library scans."""

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
        progress = min(completed / self.total, 1.0) if self.total else 0.0
        filled = int(progress * _SCAN_PROGRESS_BAR_WIDTH)
        bar = "#" * filled + "-" * (_SCAN_PROGRESS_BAR_WIDTH - filled)
        totalText = str(self.total) if self.total else "?"
        prefix = (
            f"{self.label}: [{bar}] {progress * 100:3.0f}% "
            f"({completed}/{totalText})"
        )
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


class VideoRescanMixin:
    """Workflow methods for TV rescans and duplicate-folder repair."""

    @staticmethod
    def _filesystemSafeResetFallback(path: Path) -> Path:
        """Return a colon-free fallback name for filesystems that reject colons."""
        safeName = re.sub(r"\s*:\s*", " - ", path.name)
        safeName = re.sub(r"\s+", " ", safeName).strip()
        return path.with_name(safeName)

    @contextmanager
    def _suppressResetNoiseLogs(self):
        """Temporarily silence noisy info/action logging during reset scans."""
        from . import metadata as metadata_module
        from . import video as video_module

        targets = (logger, video_module.logger, metadata_module.logger)
        methodNames = ("doing", "done", "info", "value", "action")
        originals = {
            target: {name: getattr(target, name) for name in methodNames}
            for target in targets
        }

        try:
            for target in targets:
                for name in methodNames:
                    setattr(target, name, lambda *args, **kwargs: None)
            yield
        finally:
            for target, methods in originals.items():
                for name, method in methods.items():
                    setattr(target, name, method)

    @contextmanager
    def _suppressResetMetadataPreserveLogs(self):
        """Hide routine metadata preservation/creation noise during reset scans."""
        from . import metadata as metadata_module
        from . import video as video_module

        targets = (logger, video_module.logger, metadata_module.logger)
        originals = {
            target: {"value": target.value, "action": target.action}
            for target in targets
        }

        def _wrapValue(original):
            def _value(label, *args, **kwargs):
                if label in {
                    "preserving existing metadata",
                    "preserving existing metadata files",
                }:
                    return None
                return original(label, *args, **kwargs)

            return _value

        def _wrapAction(original):
            def _action(message, *args, **kwargs):
                if isinstance(message, str) and message.startswith(
                    ("create metadata", "update metadata")
                ):
                    return None
                return original(message, *args, **kwargs)

            return _action

        try:
            for target in targets:
                target.value = _wrapValue(target.value)
                target.action = _wrapAction(target.action)
            yield
        finally:
            for target, methods in originals.items():
                target.value = methods["value"]
                target.action = methods["action"]

    @contextmanager
    def _bufferResetItemLogs(self):
        """Buffer one scan item's meaningful logs until its progress completes."""
        from . import metadata as metadata_module
        from . import video as video_module

        targets = (logger, video_module.logger, metadata_module.logger)
        methodNames = ("action", "error", "warning", "multiline", "value", "info")
        originals = {
            target: {name: getattr(target, name) for name in methodNames}
            for target in targets
        }
        events = []

        def _capture(original):
            def _buffered(*args, **kwargs):
                events.append((original, args, kwargs))

            return _buffered

        try:
            for target in targets:
                for name in methodNames:
                    setattr(target, name, _capture(originals[target][name]))
            yield events
        finally:
            for target, methods in originals.items():
                for name, original in methods.items():
                    setattr(target, name, original)

    def _flushResetItemLogs(self, progress: _ResetScanProgress, events: list) -> None:
        """Finish the current progress line, then emit buffered item results."""
        if not events:
            return
        progress.finish()
        for original, args, kwargs in events:
            original(*args, **kwargs)

    def _resetTvShowMatchesFilter(
        self, showName: str, showFilter: Optional[str]
    ) -> bool:
        """Return True when *showName* matches the optional canonical show filter."""
        if not showFilter:
            return True
        targetKey = self._buildResetTvShowDuplicateKey(showFilter)
        return bool(
            targetKey and targetKey in self._buildResetTvShowDuplicateKey(showName)
        )

    def _resetTvShowFoldersResolve(
        self, videoDirs: list[Path], showFilter: str
    ) -> set[Path]:
        """Resolve physical and catalogue title matches once for a targeted scan."""
        from .mediaCatalogue import MediaCatalogue

        # Keep every matching path, including aliases sharing a canonical title.
        catalogueFolders = {
            Path(record.folderPath)
            for record in MediaCatalogue().catalogueTvSeriesList()
            if self._resetTvShowMatchesFilter(record.showName, showFilter)
        }
        return {
            showDir
            for tvDir in videoDirs
            for showDir in self._iterResetTvShowDirs(tvDir)
            if showDir in catalogueFolders
            or self._resetTvShowMatchesFilter(showDir.name, showFilter)
        }

    def _resetTvShowNeedsMetadataRepair(self, showDir: Path) -> bool:
        """Return True when show-level TV identity metadata is missing or unusable."""
        seriesFile = showDir / "series.xml"
        seriesRoot = self._readXmlRoot(seriesFile)
        if seriesRoot is None:
            return True
        seriesId = self._readFirstXmlText(seriesRoot, ("SeriesID", "seriesid", "id"))
        imdbId = self._readFirstXmlText(seriesRoot, ("IMDB_ID", "IMDbId"))
        if seriesId or imdbId:
            return False
        return self._readTvShowTopLevelSeriesId(showDir) is None

    def _iterResetSelectedTvShowFiles(
        self,
        tvDir: Path,
        *,
        showFilter: Optional[str] = None,
        deepScan: bool = True,
        selectedFolders: Optional[set[Path]] = None,
    ):
        """Yield only TV shows that require the requested level of scan work."""
        if selectedFolders is None and showFilter:
            selectedFolders = self._resetTvShowFoldersResolve([tvDir], showFilter)
        for showDir in self._iterResetTvShowDirs(tvDir):
            showName = showDir.name
            if selectedFolders is not None and showDir not in selectedFolders:
                continue
            if not deepScan and not self._resetTvShowNeedsMetadataRepair(showDir):
                continue
            videoFiles = [
                path
                for path in sorted(showDir.rglob("*"))
                if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
            ]
            if not videoFiles:
                continue
            seriesId = self._readResetTvShowSeriesId(showDir)
            yield showName, seriesId, videoFiles

    def _iterResetTvShowFiles(self, tvDir: Path):
        """Yield grouped reset candidates by top-level TV show folder."""
        showFiles = {}
        for videoFile in sorted(tvDir.rglob("*")):
            if (
                not videoFile.is_file()
                or videoFile.suffix.lower() not in VIDEO_EXTENSIONS
            ):
                continue
            relativePath = videoFile.relative_to(tvDir)
            showName = (
                relativePath.parts[0] if len(relativePath.parts) > 1 else tvDir.name
            )
            showFiles.setdefault(showName, []).append(videoFile)

        for showName, videoFiles in showFiles.items():
            showDir = tvDir / showName
            seriesId = (
                self._readResetTvShowSeriesId(showDir) if showDir.is_dir() else None
            )
            yield showName, seriesId, videoFiles

    def _iterResetMovieFiles(self, movieDir: Path):
        """Yield grouped reset candidates by stored movie folder."""
        try:
            entries = sorted(movieDir.iterdir(), key=lambda item: item.name.casefold())
        except OSError as error:
            logger.warning("could not inspect movie storage %s: %s", movieDir, error)
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            videoFiles = [
                videoFile
                for videoFile in sorted(entry.rglob("*"))
                if videoFile.is_file()
                and videoFile.suffix.lower() in VIDEO_EXTENSIONS
                and not self._isResetMovieSupplementalFile(entry, videoFile)
            ]
            if videoFiles:
                yield entry, videoFiles

    def _isResetMovieSupplementalFile(self, movieFolder: Path, videoFile: Path) -> bool:
        """Return True for extras/featurettes that should not drive movie rescans."""
        try:
            relativeParts = videoFile.relative_to(movieFolder).parts
        except ValueError:
            return False
        if len(relativeParts) <= 1:
            return False
        return any(
            part.casefold() in {"extras", "featurettes"} for part in relativeParts
        )

    def _iterResetTvShowDirs(self, tvDir: Path) -> Iterable[Path]:
        """Yield top-level TV show directories for reset scans."""
        try:
            showDirs = sorted(
                showDir for showDir in tvDir.iterdir() if showDir.is_dir()
            )
        except OSError as error:
            logger.warning("could not inspect TV storage %s: %s", tvDir, error)
            return
        yield from showDirs

    def _readResetTvShowSeriesId(self, showDir: Path) -> Optional[str]:
        """Return a show-level SeriesID for duplicate detection during rescans."""
        return self._readTvShowTopLevelSeriesId(showDir)

    def _buildResetDuplicateTvShowAnalysis(self, showEntries: list[dict]) -> dict:
        """Return duplicate-folder warning and merge data for *showEntries*."""
        showDirsBySeriesId = {}
        canonicalNameGroups = []
        canonicalNameGroupsByKey = {}
        entriesByShowName = {entry["showName"]: entry for entry in showEntries}
        allShowNames = {entry["showName"] for entry in showEntries}

        for entry in showEntries:
            showName = entry["showName"]
            canonicalName = self._stripResetTvShowDuplicateSuffixes(showName)
            duplicateKey = self._buildResetTvShowDuplicateKey(showName)
            group = self._findResetDuplicateCanonicalNameGroup(
                duplicateKey, canonicalNameGroups, canonicalNameGroupsByKey
            )
            if group is None:
                group = {
                    "key": duplicateKey,
                    "canonicalName": canonicalName,
                    "showNames": {showName},
                }
                canonicalNameGroups.append(group)
            else:
                group["showNames"].add(showName)
            canonicalNameGroupsByKey[duplicateKey] = group

        candidateGroups = [
            group["showNames"]
            for group in canonicalNameGroups
            if len(group["showNames"]) > 1
        ]
        for showNames in candidateGroups:
            for showName in showNames:
                entry = entriesByShowName.get(showName)
                if entry is None:
                    continue
                if "seriesId" not in entry:
                    entry["seriesId"] = self._readResetTvShowSeriesId(entry["showDir"])
                seriesId = entry.get("seriesId")
                if seriesId:
                    showDirsBySeriesId.setdefault(seriesId, set()).add(showName)
        candidateGroups.extend(
            showNames for showNames in showDirsBySeriesId.values() if len(showNames) > 1
        )
        adjacency = {showName: set() for showName in allShowNames}
        for group in candidateGroups:
            uniqueNames = set(group)
            for showName in uniqueNames:
                adjacency.setdefault(showName, set()).update(uniqueNames - {showName})

        duplicateGroups = []
        seen = set()
        for showName in self._sortResetDuplicateShowNames(allShowNames):
            if showName in seen or not adjacency.get(showName):
                continue
            stack = [showName]
            component = set()
            while stack:
                current = stack.pop()
                if current in component:
                    continue
                component.add(current)
                stack.extend(adjacency.get(current, ()))
            seen.update(component)
            if len(component) > 1:
                duplicateGroups.append(self._sortResetDuplicateShowNames(component))

        return {
            "showNamesBySeriesId": showDirsBySeriesId,
            "canonicalNameGroups": canonicalNameGroups,
            "duplicateGroups": duplicateGroups,
        }

    def _loadResetIgnoredDuplicateTvShowGroups(self) -> list[frozenset[str]]:
        """Return persisted duplicate-folder groups the user marked as non-duplicates."""
        cachedGroups = getattr(self, "_resetIgnoredDuplicateTvShowGroups", None)
        if cachedGroups is not None:
            return cachedGroups

        config = {}
        if APP_CONFIG_FILE.exists():
            try:
                loaded = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                logger.warning(
                    "could not read duplicate TV show config %s: %s",
                    APP_CONFIG_FILE,
                    error,
                )
            else:
                if isinstance(loaded, dict):
                    config = loaded

        ignoredGroups = []
        for item in config.get(_IGNORED_TV_SHOW_DUPLICATES_CONFIG_KEY, []):
            if not isinstance(item, list):
                continue
            cleanedGroup = {
                showName.strip()
                for showName in item
                if isinstance(showName, str) and showName.strip()
            }
            if len(cleanedGroup) < 2:
                continue
            ignoredGroups.append(frozenset(cleanedGroup))

        self._resetIgnoredDuplicateTvShowGroups = ignoredGroups
        return ignoredGroups

    def _saveResetIgnoredDuplicateTvShowGroups(
        self, ignoredGroups: list[frozenset[str]]
    ) -> None:
        """Persist duplicate-folder groups the user marked as non-duplicates."""
        config = {}
        if APP_CONFIG_FILE.exists():
            try:
                loaded = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                logger.warning(
                    "could not read duplicate TV show config %s: %s",
                    APP_CONFIG_FILE,
                    error,
                )
            else:
                if isinstance(loaded, dict):
                    config = loaded

        config[_IGNORED_TV_SHOW_DUPLICATES_CONFIG_KEY] = [
            self._sortResetDuplicateShowNames(group)
            for group in sorted(
                ignoredGroups,
                key=lambda group: self._sortResetDuplicateShowNames(group),
            )
        ]
        self.stateFilesystem.writeText(
            APP_CONFIG_FILE,
            json.dumps(config, indent=2, sort_keys=True),
            encoding="utf-8",
            stateKind="application-state",
        )
        self._resetIgnoredDuplicateTvShowGroups = ignoredGroups

    def _rememberResetDuplicateTvShowGroupIsNotDuplicate(
        self, showNames: Iterable[str]
    ) -> None:
        """Persist that the supplied duplicate-folder group should be ignored."""
        ignoredGroups = list(self._loadResetIgnoredDuplicateTvShowGroups())
        ignoredGroup = frozenset(self._sortResetDuplicateShowNames(showNames))
        if len(ignoredGroup) < 2 or ignoredGroup in ignoredGroups:
            return
        ignoredGroups.append(ignoredGroup)
        self._saveResetIgnoredDuplicateTvShowGroups(ignoredGroups)

    def _shouldIgnoreResetDuplicateTvShowGroup(self, showNames: Iterable[str]) -> bool:
        """Return True when the group was previously marked as not duplicate."""
        showNameSet = {
            showName.strip()
            for showName in showNames
            if isinstance(showName, str) and showName.strip()
        }
        if len(showNameSet) < 2:
            return False
        return any(
            showNameSet.issubset(ignoredGroup)
            for ignoredGroup in self._loadResetIgnoredDuplicateTvShowGroups()
        )

    def _filterIgnoredResetDuplicateTvShowGroups(
        self, duplicateGroups: Iterable[list[str]]
    ) -> list[list[str]]:
        """Drop duplicate-folder groups the user previously marked as valid."""
        return [
            group
            for group in duplicateGroups
            if not self._shouldIgnoreResetDuplicateTvShowGroup(group)
        ]

    def _logResetDuplicateTvShowWarnings(
        self, showDirsBySeriesId: dict, canonicalNameGroups: list[dict]
    ) -> None:
        """Log duplicate-folder warnings from precomputed analysis."""
        for warning in self._iterResetDuplicateTvShowWarnings(
            showDirsBySeriesId, canonicalNameGroups
        ):
            logger.multiline(
                [
                    warning["label"],
                    *warning["showNames"],
                ]
            )

    def _iterResetDuplicateTvShowWarnings(
        self, showDirsBySeriesId: dict, canonicalNameGroups: list[dict]
    ) -> Iterable[dict]:
        """Yield duplicate-folder warnings in display order."""
        for seriesId, showNames in sorted(showDirsBySeriesId.items()):
            uniqueShowNames = sorted(set(showNames), key=str.casefold)
            if len(uniqueShowNames) < 2:
                continue
            if self._shouldIgnoreResetDuplicateTvShowGroup(uniqueShowNames):
                continue
            yield {
                "label": f"possible duplicate TV show folders: {seriesId}",
                "showNames": uniqueShowNames,
            }

        for group in sorted(
            canonicalNameGroups, key=lambda item: item["canonicalName"].casefold()
        ):
            uniqueShowNames = sorted(set(group["showNames"]), key=str.casefold)
            if len(uniqueShowNames) < 2:
                continue
            if self._shouldIgnoreResetDuplicateTvShowGroup(uniqueShowNames):
                continue
            yield {
                "label": f"possible duplicate TV show folders: {group['canonicalName']}",
                "showNames": uniqueShowNames,
            }

    def _recordSummaryDuplicateTvShowWarnings(
        self, showDirsBySeriesId: dict, canonicalNameGroups: list[dict]
    ) -> None:
        """Capture duplicate-folder warnings for the optional summary report."""
        for warning in self._iterResetDuplicateTvShowWarnings(
            showDirsBySeriesId, canonicalNameGroups
        ):
            self._recordSummaryDuplicateTvShow(warning["label"], warning["showNames"])

    def _logResetDuplicateTvShowFolders(self, tvDir: Path) -> None:
        """Warn when multiple stored TV show folders look like duplicates."""
        showEntries = self._buildResetDuplicateTvShowEntries(tvDir)
        duplicateAnalysis = self._buildResetDuplicateTvShowAnalysis(showEntries)
        self._logResetDuplicateTvShowWarnings(
            duplicateAnalysis["showNamesBySeriesId"],
            duplicateAnalysis["canonicalNameGroups"],
        )

    def _buildResetDuplicateTvShowEntries(self, tvDir: Path) -> list[dict]:
        """Return top-level TV show entries for duplicate analysis and prompts."""
        return [
            {"showName": showDir.name, "showDir": showDir}
            for showDir in self._iterResetTvShowDirs(tvDir)
        ]

    def _shouldPromptInteractively(self) -> bool:
        """Return True when stdin/stdout are interactive enough for user prompts."""
        stdinIsTty = getattr(sys.stdin, "isatty", None)
        stdoutIsTty = getattr(sys.stdout, "isatty", None)
        stderrIsTty = getattr(sys.stderr, "isatty", None)
        return bool(
            callable(stdinIsTty)
            and stdinIsTty()
            and (
                (callable(stdoutIsTty) and stdoutIsTty())
                or (callable(stderrIsTty) and stderrIsTty())
            )
        )

    def _sortResetDuplicateShowNames(self, showNames: Iterable[str]) -> list[str]:
        """Return duplicate folder names ordered for merge prompts."""

        def _sortKey(showName: str) -> tuple[bool, int, str]:
            canonicalName = self._buildTvShowFolderName(showName)
            return (canonicalName != showName, len(showName), showName.casefold())

        return sorted(set(showNames), key=_sortKey)

    def _collectResetDuplicateTvShowGroups(
        self, showEntries: list[dict]
    ) -> list[list[str]]:
        """Return connected groups of possibly-duplicate TV show folders."""
        duplicateAnalysis = self._buildResetDuplicateTvShowAnalysis(showEntries)
        return self._filterIgnoredResetDuplicateTvShowGroups(
            duplicateAnalysis["duplicateGroups"]
        )

    def _promptResetDuplicateTvShowMerge(
        self, showNames: list[str]
    ) -> Optional[tuple[str, list[str]]]:
        """Ask whether duplicate TV show folders should be merged."""
        orderedShowNames = self._sortResetDuplicateShowNames(showNames)
        mergePrompt = "Merge these folders? (y/n/q): "
        shouldMerge = self._readMenuChoice(
            mergePrompt, validChoices={"y", "n", "q"}, defaultChoice="n"
        )
        if shouldMerge in {"q", "quit"}:
            logger.info("user requested to quit")
            sys.exit(0)
        if shouldMerge != "y":
            self._rememberResetDuplicateTvShowGroupIsNotDuplicate(orderedShowNames)
            return None

        selectionKeys = "123456789abcdefghijklmnopqrstuvwxyz"
        if len(orderedShowNames) > len(selectionKeys):
            defaultMaster = orderedShowNames[0]
            prompt = (
                "Enter the master TV show folder name exactly as shown "
                f"(default: {defaultMaster}): "
            )
            selectedMaster = self._readTextResponse(prompt).strip() or defaultMaster
            if selectedMaster not in orderedShowNames:
                logger.warning(
                    "skipping rescan merge; unknown master TV show folder: %s",
                    selectedMaster,
                )
                return None
            return selectedMaster, orderedShowNames

        choiceMap = dict(zip(selectionKeys, orderedShowNames))
        choiceLines = "\n".join(
            f"  {key}) {showName}" for key, showName in choiceMap.items()
        )
        defaultChoice = next(iter(choiceMap))
        choicePrompt = (
            "Choose the master TV show folder for the merged result:\n"
            f"{choiceLines}\n"
            f"Select master folder ({'/'.join(choiceMap)}): "
        )
        selectedChoice = self._readMenuChoice(
            choicePrompt,
            validChoices=set(choiceMap),
            defaultChoice=defaultChoice,
        )
        return choiceMap[selectedChoice], orderedShowNames

    @staticmethod
    def _formatResetTvShowMergeBytes(value: int) -> str:
        """Return a compact human-readable byte count for merge diagnostics."""
        size = float(max(value, 0))
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024.0 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def _resetTvShowMergeRequiredBytes(self, sourceDir: Path) -> int:
        """Return the total regular-file bytes below *sourceDir*."""
        total = 0
        try:
            paths = sourceDir.rglob("*")
            for path in paths:
                if path.is_file():
                    total += path.stat().st_size
        except OSError as error:
            logger.warning(
                "could not size TV show merge source %s: %s", sourceDir, error
            )
        return total

    def _resetTvShowMergeIsCrossFilesystem(
        self, sourceDir: Path, destinationDir: Path
    ) -> bool:
        """Return True when a merge must copy data between filesystems."""
        try:
            return sourceDir.stat().st_dev != destinationDir.stat().st_dev
        except OSError:
            return True

    def _resetTvShowMergeHasSufficientSpace(
        self, sourceDir: Path, destinationDir: Path
    ) -> bool:
        """Return whether a cross-filesystem merge fits on the destination."""
        if not self._resetTvShowMergeIsCrossFilesystem(sourceDir, destinationDir):
            return True

        requiredBytes = self._resetTvShowMergeRequiredBytes(sourceDir)
        try:
            freeBytes = shutil.disk_usage(destinationDir).free
        except OSError as error:
            logger.error(
                f"could not determine free space for TV merge destination "
                f"{destinationDir}: {error}"
            )
            return False

        if requiredBytes <= freeBytes:
            return True

        logger.error(
            f"not enough free space to merge TV show folders: "
            f"{sourceDir} requires {self._formatResetTvShowMergeBytes(requiredBytes)}; "
            f"{destinationDir} has {self._formatResetTvShowMergeBytes(freeBytes)} free"
)
        self._recordSummaryCleanup(
            f"merge blocked by insufficient free space: {sourceDir} -> {destinationDir}"
        )
        return False

    def _countResetTvShowMergeEntries(self, sourceDir: Path) -> int:
        """Return the number of descendant entries involved in a TV merge."""
        try:
            return sum(1 for _path in sourceDir.rglob("*"))
        except OSError:
            return 0

    def _mergeResetTvShowFolderContents(
        self,
        sourceDir: Path,
        destinationDir: Path,
        progress=None,
    ) -> None:
        """Move non-conflicting files from *sourceDir* into *destinationDir*."""
        if not sourceDir.exists() or not sourceDir.is_dir():
            return
        destinationDir.mkdir(parents=True, exist_ok=True)
        for sourcePath in sorted(
            sourceDir.iterdir(), key=lambda item: item.name.casefold()
        ):
            destinationPath = destinationDir / sourcePath.name
            if progress is not None:
                progress.show(sourcePath.name)

            if sourcePath.is_dir():
                if destinationPath.exists() and not destinationPath.is_dir():
                    if progress is not None:
                        progress.pause()
                    logger.warning(
                        "skipping rescan merge; destination already exists: %s",
                        destinationPath,
                    )
                    self._recordSummaryCleanup(
                        f"cleanup needed: {sourcePath} conflicts with existing {destinationPath}"
                    )
                    if progress is not None:
                        progress.advance(1, sourcePath.name)
                    continue

                self._mergeResetTvShowFolderContents(
                    sourcePath, destinationPath, progress=progress
                )
                try:
                    self.filesystem.removeEmptyDirectory(sourcePath)
                    self._recordSummaryCleanup(f"removed empty folder: {sourcePath}")
                except OSError:
                    pass
                if progress is not None:
                    progress.advance(1, sourcePath.name)
                continue

            if destinationPath.exists():
                if progress is not None:
                    progress.pause()
                logger.warning(
                    "skipping rescan merge; destination already exists: %s",
                    destinationPath,
                )
                self._recordSummaryCleanup(
                    f"cleanup needed: {sourcePath} conflicts with existing {destinationPath}"
                )
                if progress is not None:
                    progress.advance(1, sourcePath.name)
                continue

            self._recordSummaryTransfer(sourcePath, destinationPath)
            self.filesystem.move(sourcePath, destinationPath)
            if progress is not None:
                progress.advance(1, sourcePath.name)

        try:
            self.filesystem.removeEmptyDirectory(sourceDir)
            self._recordSummaryCleanup(f"removed empty folder: {sourceDir}")
        except OSError:
            pass

    def _mergeResetDuplicateTvShowFolders(
        self,
        tvDir: Path,
        showEntries: list[dict],
        duplicateGroups: Optional[list[list[str]]] = None,
        showDirsBySeriesId: Optional[dict] = None,
        canonicalNameGroups: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Prompt for and merge duplicate TV show folders before rescanning."""
        if not self._shouldPromptInteractively():
            return showEntries

        entriesByShowName = {entry["showName"]: entry for entry in showEntries}
        if duplicateGroups is None:
            duplicateAnalysis = self._buildResetDuplicateTvShowAnalysis(showEntries)
            duplicateGroups = duplicateAnalysis["duplicateGroups"]
            showDirsBySeriesId = duplicateAnalysis["showNamesBySeriesId"]
            canonicalNameGroups = duplicateAnalysis["canonicalNameGroups"]
        if not duplicateGroups:
            return showEntries

        unpromptedGroups = {
            tuple(self._sortResetDuplicateShowNames(group)): set(group)
            for group in duplicateGroups
        }
        leftoverMergedDirs = set()

        if showDirsBySeriesId is None:
            showDirsBySeriesId = {}
        if canonicalNameGroups is None:
            canonicalNameGroups = []

        def _mergePromptedGroup(
            masterShowName: str, orderedShowNames: list[str]
        ) -> None:
            masterEntry = entriesByShowName.get(masterShowName)
            if masterEntry is None:
                return

            for showName in orderedShowNames:
                if showName == masterShowName:
                    continue
                sourceEntry = entriesByShowName.get(showName)
                if sourceEntry is None or sourceEntry.get("_mergedInto"):
                    continue
                sourceDir = tvDir / showName
                destinationDir = tvDir / masterShowName
                logger.multiline(["merging TV show folders", masterShowName, showName])
                if self.dryRun:
                    self._recordSummaryCleanup(
                        f"merge TV show folders needed: {sourceDir} -> {destinationDir}"
                    )
                    continue

                self._mergeResetTvShowFolderContents(sourceDir, destinationDir)
                if sourceDir.exists():
                    leftoverMergedDirs.add(sourceDir)
                if not masterEntry.get("seriesId") and sourceEntry.get("seriesId"):
                    masterEntry["seriesId"] = sourceEntry["seriesId"]
                sourceEntry["_mergedInto"] = masterShowName

        def _promptMatchingGroup(showNames: list[str]) -> None:
            warningShowNames = set(showNames)
            for groupKey, groupShowNames in list(unpromptedGroups.items()):
                if not warningShowNames.issubset(groupShowNames):
                    continue
                promptResult = self._promptResetDuplicateTvShowMerge(list(groupKey))
                unpromptedGroups.pop(groupKey, None)
                if promptResult is None:
                    return

                _mergePromptedGroup(*promptResult)
                return

        for warning in self._iterResetDuplicateTvShowWarnings(
            showDirsBySeriesId, canonicalNameGroups
        ):
            warningShowNames = set(warning["showNames"])
            if not any(
                warningShowNames.issubset(groupShowNames)
                for groupShowNames in unpromptedGroups.values()
            ):
                continue
            logger.multiline([warning["label"], *warning["showNames"]])
            _promptMatchingGroup(warning["showNames"])

        for groupKey in list(unpromptedGroups):
            promptResult = self._promptResetDuplicateTvShowMerge(list(groupKey))
            unpromptedGroups.pop(groupKey, None)
            if promptResult is None:
                continue

            _mergePromptedGroup(*promptResult)

        if leftoverMergedDirs:
            for path in sorted(leftoverMergedDirs):
                self._recordSummaryCleanup(f"cleanup needed: {path}")
            logger.multiline(
                [
                    "rescan merge cleanup still needed",
                    *sorted(str(path) for path in leftoverMergedDirs),
                ]
            )

        return [entry for entry in showEntries if not entry.get("_mergedInto")]

    def _iterResetEpisodeCompanionRenames(
        self, videoFile: Path, destinationPath: Path
    ) -> list[tuple[Path, Path]]:
        """Return existing same-stem XML/JPG companion files that should be renamed."""
        candidates = []
        sameDir = videoFile.parent
        metadataDir = sameDir / "metadata"
        for baseDir in (sameDir, metadataDir):
            for suffix in (".xml", ".jpg"):
                candidates.append(
                    (
                        baseDir / f"{videoFile.stem}{suffix}",
                        baseDir / f"{destinationPath.stem}{suffix}",
                    )
                )

        renames = []
        seen = set()
        for sourcePath, destPath in candidates:
            if sourcePath in seen:
                continue
            seen.add(sourcePath)
            if sourcePath.exists() and sourcePath != destPath:
                renames.append((sourcePath, destPath))
        return renames

    def _updateEpisodeMetadataFile(self, metadataFile: Path, tvInfo: dict) -> None:
        """Update or regenerate an existing episode metadata XML file."""
        root = self._readXmlRoot(metadataFile)
        if root is None:
            if metadataFile.exists() and self._readXmlText(metadataFile) is not None:
                root = self._buildEpisodeMetadataTemplateRoot(tvInfo)
                if root is None:
                    return
                if self.dryRun:
                    return
                self._writeXml(metadataFile, root)
            return

        _, changed = self._updateEpisodeMetadataRoot(root, tvInfo)
        episodeTitle = tvInfo.get("episodeTitle")
        episodeTitleNode = root.find("EpisodeName")
        if episodeTitleNode is None:
            episodeTitleNode = ET.SubElement(root, "EpisodeName")
            changed = True
        if (episodeTitleNode.text or "") != (episodeTitle or ""):
            episodeTitleNode.text = episodeTitle or ""
            changed = True
        if not changed:
            return
        if self.dryRun:
            return
        self._writeXml(metadataFile, root)

    def _updateMovieMetadataRoot(self, root: ET.Element, movieInfo: dict) -> bool:
        """Update a movie metadata XML root with resolved title, year, and IDs."""
        fieldMap = {
            "LocalTitle": movieInfo.get("title") or "",
            "OriginalTitle": movieInfo.get("title") or "",
            "ProductionYear": movieInfo.get("year") or "",
            "IMDbId": movieInfo.get("imdbId") or "",
            "TMDbId": movieInfo.get("tmdbId") or "",
        }
        changed = False
        for fieldName, value in fieldMap.items():
            node = root.find(fieldName)
            if node is None:
                node = ET.SubElement(root, fieldName)
                changed = True
            if (node.text or "") != value:
                node.text = value
                changed = True
        return changed

    def _updateMovieMetadataFile(self, metadataFile: Path, movieInfo: dict) -> None:
        """Update or regenerate movie.xml for an existing stored movie."""
        root = self._readXmlRoot(metadataFile)
        if root is None:
            if metadataFile.exists() and self._readXmlText(metadataFile) is not None:
                title = movieInfo.get("title")
                if not title:
                    return
                root = ET.Element("Title")
                self._updateMovieMetadataRoot(root, movieInfo)
                if self.dryRun:
                    return
                self._writeXml(metadataFile, root)
            return

        if not self._updateMovieMetadataRoot(root, movieInfo):
            return
        logger.action("update metadata: %s", metadataFile)
        if self.dryRun:
            return
        self._writeXml(metadataFile, root)

    def _resolveResetMovieInfo(self, videoFile: Path) -> Optional[dict]:
        """Resolve one canonical movie identity for a reset-scan folder."""
        with self._suppressResetNoiseLogs():
            mcmHints = self._readMovieMcmHints(videoFile)
            parsedMovieInfo = self.parseMovieFilename(videoFile.name)
            sourceMovieInfo = (
                self._applyMovieMcmHints(parsedMovieInfo, mcmHints, videoFile)
                or parsedMovieInfo
            )
            sourceMovieInfo = self._normaliseMovieMetadata(sourceMovieInfo)
            if not sourceMovieInfo:
                return None
            return self._enrichMovieMetadata(sourceMovieInfo) or sourceMovieInfo

    def _resetMovieMetadataForFile(
        self,
        videoFile: Path,
        reservedDestinations: Optional[set[Path]] = None,
        resolvedMovieInfo: Optional[dict] = None,
    ) -> str:
        """Repair metadata and canonical naming for one stored movie file."""
        if resolvedMovieInfo is None:
            resolvedMovieInfo = self._resolveResetMovieInfo(videoFile)
        if not resolvedMovieInfo:
            return "skipped"
        resolvedMovieInfo = dict(resolvedMovieInfo)
        resolvedMovieInfo["extension"] = videoFile.suffix

        movieDir = videoFile.parent
        with self._suppressResetMetadataPreserveLogs():
            movieXml = movieDir / "movie.xml"
            if movieXml.exists():
                self._updateMovieMetadataFile(movieXml, resolvedMovieInfo)
            else:
                self._ensureMovieMetadata(movieDir, resolvedMovieInfo)
            self._ensureMovieDvdIdMetadata(movieDir, resolvedMovieInfo)
            self._fetchMovieArtwork(resolvedMovieInfo, movieDir)

        destinationName = self._buildMovieDestinationFilename(
            videoFile, resolvedMovieInfo
        )
        if destinationName == videoFile.name:
            return "skipped"

        destinationPath = videoFile.with_name(destinationName)
        if destinationPath.exists() or (
            reservedDestinations is not None and destinationPath in reservedDestinations
        ):
            logger.error("scan movie target already exists: %s", destinationPath)
            return "errors"
        if reservedDestinations is not None:
            reservedDestinations.add(destinationPath)

        logger.multiline(["renaming movie", videoFile.name, destinationPath.name])
        if self.dryRun:
            self._recordSummaryRename(videoFile, destinationPath)
            return "renamed"

        try:
            self.filesystem.rename(videoFile, destinationPath)
        except OSError as error:
            if error.errno != errno.EINVAL or ":" not in destinationPath.name:
                logger.error(
                    "could not rename movie %s -> %s: %s",
                    videoFile,
                    destinationPath,
                    error,
                )
                return "errors"
            fallbackPath = self._filesystemSafeResetFallback(destinationPath)
            if fallbackPath.exists() or (
                reservedDestinations is not None
                and fallbackPath in reservedDestinations
            ):
                logger.error(
                    "scan movie fallback target already exists: %s", fallbackPath
                )
                return "errors"
            logger.multiline(
                ["filesystem-safe movie name", destinationPath.name, fallbackPath.name]
            )
            try:
                self.filesystem.rename(videoFile, fallbackPath)
            except (OSError, ValueError) as fallbackError:
                logger.error(
                    "could not rename movie %s -> %s: %s",
                    videoFile,
                    fallbackPath,
                    fallbackError,
                )
                return "errors"
            destinationPath = fallbackPath
            if reservedDestinations is not None:
                reservedDestinations.add(destinationPath)
        except ValueError as error:
            logger.error(
                "could not rename movie %s -> %s: %s",
                videoFile,
                destinationPath,
                error,
            )
            return "errors"
        self._recordSummaryRename(videoFile, destinationPath)
        return "renamed"

    def _maybeRenameResetMovieFolder(
        self,
        movieFolder: Path,
        videoFiles: list[Path],
        movieInfo: Optional[dict] = None,
    ):
        """Return updated movie folder and paths after canonical folder rename."""
        if not movieFolder.is_dir() or not videoFiles:
            return movieFolder, videoFiles

        if movieInfo is None:
            movieInfo = self._resolveResetMovieInfo(videoFiles[0])
        if not movieInfo or not movieInfo.get("title") or not movieInfo.get("year"):
            return movieFolder, videoFiles

        from .showFolders import canonicalMovieFolderName

        destinationDir = movieFolder.with_name(
            canonicalMovieFolderName(f"{movieInfo['title']} ({movieInfo['year']})")
        )
        if destinationDir == movieFolder:
            return movieFolder, videoFiles
        if destinationDir.exists():
            logger.error(
                "rescan movie folder target already exists: %s", destinationDir
            )
            return movieFolder, videoFiles

        logger.multiline(
            ["renaming movie folder", movieFolder.name, destinationDir.name]
        )
        if self.dryRun:
            self._recordSummaryRename(movieFolder, destinationDir)
            return destinationDir, [
                destinationDir / videoFile.relative_to(movieFolder)
                for videoFile in videoFiles
            ]

        try:
            self.filesystem.rename(movieFolder, destinationDir)
        except OSError as error:
            if error.errno != errno.EINVAL or ":" not in destinationDir.name:
                logger.error("could not rename movie folder %s: %s", movieFolder, error)
                return movieFolder, videoFiles
            fallbackDir = self._filesystemSafeResetFallback(destinationDir)
            if fallbackDir.exists():
                logger.error(
                    "rescan movie folder fallback target already exists: %s",
                    fallbackDir,
                )
                return movieFolder, videoFiles
            logger.multiline(
                ["filesystem-safe movie folder", destinationDir.name, fallbackDir.name]
            )
            try:
                self.filesystem.rename(movieFolder, fallbackDir)
            except (OSError, ValueError) as fallbackError:
                logger.error(
                    "could not rename movie folder %s -> %s: %s",
                    movieFolder,
                    fallbackDir,
                    fallbackError,
                )
                return movieFolder, videoFiles
            destinationDir = fallbackDir
        self._recordSummaryRename(movieFolder, destinationDir)

        return destinationDir, [
            destinationDir / videoFile.relative_to(movieFolder)
            for videoFile in videoFiles
        ]

    def _resetTvEpisodeTitleForFile(self, videoFile: Path) -> str:
        """Rename one stored TV episode file when better title metadata is available."""
        parsedTvInfo = self.parseTvFilename(videoFile.name)
        if not parsedTvInfo:
            return "skipped"
        parsedEpisodeTitle = parsedTvInfo.get("episodeTitle")
        parsedEpisodeTitleNeedsCleanup = self._parsedTvEpisodeTitleNeedsCleanup(
            videoFile.name
        )
        timedTitle = self._normaliseTimedTvEpisodeTitle(parsedEpisodeTitle)
        needsCanonicalLookup = self._tvEpisodeTitleNeedsCanonicalLookup(
            parsedEpisodeTitle
        )
        needsTimedTitleNormalisation = timedTitle not in (None, parsedEpisodeTitle)
        if needsTimedTitleNormalisation:
            parsedTvInfo = dict(parsedTvInfo)
            parsedTvInfo["episodeTitle"] = timedTitle

        sourceSeasonDir = videoFile.parent
        showDir = (
            sourceSeasonDir.parent
            if re.match(r"^season\b", sourceSeasonDir.name, re.IGNORECASE)
            and sourceSeasonDir.parent != sourceSeasonDir
            else None
        )
        needsMetadataRepair = bool(
            showDir
            and (
                not (showDir / "series.xml").exists()
                or self._readFirstXmlText(
                    self._readXmlRoot(showDir / "series.xml"),
                    ("SeriesID", "seriesid", "id"),
                )
                is None
                or not self._hasMatchingFiles(showDir, ("mcm_id__*.dvdid.xml",))
                or any(
                    self._readFirstXmlText(
                        self._readXmlRoot(dvdIdFile),
                        ("SeriesID", "seriesid", "id"),
                    )
                    is None
                    for dvdIdFile in showDir.glob("mcm_id__*.dvdid.xml")
                )
            )
        )

        with self._suppressResetNoiseLogs():
            mcmHints = self._readTvMcmHints(videoFile)
            sourceTvInfo = (
                self._applyTvMcmHints(parsedTvInfo, mcmHints, videoFile) or parsedTvInfo
            )
            sourceTvInfo = self._normaliseTvMetadata(sourceTvInfo)
            if not sourceTvInfo:
                return "skipped"

            libraryMatch = self._lookupTvMetadataInLibrary(sourceTvInfo)
            keepExistingShowName = sourceTvInfo.get("metadataSource") == "mcm"
            resolvedTvInfo = self._applyAuthoritativeTvMetadata(
                sourceTvInfo,
                libraryMatch,
                keepExistingShowName=keepExistingShowName,
            )
            resolvedTvInfo = self._resolveCanonicalTvShowName(
                resolvedTvInfo,
                libraryMatch,
                keepExistingShowName=keepExistingShowName,
            )

            if needsCanonicalLookup or (
                needsMetadataRepair and not resolvedTvInfo.get("seriesId")
            ):
                resolvedTvInfo = (
                    self._enrichTvMetadata(resolvedTvInfo) or resolvedTvInfo
                )

        capitalisedShowName = self._capitaliseLowercaseTvShowTitle(
            resolvedTvInfo.get("showName")
        )
        needsShowTitleNormalisation = capitalisedShowName != resolvedTvInfo.get(
            "showName"
        )
        if needsShowTitleNormalisation:
            resolvedTvInfo = dict(resolvedTvInfo)
            resolvedTvInfo["showName"] = capitalisedShowName

        resolvedEpisodeTitle = resolvedTvInfo.get("episodeTitle")
        parsedEpisodeTitleKey = self._normaliseLookupText(parsedEpisodeTitle)
        resolvedEpisodeTitleKey = self._normaliseLookupText(resolvedEpisodeTitle)
        hasIncorrectEpisodeTitle = bool(
            parsedEpisodeTitleKey
            and resolvedEpisodeTitleKey
            and parsedEpisodeTitleKey != resolvedEpisodeTitleKey
        )

        if showDir is not None:
            with self._suppressResetMetadataPreserveLogs():
                self._ensureSeriesMetadata(showDir, resolvedTvInfo)
                self._ensureTvDvdIdMetadata(videoFile, showDir, resolvedTvInfo)

        sourceMetadataFile = videoFile.parent / "metadata" / f"{videoFile.stem}.xml"
        preferSpaceStyle = (
            needsCanonicalLookup
            or needsTimedTitleNormalisation
            or parsedEpisodeTitleNeedsCleanup
            or hasIncorrectEpisodeTitle
        )
        destinationName = self._buildTvDestinationFilename(
            videoFile, resolvedTvInfo, preferSpaceStyle=preferSpaceStyle
        )
        if (
            not needsCanonicalLookup
            and not needsTimedTitleNormalisation
            and not needsShowTitleNormalisation
            and not parsedEpisodeTitleNeedsCleanup
            and not hasIncorrectEpisodeTitle
        ):
            if sourceMetadataFile.exists():
                self._updateEpisodeMetadataFile(sourceMetadataFile, resolvedTvInfo)
            return "skipped"

        if destinationName == videoFile.name:
            return "skipped"

        destinationPath = videoFile.with_name(destinationName)
        if destinationPath.exists():
            logger.error("rescan target already exists: %s", destinationPath)
            return "errors"

        companionRenames = self._iterResetEpisodeCompanionRenames(
            videoFile, destinationPath
        )
        for sourcePath, companionDestination in companionRenames:
            if companionDestination.exists():
                logger.error("rescan target already exists: %s", companionDestination)
                return "errors"

        destinationMetadataFile = (
            videoFile.parent / "metadata" / f"{destinationPath.stem}.xml"
        )

        logger.multiline(["renaming", videoFile.name, destinationPath.name])
        if self.dryRun:
            self._recordSummaryRename(videoFile, destinationPath)
            for sourcePath, companionDestination in companionRenames:
                self._recordSummaryRename(sourcePath, companionDestination)
            return "renamed"

        try:
            self.filesystem.rename(videoFile, destinationPath)
            self._recordSummaryRename(videoFile, destinationPath)
            for sourcePath, companionDestination in companionRenames:
                self.filesystem.rename(sourcePath, companionDestination)
                self._recordSummaryRename(sourcePath, companionDestination)
        except (OSError, ValueError) as error:
            logger.error(
                "could not rename TV episode %s -> %s: %s",
                videoFile,
                destinationPath,
                error,
            )
            return "errors"
        if destinationMetadataFile.exists():
            self._updateEpisodeMetadataFile(destinationMetadataFile, resolvedTvInfo)
        return "renamed"

    def _handleTargetedResetTvShowDuplicates(
        self,
        videoDirs: list[Path],
        showFilter: str,
        selectedFolders: Optional[set[Path]] = None,
    ) -> None:
        """Detect and optionally merge one targeted TV show across all storage roots."""
        if selectedFolders is None:
            selectedFolders = self._resetTvShowFoldersResolve(videoDirs, showFilter)
        entries = [
            {"showName": showDir.name, "showDir": showDir}
            for showDir in sorted(selectedFolders)
        ]
        if len(entries) < 2:
            return

        canonicalName = self._stripResetTvShowDuplicateSuffixes(showFilter)
        displayPaths = sorted(str(entry["showDir"]) for entry in entries)
        label = f"possible duplicate TV show folders: {canonicalName}"
        logger.multiline([label, *displayPaths])
        self._recordSummaryDuplicateTvShow(label, displayPaths)

        if not self._shouldPromptInteractively():
            return

        shouldMerge = self._readMenuChoice(
            "Merge these folders? (y/n/q): ",
            validChoices={"y", "n", "q"},
            defaultChoice="n",
        )
        if shouldMerge in {"q", "quit"}:
            logger.info("user requested to quit")
            sys.exit(0)
        if shouldMerge != "y":
            return

        selectionKeys = "123456789abcdefghijklmnopqrstuvwxyz"
        if len(entries) > len(selectionKeys):
            logger.warning("too many matching TV show folders to choose a merge master")
            return

        orderedEntries = sorted(
            entries, key=lambda entry: str(entry["showDir"]).casefold()
        )
        choiceMap = dict(zip(selectionKeys, orderedEntries))
        choiceLines = "\n".join(
            f"  {key}) {entry['showDir']}" for key, entry in choiceMap.items()
        )
        defaultChoice = next(iter(choiceMap))
        selectedChoice = self._readMenuChoice(
            "Choose the master TV show folder for the merged result:\n"
            f"{choiceLines}\n"
            f"Select master folder ({'/'.join(choiceMap)}): ",
            validChoices=set(choiceMap),
            defaultChoice=defaultChoice,
        )
        masterDir = choiceMap[selectedChoice]["showDir"]

        for entry in orderedEntries:
            sourceDir = entry["showDir"]
            if sourceDir == masterDir:
                continue
            logger.multiline(["merging TV show folders", masterDir, sourceDir])
            if not self._resetTvShowMergeHasSufficientSpace(sourceDir, masterDir):
                continue
            if self.dryRun:
                self._recordSummaryCleanup(
                    f"merge TV show folders needed: {sourceDir} -> {masterDir}"
                )
                continue
            from .mediaMerge import _TvMergeProgress

            mergeProgress = _TvMergeProgress(
                self._stripResetTvShowDuplicateSuffixes(masterDir.name),
                sourceDir.name,
            )
            mergeProgress.setTotal(self._countResetTvShowMergeEntries(sourceDir))
            try:
                self._mergeResetTvShowFolderContents(
                    sourceDir, masterDir, progress=mergeProgress
                )
            finally:
                mergeProgress.finish()
            if sourceDir.exists():
                self._recordSummaryCleanup(f"cleanup needed: {sourceDir}")

    def resetTvEpisodeTitles(
        self,
        videoDirs: Optional[list[Path]] = None,
        *,
        showFilter: Optional[str] = None,
        deepScan: bool = True,
    ) -> dict:
        """Repair selected TV metadata; deep scans also retitle every selected episode."""
        stats = {"renamed": 0, "skipped": 0, "errors": 0}

        if videoDirs is None:
            with self._suppressResetNoiseLogs():
                movieDirs, videoDirs = self.scanStorageLocations()
                self._prepareMetadataLibrary(movieDirs, videoDirs)
        if not videoDirs:
            logger.error("No TV storage locations found!")
            self._writeSummaryReport()
            return stats

        selectedFolders = None
        if showFilter:
            # Duplicate handling and episode discovery must use the same selection.
            selectedFolders = self._resetTvShowFoldersResolve(videoDirs, showFilter)
            self._handleTargetedResetTvShowDuplicates(
                videoDirs, showFilter, selectedFolders
            )

        preparedGroupsByDir = []
        for tvDir in videoDirs:
            if not showFilter:
                showEntries = self._buildResetDuplicateTvShowEntries(tvDir)
                duplicateAnalysis = self._buildResetDuplicateTvShowAnalysis(showEntries)
                self._recordSummaryDuplicateTvShowWarnings(
                    duplicateAnalysis["showNamesBySeriesId"],
                    duplicateAnalysis["canonicalNameGroups"],
                )
                duplicateGroups = self._filterIgnoredResetDuplicateTvShowGroups(
                    duplicateAnalysis["duplicateGroups"]
                )

                if self._shouldPromptInteractively():
                    self._mergeResetDuplicateTvShowFolders(
                        tvDir,
                        showEntries,
                        duplicateGroups,
                        duplicateAnalysis["showNamesBySeriesId"],
                        duplicateAnalysis["canonicalNameGroups"],
                    )
                else:
                    for warning in self._iterResetDuplicateTvShowWarnings(
                        duplicateAnalysis["showNamesBySeriesId"],
                        duplicateAnalysis["canonicalNameGroups"],
                    ):
                        logger.multiline([warning["label"], *warning["showNames"]])

            preparedGroupsByDir.append(
                (
                    tvDir,
                    list(
                        self._iterResetSelectedTvShowFiles(
                            tvDir,
                            showFilter=showFilter,
                            selectedFolders=selectedFolders,
                            deepScan=deepScan or bool(showFilter),
                        )
                    ),
                )
            )

        totalShows = sum(len(groups) for _tvDir, groups in preparedGroupsByDir)
        progress = _ResetScanProgress(totalShows, "Scanning TV library")
        completedShows = 0

        for tvDir, preparedShowGroups in preparedGroupsByDir:
            for showName, seriesId, videoFiles in preparedShowGroups:
                progress.render(completedShows, showName)
                with self._bufferResetItemLogs() as itemLogs:
                    showName, videoFiles = self._maybeRenameResetTvShowFolder(
                        tvDir, showName, videoFiles
                    )
                    showDisplayName = self._buildTvShowFolderName(showName)
                    for videoFile in videoFiles:
                        outcome = self._resetTvEpisodeTitleForFile(videoFile)
                        stats[outcome] += 1
                completedShows += 1
                progress.render(completedShows, showDisplayName)
                self._flushResetItemLogs(progress, itemLogs)

        progress.finish()
        self._writeSummaryReport()
        return stats

    def resetMovieMetadata(self, movieDirs: Optional[list[Path]] = None) -> dict:
        """Repair stored movie metadata and canonical movie filenames."""
        stats = {"renamed": 0, "skipped": 0, "errors": 0}

        if movieDirs is None:
            with self._suppressResetNoiseLogs():
                movieDirs, videoDirs = self.scanStorageLocations()
                self._prepareMetadataLibrary(movieDirs, videoDirs)

        if not movieDirs:
            logger.error("No movie storage locations found!")
            return stats

        movieGroups = [
            item
            for movieDir in movieDirs
            for item in self._iterResetMovieFiles(movieDir)
        ]
        progress = _ResetScanProgress(len(movieGroups), "Scanning movie library")
        reservedDestinations: set[Path] = set()
        try:
            for completed, (movieFolder, videoFiles) in enumerate(movieGroups):
                progress.render(completed, movieFolder.name)
                with self._bufferResetItemLogs() as itemLogs:
                    resolvedMovieInfo = self._resolveResetMovieInfo(videoFiles[0])
                    movieFolder, videoFiles = self._maybeRenameResetMovieFolder(
                        movieFolder, videoFiles, resolvedMovieInfo
                    )
                    for videoFile in videoFiles:
                        outcome = self._resetMovieMetadataForFile(
                            videoFile, reservedDestinations, resolvedMovieInfo
                        )
                        stats[outcome] += 1
                progress.render(completed + 1, movieFolder.name)
                self._flushResetItemLogs(progress, itemLogs)
        finally:
            progress.finish()

        return stats

    def resetLibraryMetadata(
        self,
        target: str = "both",
        *,
        showFilter: Optional[str] = None,
        deepScan: bool = True,
    ) -> dict:
        """Repair stored media, optionally limiting TV work or using a lightweight scan."""
        target = (target or "both").casefold()
        if target == "movie":
            target = "movies"
        if target not in {"both", "movies", "tv"}:
            raise ValueError(f"unknown rescan target: {target}")

        with self._suppressResetNoiseLogs():
            movieDirs, videoDirs = self.scanStorageLocations()
            metadataMovieDirs = movieDirs if target in {"both", "movies"} else []
            metadataVideoDirs = videoDirs if target in {"both", "tv"} else []
            if showFilter:
                self._loadMetadataLibrary()
            else:
                self._prepareMetadataLibrary(metadataMovieDirs, metadataVideoDirs)

        if deepScan and not showFilter:
            self._mediaCatalogueReplace(
                movieDirs,
                videoDirs,
                replaceMovies=target in {"both", "movies"},
                replaceTv=target in {"both", "tv"},
            )

        emptyStats = {"renamed": 0, "skipped": 0, "errors": 0}
        movieStats = dict(emptyStats)
        tvStats = {"renamed": 0, "skipped": 0, "errors": 0}

        if target in {"both", "movies"}:
            movieStats = self.resetMovieMetadata(movieDirs)

        if target in {"both", "tv"}:
            if videoDirs:
                tvStats = self.resetTvEpisodeTitles(
                    videoDirs,
                    showFilter=showFilter,
                    deepScan=deepScan,
                )
            else:
                logger.error("No TV storage locations found!")
                self._writeSummaryReport()
        else:
            self._writeSummaryReport()

        return {"movies": movieStats, "tv": tvStats}

    def _mediaCatalogueReplace(
        self,
        movieDirs: list[Path],
        videoDirs: list[Path],
        *,
        replaceMovies: bool = True,
        replaceTv: bool = True,
    ) -> None:
        """Refresh SQLite movie/TV rows from the scanned storage roots."""

        from . import constants
        from .mediaCatalogue import MediaCatalogue

        MediaCatalogue(
            databasePath=constants.MEDIA_CATALOGUE_DATABASE
        ).catalogueReplaceFromStorage(
            movieDirs,
            videoDirs,
            replaceMovies=replaceMovies,
            replaceTv=replaceTv,
        )
