"""CLI regression tests for season-folder normalisation integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import organiseMyVideo.__main__ as applicationMain


def testOrganiseSkipsSeasonNormalisationWhenMockStorageScanHasNoLocations(
    tmp_path: Path,
):
    """CLI tests using a bare MagicMock organizer must not fail in post-processing."""

    organizer = MagicMock()
    organizer.scanStorageLocations.return_value = MagicMock()

    with patch("organiseMyVideo.VideoOrganizer", return_value=organizer):
        status = applicationMain.main(["media", "organise", str(tmp_path)])

    assert status == 0
    organizer.processFiles.assert_called_once_with(interactive=True)
