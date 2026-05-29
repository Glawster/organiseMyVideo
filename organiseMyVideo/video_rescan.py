"""TV rescan/reset workflows and duplicate-folder handling."""

from contextlib import contextmanager
import difflib
import json
import re
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import APP_CONFIG_FILE, VIDEO_EXTENSIONS

logger = getLogger()
_IGNORED_TV_SHOW_DUPLICATES_CONFIG_KEY = "ignored_tv_show_duplicates"


class VideoRescanMixin:
    """Workflow methods for TV rescans and duplicate-folder repair."""

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
        """Hide no-op metadata preservation logs while keeping real update logs."""
        from . import metadata as metadata_module
        from . import video as video_module

        targets = (logger, video_module.logger, metadata_module.logger)
        originals = {target: target.value for target in targets}

        def _wrapValue(original):
            def _value(label, *args, **kwargs):
                if label in {
                    "preserving existing metadata",
                    "preserving existing metadata files",
                }:
                    return None
                return original(label, *args, **kwargs)

            return _value

        try:
            for target in targets:
                target.value = _wrapValue(target.value)
            yield
        finally:
            for target, original in originals.items():
                target.value = original

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
        APP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        APP_CONFIG_FILE.write_text(
            json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
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

    def _mergeResetTvShowFolderContents(
        self, sourceDir: Path, destinationDir: Path
    ) -> None:
        """Move non-conflicting files from *sourceDir* into *destinationDir*."""
        if not sourceDir.exists() or not sourceDir.is_dir():
            return
        destinationDir.mkdir(parents=True, exist_ok=True)
        for sourcePath in sorted(
            sourceDir.iterdir(), key=lambda item: item.name.casefold()
        ):
            destinationPath = destinationDir / sourcePath.name
            if destinationPath.exists():
                if sourcePath.is_dir() and destinationPath.is_dir():
                    self._mergeResetTvShowFolderContents(sourcePath, destinationPath)
                    try:
                        sourcePath.rmdir()
                        self._recordSummaryCleanup(
                            f"removed empty folder: {sourcePath}"
                        )
                    except OSError:
                        pass
                    continue
                logger.warning(
                    "skipping rescan merge; destination already exists: %s",
                    destinationPath,
                )
                self._recordSummaryCleanup(
                    f"cleanup needed: {sourcePath} conflicts with existing {destinationPath}"
                )
                continue
            logger.multiline(
                ["merging TV show folder item", sourcePath, destinationPath]
            )
            self._recordSummaryTransfer(sourcePath, destinationPath)
            shutil.move(str(sourcePath), str(destinationPath))

        try:
            sourceDir.rmdir()
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
                metadataFile.parent.mkdir(parents=True, exist_ok=True)
                ET.ElementTree(root).write(
                    metadataFile, encoding="utf-8", xml_declaration=True
                )
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
        ET.ElementTree(root).write(metadataFile, encoding="utf-8", xml_declaration=True)

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

        videoFile.rename(destinationPath)
        self._recordSummaryRename(videoFile, destinationPath)
        for sourcePath, companionDestination in companionRenames:
            companionDestination.parent.mkdir(parents=True, exist_ok=True)
            sourcePath.rename(companionDestination)
            self._recordSummaryRename(sourcePath, companionDestination)
        if destinationMetadataFile.exists():
            self._updateEpisodeMetadataFile(destinationMetadataFile, resolvedTvInfo)
        return "renamed"

    def resetTvEpisodeTitles(self) -> dict:
        """Retitle stored TV episodes whose filename suffix still looks noisy."""
        stats = {"renamed": 0, "skipped": 0, "errors": 0}

        with self._suppressResetNoiseLogs():
            movieDirs, videoDirs = self.scanStorageLocations()
            self._prepareMetadataLibrary(movieDirs, videoDirs)
        if not videoDirs:
            logger.error("No TV storage locations found!")
            self._writeSummaryReport()
            return stats

        for tvDir in videoDirs:
            if self._shouldPromptInteractively():
                showEntries = self._buildResetDuplicateTvShowEntries(tvDir)
                duplicateAnalysis = self._buildResetDuplicateTvShowAnalysis(showEntries)
                self._recordSummaryDuplicateTvShowWarnings(
                    duplicateAnalysis["showNamesBySeriesId"],
                    duplicateAnalysis["canonicalNameGroups"],
                )
                self._mergeResetDuplicateTvShowFolders(
                    tvDir,
                    showEntries,
                    self._filterIgnoredResetDuplicateTvShowGroups(
                        duplicateAnalysis["duplicateGroups"]
                    ),
                    duplicateAnalysis["showNamesBySeriesId"],
                    duplicateAnalysis["canonicalNameGroups"],
                )
                showEntryIterator = self._iterResetTvShowFiles(tvDir)
            else:
                duplicateAnalysis = self._buildResetDuplicateTvShowAnalysis(
                    self._buildResetDuplicateTvShowEntries(tvDir)
                )
                self._recordSummaryDuplicateTvShowWarnings(
                    duplicateAnalysis["showNamesBySeriesId"],
                    duplicateAnalysis["canonicalNameGroups"],
                )
                self._logResetDuplicateTvShowFolders(tvDir)
                showEntryIterator = self._iterResetTvShowFiles(tvDir)

            for showName, seriesId, videoFiles in showEntryIterator:
                showName, videoFiles = self._maybeRenameResetTvShowFolder(
                    tvDir, showName, videoFiles
                )
                showDisplayName = self._buildTvShowFolderName(showName)
                showLabel = (
                    f"{showDisplayName} [{seriesId}]" if seriesId else showDisplayName
                )
                logger.action(f"rescanning: {showLabel}")
                for videoFile in videoFiles:
                    outcome = self._resetTvEpisodeTitleForFile(videoFile)
                    stats[outcome] += 1

        self._writeSummaryReport()
        return stats
