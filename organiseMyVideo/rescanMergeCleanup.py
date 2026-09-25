"""Safe cleanup behaviour for duplicate TV folders merged during rescans."""

from __future__ import annotations

import filecmp
from pathlib import Path

from organiseMyProjects.logUtils import getLogger  # type: ignore

logger = getLogger()


class RescanMergeCleanupMixin:
    """Remove redundant collisions while preserving genuine media conflicts."""

    def _mergeResetTvShowFolderContents(
        self,
        sourceDir: Path,
        destinationDir: Path,
        progress=None,
    ) -> None:
        """Merge *sourceDir* and clean redundant copies safely.

        Files missing from the destination are moved. Recognised regenerable TV
        metadata always keeps the selected master-folder copy and discards the
        source copy. Other collisions are removed only when byte-identical;
        differing files are retained and reported as conflicts. Empty source
        directories are removed as the recursive merge unwinds.

        When a live merge progress display is supplied, conflict warnings are
        buffered until the outermost merge completes so logger output does not
        interrupt the progress line.
        """
        if not sourceDir.exists() or not sourceDir.is_dir():
            return

        ownsConflictBuffer = progress is not None and not hasattr(
            progress, "_resetMergeConflicts"
        )
        if ownsConflictBuffer:
            progress._resetMergeConflicts = []

        destinationDir.mkdir(parents=True, exist_ok=True)
        for sourcePath in sorted(
            sourceDir.iterdir(), key=lambda item: item.name.casefold()
        ):
            destinationPath = destinationDir / sourcePath.name
            if progress is not None:
                progress.show(sourcePath.name)

            if sourcePath.is_dir():
                if destinationPath.exists() and not destinationPath.is_dir():
                    self._recordResetMergeConflict(
                        sourcePath, destinationPath, progress
                    )
                    continue

                self._mergeResetTvShowFolderContents(
                    sourcePath, destinationPath, progress=progress
                )
                self._removeResetMergeDirectoryIfEmpty(sourcePath)
                if progress is not None:
                    progress.advance(1, sourcePath.name)
                continue

            if destinationPath.exists():
                if destinationPath.is_file() and self._resetMergeMetadataIsRegenerable(
                    sourcePath
                ):
                    self.filesystem.removeFile(sourcePath, stateKind="media")
                    self._recordSummaryCleanup(
                        f"removed regenerable metadata duplicate: {sourcePath}"
                    )
                    if progress is not None:
                        progress.advance(1, sourcePath.name)
                    continue

                if destinationPath.is_file() and self._resetMergeFilesIdentical(
                    sourcePath, destinationPath
                ):
                    self.filesystem.removeFile(sourcePath, stateKind="media")
                    self._recordSummaryCleanup(
                        f"removed identical duplicate: {sourcePath}"
                    )
                    if progress is not None:
                        progress.advance(1, sourcePath.name)
                    continue

                self._recordResetMergeConflict(sourcePath, destinationPath, progress)
                continue

            self._recordSummaryTransfer(sourcePath, destinationPath)
            self.filesystem.move(sourcePath, destinationPath)
            if progress is not None:
                progress.advance(1, sourcePath.name)

        self._removeResetMergeDirectoryIfEmpty(sourceDir)

        if ownsConflictBuffer:
            conflicts = progress._resetMergeConflicts
            del progress._resetMergeConflicts
            if conflicts:
                progress.finish()
                logger.multiline(
                    [
                        f"rescan merge conflicts - {len(conflicts)} files retained",
                        *conflicts,
                    ]
                )

    @staticmethod
    def _resetMergeMetadataIsRegenerable(sourcePath: Path) -> bool:
        """Return True for TV metadata that can be regenerated after a merge."""
        if sourcePath.name.casefold() == "series.xml":
            return True
        return (
            sourcePath.suffix.casefold() == ".xml"
            and sourcePath.parent.name.casefold() == "metadata"
        )

    @staticmethod
    def _resetMergeFilesIdentical(sourcePath: Path, destinationPath: Path) -> bool:
        """Return True only when two regular files are byte-for-byte identical."""
        try:
            return filecmp.cmp(sourcePath, destinationPath, shallow=False)
        except OSError:
            return False

    def _recordResetMergeConflict(
        self, sourcePath: Path, destinationPath: Path, progress=None
    ) -> None:
        """Preserve and report a merge collision whose contents cannot be removed."""
        if progress is not None and hasattr(progress, "_resetMergeConflicts"):
            progress._resetMergeConflicts.append(str(destinationPath))
        else:
            logger.warning(
                "skipping rescan merge; destination already exists: %s",
                destinationPath,
            )
        self._recordSummaryCleanup(
            f"cleanup needed: {sourcePath} conflicts with existing {destinationPath}"
        )
        if progress is not None:
            progress.advance(1, sourcePath.name)

    def _removeResetMergeDirectoryIfEmpty(self, directory: Path) -> None:
        """Remove *directory* when the merge has left it empty."""
        try:
            self.filesystem.removeEmptyDirectory(directory)
        except OSError:
            return
        if not directory.exists():
            self._recordSummaryCleanup(f"removed empty folder: {directory}")
