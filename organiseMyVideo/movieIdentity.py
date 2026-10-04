"""Decide whether a proposed movie title and year may rename the copy on disk.

A folder or filename that already names a film is kept when metadata names a
different film or a different release year. Punctuation, spacing, a leading or
trailing ``The``, and a capitalisation upgrade remain ordinary tidy-ups.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

MOVIE_IDENTITY_ABSENT = "absent"
MOVIE_IDENTITY_AGREE = "agree"
MOVIE_IDENTITY_CONFLICT = "conflict"
MOVIE_IDENTITY_PRESERVE_CASE = "preserve-case"

# Keys used only while a rename is being considered. They must not be stored
# in the metadata library or written into movie.xml.
MOVIE_IDENTITY_STATE_KEYS = (
    "identityConflict",
    "identityConflictReported",
    "identityNamingTitle",
)

_APOSTROPHE_PATTERN = re.compile(r"['\u2019]")
_NON_IDENTITY_PATTERN = re.compile(r"[^0-9a-z]+")
_PATH_LIKE_TITLE_PATTERN = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")


@dataclass(frozen=True)
class MovieIdentityDecision:
    """Comparison of one on-disk movie label with the proposed metadata."""

    kind: str
    currentTitle: Optional[str] = None
    currentYear: Optional[str] = None
    proposedTitle: Optional[str] = None
    proposedYear: Optional[str] = None
    retainedTitle: Optional[str] = None


def movieIdentityClassify(
    currentTitle: object,
    currentYear: object,
    proposedTitle: object,
    proposedYear: object,
) -> MovieIdentityDecision:
    """Return whether *currentTitle* may be replaced by *proposedTitle*.

    ``absent`` means this label does not already name a film, so the caller
    keeps today's repair behaviour. ``agree`` allows punctuation and article
    tidy-up. ``preserve-case`` keeps the on-disk capitals. ``conflict`` blocks
    the rename.
    """
    currentTitleText = _displayText(currentTitle)
    proposedTitleText = _displayText(proposedTitle)
    currentYearText = _yearText(currentYear)
    proposedYearText = _yearText(proposedYear)
    empty = MovieIdentityDecision(
        MOVIE_IDENTITY_ABSENT,
        currentTitle=currentTitleText,
        currentYear=currentYearText,
        proposedTitle=proposedTitleText,
        proposedYear=proposedYearText,
    )
    if not currentTitleText or not proposedTitleText:
        return empty

    currentIdentity = movieTitleIdentity(currentTitleText)
    proposedIdentity = movieTitleIdentity(proposedTitleText)
    if not currentIdentity or not proposedIdentity:
        return empty

    if currentIdentity != proposedIdentity or (
        currentYearText is not None
        and proposedYearText is not None
        and currentYearText != proposedYearText
    ):
        return MovieIdentityDecision(
            MOVIE_IDENTITY_CONFLICT,
            currentTitle=currentTitleText,
            currentYear=currentYearText,
            proposedTitle=proposedTitleText,
            proposedYear=proposedYearText,
        )

    if _capitalisationDowngrade(currentTitleText, proposedTitleText):
        return MovieIdentityDecision(
            MOVIE_IDENTITY_PRESERVE_CASE,
            currentTitle=currentTitleText,
            currentYear=currentYearText,
            proposedTitle=proposedTitleText,
            proposedYear=proposedYearText,
            retainedTitle=currentTitleText,
        )

    return MovieIdentityDecision(
        MOVIE_IDENTITY_AGREE,
        currentTitle=currentTitleText,
        currentYear=currentYearText,
        proposedTitle=proposedTitleText,
        proposedYear=proposedYearText,
    )


def movieIdentityClassifySources(
    sources: Sequence[tuple[object, object]],
    proposedTitle: object,
    proposedYear: object,
) -> MovieIdentityDecision:
    """Classify *sources* in order and let a conflict win."""
    established = []
    for currentTitle, currentYear in sources:
        decision = movieIdentityClassify(
            currentTitle, currentYear, proposedTitle, proposedYear
        )
        if decision.kind != MOVIE_IDENTITY_ABSENT:
            established.append(decision)
    if not established:
        return movieIdentityClassify(None, None, proposedTitle, proposedYear)
    for decision in established:
        if decision.kind == MOVIE_IDENTITY_CONFLICT:
            return decision
    for decision in established:
        if decision.kind == MOVIE_IDENTITY_PRESERVE_CASE:
            return decision
    return established[0]


def movieIdentityMetadataSuspectReasons(
    title: object,
    *,
    metadataRuntime: object = None,
    mediaRuntime: object = None,
) -> tuple[str, ...]:
    """Return reasons why metadata should not be trusted as movie identity."""
    reasons = []
    titleText = _displayText(title)
    if titleText and _PATH_LIKE_TITLE_PATTERN.match(titleText):
        reasons.append("metadata title contains a filesystem path")

    metadataMinutes = _runtimeMinutes(metadataRuntime)
    mediaMinutes = _runtimeMinutes(mediaRuntime)
    if metadataMinutes is not None and mediaMinutes is not None and mediaMinutes > 0:
        difference = abs(metadataMinutes - mediaMinutes)
        if difference >= 15 and difference / mediaMinutes >= 0.25:
            reasons.append("metadata runtime conflicts materially with media runtime")

    return tuple(reasons)


def movieIdentityEvidence(movieInfo: Mapping[str, object]) -> str:
    """Return the local source that supplied the proposed movie identity."""
    source = movieInfo.get("metadataSource")
    if source == "mcm":
        return "movie.xml"
    if isinstance(source, str) and source.strip():
        return source.strip()
    return "metadata"


def movieIdentityNamingTitle(movieInfo: Mapping[str, object]) -> Optional[str]:
    """Return the title a folder or file rename should use."""
    for key in ("identityNamingTitle", "title"):
        text = _displayText(movieInfo.get(key))
        if text:
            return text
    return None


def movieIdentityReport(
    decision: MovieIdentityDecision,
    *,
    evidence: str,
    imdbId: object = None,
    tmdbId: object = None,
    runtime: object = None,
    mediaRuntime: object = None,
) -> str:
    """Return the operator-facing conflict report."""
    suspectReasons = movieIdentityMetadataSuspectReasons(
        decision.proposedTitle,
        metadataRuntime=runtime,
        mediaRuntime=mediaRuntime,
    )
    heading = (
        "movie metadata identity suspect" if suspectReasons else "movie identity conflict"
    )
    lines = [
        heading,
        f"current: {_movieIdentityLabel(decision.currentTitle, decision.currentYear)}",
        f"proposed: {_movieIdentityLabel(decision.proposedTitle, decision.proposedYear)}",
        f"evidence: {evidence}",
    ]
    for reason in suspectReasons:
        lines.append(f"reason: {reason}")
    for label, value in (("imdb", imdbId), ("tmdb", tmdbId)):
        text = _displayText(value)
        if text:
            lines.append(f"{label}: {text}")
    runtimeText = _displayText(runtime)
    if runtimeText:
        label = "metadata runtime" if mediaRuntime is not None else "runtime"
        lines.append(f"{label}: {runtimeText}")
    mediaRuntimeText = _displayText(mediaRuntime)
    if mediaRuntimeText:
        lines.append(f"media runtime: {mediaRuntimeText}")
    return "\n".join(lines)


def movieTitleIdentity(title: str) -> str:
    """Return a key that ignores case, punctuation, spacing, and outer The."""
    text = _APOSTROPHE_PATTERN.sub("", title.casefold())
    text = _NON_IDENTITY_PATTERN.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    if text.endswith(" the"):
        text = text[:-4]
    return text.strip()


def _identityLetters(text: str) -> str:
    """Return the letters in *text*, ignoring punctuation and digits."""
    return "".join(character for character in text if character.isalpha())


def _capitalisationDowngrade(current: str, proposed: str) -> bool:
    """Return True when *proposed* would lowercase a capital already on disk."""
    currentLetters = _identityLetters(current)
    proposedLetters = _identityLetters(proposed)
    if currentLetters.casefold() != proposedLetters.casefold():
        return False
    if len(currentLetters) != len(proposedLetters):
        return sum(character.isupper() for character in currentLetters) > sum(
            character.isupper() for character in proposedLetters
        )
    return any(
        currentCharacter.isupper() and proposedCharacter.islower()
        for currentCharacter, proposedCharacter in zip(currentLetters, proposedLetters)
    )


def _displayText(value: object) -> Optional[str]:
    """Return a stripped string, or None when *value* is empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _movieIdentityLabel(title: Optional[str], year: Optional[str]) -> str:
    """Return ``Title (Year)`` without duplicating an embedded matching year."""
    if title and year:
        embeddedYear = re.search(r"\((\d{4})\)\s*$", title)
        if embeddedYear and embeddedYear.group(1) == str(year):
            return title
        return f"{title} ({year})"
    return title or ""


def _runtimeMinutes(value: object) -> Optional[float]:
    """Return a numeric runtime in minutes when *value* begins with a number."""
    text = _displayText(value)
    if text is None:
        return None
    match = re.match(r"^\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _yearText(value: object) -> Optional[str]:
    """Return a release year, treating the unknown-year sentinel as absent."""
    text = _displayText(value)
    if text is None or text.casefold() == "unknown":
        return None
    return text
