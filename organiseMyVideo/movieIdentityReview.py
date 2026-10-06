"""REQ-035 review fixes for suspect movie metadata and ancillary matching."""

from __future__ import annotations

import re
from pathlib import Path

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS
from .incomingNames import mediaNameIsAncillary
from .movieIdentity import (
    movieIdentityClassifySources,
    movieIdentityEvidence,
    movieIdentityMetadataSuspectReasons,
    movieIdentityReport,
)

logger = getLogger()

_ANCILLARY_DESCRIPTOR = re.compile(
    r"(?:behind[ ._-]+the[ ._-]+scenes|featurettes?|deleted[ ._-]+scenes?|"
    r"interviews?|making[ ._-]+of|trailers?)",
    re.IGNORECASE,
)
_ANCILLARY_SEGMENT = re.compile(
    rf"(?:^|\s[-–—]\s|[._\[\]()]+){_ANCILLARY_DESCRIPTOR.pattern}"
    rf"(?=$|\s[-–—]\s|[._\[\]()]+)",
    re.IGNORECASE,
)


class MovieIdentityReviewMixin:
    """Tighten REQ-035 identity evidence without changing general scan policy."""

    def _movieTechnicalRuntimeMinutes(self, *paths: Path) -> str | None:
        """Return actual feature runtime in minutes when a video can be probed."""
        videoFile = next(
            (
                Path(path)
                for path in paths
                if Path(path).is_file()
                and Path(path).suffix.casefold() in VIDEO_EXTENSIONS
            ),
            None,
        )
        if videoFile is None:
            return None

        from organiseMediaStudio.video.errors import VideoProcessingError
        from organiseMediaStudio.video.probe import videoProbe

        try:
            durationSeconds = videoProbe(videoFile).durationSeconds
        except (OSError, VideoProcessingError):
            return None
        if durationSeconds is None or durationSeconds <= 0:
            return None
        minutes = durationSeconds / 60.0
        return f"{minutes:.1f}".rstrip("0").rstrip(".")

    def _movieIdentityDecisionForPaths(self, movieInfo: dict, *paths: Path):
        """Return the current-vs-proposed decision used in identity reporting."""
        sources = []
        for path in paths:
            parsed = self.parseMovieFilename(Path(path).name)
            if not parsed or not parsed.get("title"):
                continue
            sources.append((parsed.get("title"), parsed.get("year")))
        return movieIdentityClassifySources(
            sources,
            movieInfo.get("title"),
            movieInfo.get("year"),
        )

    def _refuseMovieIdentityChange(self, movieInfo: dict, *paths: Path) -> bool:
        """Block suspect MCM evidence before ordinary identity comparison."""
        if movieInfo.get("metadataSource") == "mcm":
            mediaRuntime = movieInfo.get("mediaRuntime")
            if movieInfo.get("runtime") and mediaRuntime is None:
                mediaRuntime = self._movieTechnicalRuntimeMinutes(*paths)

            suspectReasons = movieIdentityMetadataSuspectReasons(
                movieInfo.get("title"),
                metadataRuntime=movieInfo.get("runtime"),
                mediaRuntime=mediaRuntime,
            )
            if suspectReasons:
                if mediaRuntime is not None:
                    movieInfo["mediaRuntime"] = mediaRuntime
                if not movieInfo.get("identityConflict"):
                    movieInfo["identityConflict"] = self._movieIdentityDecisionForPaths(
                        movieInfo, *paths
                    )
                if not movieInfo.get("identityConflictReported"):
                    self._reportMovieIdentityConflict(movieInfo, *paths)
                    movieInfo["identityConflictReported"] = True
                return True

        return super()._refuseMovieIdentityChange(movieInfo, *paths)

    def _reportMovieIdentityConflict(self, movieInfo: dict, *paths: Path) -> None:
        """Include the affected folder in the visible operator warning."""
        report = movieIdentityReport(
            movieInfo["identityConflict"],
            evidence=movieIdentityEvidence(movieInfo),
            imdbId=movieInfo.get("imdbId"),
            tmdbId=movieInfo.get("tmdbId"),
            runtime=movieInfo.get("runtime"),
            mediaRuntime=movieInfo.get("mediaRuntime"),
        )
        location = next(
            (
                path if path.is_dir() else path.parent
                for path in (Path(path) for path in paths)
            ),
            None,
        )
        lines = report.splitlines()
        if location is not None:
            lines.insert(1, f"folder: {location}")
        visibleReport = "\n".join(lines)
        logger.warning("%s", visibleReport)
        self._recordSummaryInvestigation(lines[0], *lines[1:])

    def _isResetMovieAncillaryFile(self, movieFolder: Path, videoFile: Path) -> bool:
        """Recognise explicit ancillary descriptors without substring false positives."""
        if mediaNameIsAncillary(videoFile.name):
            return True

        stem = videoFile.stem.strip()
        if _ANCILLARY_DESCRIPTOR.fullmatch(stem) or _ANCILLARY_SEGMENT.search(stem):
            return True

        try:
            relativeParts = videoFile.relative_to(movieFolder).parts
        except ValueError:
            return False
        return any(self._isSampleLikeFolder(Path(part)) for part in relativeParts[:-1])
