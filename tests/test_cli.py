from unittest.mock import patch

import pytest

from organiseMyVideo import __main__ as applicationMain


@pytest.mark.parametrize(
    "arguments",
    [
        ["--debug", "camera", "list"],
        ["camera", "--debug", "list"],
        ["camera", "list", "--debug"],
    ],
)
def testCameraDebugOnlyChangesLogging(arguments):
    import logging

    with patch("organiseMyVideo.cameraCli._cameraListRun", return_value=0) as action:
        with patch.object(applicationMain, "getLogger") as logger:
            assert applicationMain.main(arguments) == 0
    action.assert_called_once_with()
    assert logger.call_args.kwargs["level"] == logging.DEBUG


def testGlobalConfirmationSurvivesCameraSubparser():
    args = applicationMain.buildParser().parse_args(
        ["--confirm", "camera", "scan", "--source", "/tmp"]
    )
    assert args.confirm is True


def testDebugPreservesMediaLocateDispatch():
    from organiseMyVideo.cli import main

    with patch("organiseMyVideo.cli.locateMedia", return_value=[]) as locate:
        assert main(["--debug", "media", "locate", "Example"]) == 1
    locate.assert_called_once_with("Example")
