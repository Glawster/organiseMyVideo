"""Tests for the camera-card inventory list display."""

from organiseMyVideo.cameraInventoryList import (
    ANSI_GREEN,
    ANSI_RED,
    ANSI_RESET,
    CameraInventoryListRecord,
    cameraInventoryListSummary,
)


def _record(*, contentBytes: int, archived: bool) -> CameraInventoryListRecord:
    """Return one representative list row."""

    return CameraInventoryListRecord(
        cardId=17,
        inventoriedAt="2026-09-16T10:00:00+00:00",
        cardBrand="Transcend",
        cardRatedGigabytes=16,
        freeBytes=500 * 1024 * 1024,
        contentBytes=contentBytes,
        volumeKind="sd",
        snapshotId="snapshot-17" if archived else None,
        archived=archived,
    )


def testCameraInventoryListColoursEmptyCardsGreen() -> None:
    """Empty cards are green and retain an explicit EMPTY status."""

    summary = cameraInventoryListSummary(
        (_record(contentBytes=0, archived=False),),
        useColour=True,
    )

    assert "EMPTY" in summary
    assert ANSI_GREEN in summary
    assert ANSI_RED not in summary
    assert ANSI_RESET in summary


def testCameraInventoryListColoursArchivedCardsRed() -> None:
    """Archived cards are red and retain an explicit ARCHIVED status."""

    summary = cameraInventoryListSummary(
        (_record(contentBytes=1024, archived=True),),
        useColour=True,
    )

    assert "ARCHIVED" in summary
    assert ANSI_RED in summary
    assert ANSI_GREEN not in summary
    assert ANSI_RESET in summary


def testCameraInventoryListEmptyTakesPrecedenceOverArchived() -> None:
    """A cleared reusable card is shown as empty even after an earlier archive."""

    summary = cameraInventoryListSummary(
        (_record(contentBytes=0, archived=True),),
        useColour=True,
    )

    assert "EMPTY" in summary
    assert "ARCHIVED" not in summary
    assert ANSI_GREEN in summary
    assert ANSI_RED not in summary


def testCameraInventoryListKeepsStatusWithoutTerminalColour() -> None:
    """Redirected output remains useful without ANSI escape sequences."""

    summary = cameraInventoryListSummary(
        (
            _record(contentBytes=0, archived=False),
            _record(contentBytes=1024, archived=True),
        ),
        useColour=False,
    )

    assert "EMPTY" in summary
    assert "ARCHIVED" in summary
    assert "\033[" not in summary
