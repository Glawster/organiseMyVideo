"""REQ-035 review fixes for suspect movie metadata and ancillary matching."""

from __future__ import annotations

import glob
import re
from pathlib import Path

from organiseMyProjects.logUtils import getLogger  # type: ignore

from .constants import VIDEO_EXTENSIONS
from .incomingNames import mediaNameIsAncillary
from .movieIdentity import (
    MOVIE_IDENTITY_CONFLICT,
    movieFeatureLengthShort,
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
    rf"(?=$|\s*(?:[-–—._\[\]()]+|\(\d{{4}}\)))",
    re.IGNORECASE,
)


class MovieIdentityReviewMixin:
    """Tighten REQ-035 identity evidence without changing general scan policy."""

    def _movieTechnicalRuntimeMinutes(self, *paths: Path) -> str | None:
        """Return actual feature runtime in minutes when a video can be probed."""
        from organiseMediaStudio.video.errors import VideoProcessingError
        from organiseMediaStudio.video.probe import videoProbe

        try:
            videoFile = self._movieFeatureFile(*paths)
        except OSError:
            return None
        if videoFile is None:
            return None
        # The guard runs before and after enrichment; probe each file once.
        cache = self.__dict__.setdefault("_movieFeatureRuntimeCache", {})
        if videoFile in cache:
            return cache[videoFile]
        try:
            durationSeconds = videoProbe(videoFile).durationSeconds
        except (OSError, VideoProcessingError):
            durationSeconds = None
        runtime = None
        if durationSeconds is not None and durationSeconds > 0:
            runtime = f"{durationSeconds / 60.0:.1f}".rstrip("0").rstrip(".")
        cache[videoFile] = runtime
        return runtime

    def _movieFeatureFile(self, *paths: Path) -> Path | None:
        """Return the largest video among *paths* and their same-named siblings.

        Only same-named siblings are considered, because a file's parent can be
        a staging folder holding unrelated films.
        """
        videoFiles = [
            Path(path)
            for path in paths
            if Path(path).is_file() and Path(path).suffix.casefold() in VIDEO_EXTENSIONS
        ]
        candidates = set(videoFiles)
        for videoFile in videoFiles:
            candidates.update(
                sibling
                for sibling in videoFile.parent.glob(f"{glob.escape(videoFile.stem)}.*")
                if sibling.is_file() and sibling.suffix.casefold() in VIDEO_EXTENSIONS
            )
        return max(
            candidates, key=lambda path: (path.stat().st_size, str(path)), default=None
        )

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
        """Block suspect MCM evidence before ordinary identity comparison.

        A path-like title blocks even when the normalised identity agrees. A
        runtime that differs from the feature only adds evidence to a real
        title or year conflict; on its own it says nothing about identity, so
        a feature much shorter than its metadata is reported as possibly
        incomplete instead.
        """
        if movieInfo.get("metadataSource") != "mcm":
            return super()._refuseMovieIdentityChange(movieInfo, *paths)

        mediaRuntime = movieInfo.get("mediaRuntime")
        if movieInfo.get("runtime") and mediaRuntime is None:
            mediaRuntime = self._movieTechnicalRuntimeMinutes(*paths)
        if mediaRuntime is not None:
            movieInfo["mediaRuntime"] = mediaRuntime

        if movieIdentityMetadataSuspectReasons(movieInfo.get("title")):
            if not movieInfo.get("identityConflict"):
                movieInfo["identityConflict"] = self._movieIdentityDecisionForPaths(
                    movieInfo, *paths
                )
            if not movieInfo.get("identityConflictReported"):
                self._reportMovieIdentityConflict(movieInfo, *paths)
                movieInfo["identityConflictReported"] = True
            return True

        decision = self._movieIdentityDecisionForPaths(movieInfo, *paths)
        if decision.kind != MOVIE_IDENTITY_CONFLICT and movieFeatureLengthShort(
            movieInfo.get("runtime"), mediaRuntime
        ):
            self._reportShortMovieFeature(movieInfo, *paths)

        return super()._refuseMovieIdentityChange(movieInfo, *paths)

    def _reportShortMovieFeature(self, movieInfo: dict, *paths: Path) -> None:
        """Warn once that a feature is much shorter than its metadata runtime."""
        feature = self._movieFeatureFile(*paths)
        reported = self.__dict__.setdefault("_shortMovieFeaturesReported", set())
        if feature in reported:
            return
        reported.add(feature)
        details = [
            f"folder: {feature.parent}" if feature is not None else "",
            f"file: {feature.name}" if feature is not None else "",
            f"metadata runtime: {movieInfo.get('runtime')}",
            f"media runtime: {movieInfo.get('mediaRuntime')}",
            "reason: the feature is much shorter than its metadata runtime",
        ]
        details = [detail for detail in details if detail]
        logger.warning("%s", "\n".join(["movie file possibly incomplete", *details]))
        self._recordSummaryInvestigation("movie file possibly incomplete", *details)

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
