"""Tests for the official Imagine API archive commands."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import organiseMyVideo.__main__ as omv_main
from organiseMyVideo.grok import ImagineArchive, grokCommandRun
from organiseMyVideo import constants


class FakeFileOutput:
    def __init__(self, file_id: str, filename: str):
        self.file_id = file_id
        self.filename = filename


class FakeGenerateResponse:
    def __init__(self, file_id: str, filename: str, storage_error=None):
        self.file_output = FakeFileOutput(file_id, filename)
        self.storage_error = storage_error


class FakeListResponse:
    def __init__(self, data, pagination_token=None):
        self.data = data
        self.pagination_token = pagination_token


class FakeFiles:
    def __init__(self, pages, contents=None):
        self.pages = list(pages)
        self.contents = contents or {}
        self.listCalls = []
        self.contentCalls = []

    def list(self, **kwargs):
        self.listCalls.append(kwargs)
        if not self.pages:
            return FakeListResponse([])
        return self.pages.pop(0)

    def content(self, file_id):
        self.contentCalls.append(file_id)
        return self.contents[file_id]


class FakeClient:
    def __init__(self, files=None, imageResponse=None, videoResponse=None):
        self.files = files or FakeFiles([])
        self.image = MagicMock()
        self.video = MagicMock()
        if imageResponse is not None:
            self.image.sample.return_value = imageResponse
        if videoResponse is not None:
            self.video.generate.return_value = videoResponse


def _mediaFile(fileId, filename, contentType, size=12):
    return SimpleNamespace(
        id=fileId,
        filename=filename,
        size=size,
        content_type=contentType,
        created_at="2026-08-23T00:00:00Z",
    )


def testGenerateFailsFastWithoutApiKey(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    archive = ImagineArchive(dryRun=True)

    with pytest.raises(RuntimeError, match="XAI_API_KEY"):
        archive.imageGenerate("a quiet harbour")


def testGenerateDryRunDoesNotCallApiOrWriteCatalog(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    client = FakeClient(
        imageResponse=FakeGenerateResponse("file_1", "harbour.jpg"),
    )
    catalog = tmp_path / "grokCatalog.json"
    archive = ImagineArchive(
        dryRun=True,
        client=client,
        catalogPath=catalog,
    )

    record = archive.imageGenerate("a quiet harbour", filename="harbour.jpg")

    assert record["fileId"] == ""
    assert record["filename"] == "harbour.jpg"
    client.image.sample.assert_not_called()
    assert not catalog.exists()


def testGenerateConfirmPersistsStorageOptionsAndCatalog(tmp_path):
    client = FakeClient(
        imageResponse=FakeGenerateResponse("file_harbour", "harbour.jpg"),
    )
    catalog = tmp_path / "grokCatalog.json"
    archive = ImagineArchive(
        dryRun=False,
        client=client,
        catalogPath=catalog,
    )

    record = archive.imageGenerate("a quiet harbour", filename="harbour.jpg")

    assert record["fileId"] == "file_harbour"
    client.image.sample.assert_called_once()
    kwargs = client.image.sample.call_args.kwargs
    assert kwargs["prompt"] == "a quiet harbour"
    assert kwargs["model"] == constants.GROK_IMAGE_MODEL
    assert kwargs["storage_options"] == {"filename": "harbour.jpg"}
    saved = catalog.read_text(encoding="utf-8")
    assert "file_harbour" in saved
    assert "a quiet harbour" in saved


def testGenerateVideoUsesVideoModel(tmp_path):
    client = FakeClient(
        videoResponse=FakeGenerateResponse("file_clip", "harbour.mp4"),
    )
    archive = ImagineArchive(
        dryRun=False,
        client=client,
        catalogPath=tmp_path / "grokCatalog.json",
    )

    record = archive.videoGenerate("slow pan", filename="harbour.mp4", duration=8)

    assert record["fileId"] == "file_clip"
    kwargs = client.video.generate.call_args.kwargs
    assert kwargs["model"] == constants.GROK_VIDEO_MODEL
    assert kwargs["duration"] == 8
    assert kwargs["storage_options"] == {"filename": "harbour.mp4"}
    client.image.sample.assert_not_called()


def testFileListOmitsNonMediaAndPaginates():
    firstPage = FakeListResponse(
        [
            _mediaFile("file_img", "harbour.jpg", "image/jpeg"),
            _mediaFile("file_doc", "notes.pdf", "application/pdf"),
        ],
        pagination_token="next",
    )
    secondPage = FakeListResponse(
        [
            _mediaFile("file_vid", "harbour.mp4", "video/mp4"),
        ]
    )
    client = FakeClient(files=FakeFiles([firstPage, secondPage]))
    archive = ImagineArchive(dryRun=True, client=client, pageSize=2)

    records = archive.fileList()

    assert [item["fileId"] for item in records] == ["file_img", "file_vid"]
    assert len(client.files.listCalls) == 2
    assert client.files.listCalls[1]["pagination_token"] == "next"


def testDownloadDryRunDoesNotWriteFiles(tmp_path):
    listed = FakeListResponse([_mediaFile("file_img", "harbour.jpg", "image/jpeg")])
    client = FakeClient(
        files=FakeFiles([listed], contents={"file_img": b"jpeg-bytes"}),
    )
    downloadDir = tmp_path / "Grok"
    archive = ImagineArchive(
        dryRun=True,
        client=client,
        downloadDir=downloadDir,
    )

    stats = archive.fileDownload()

    assert stats["downloaded"] == 1
    assert not downloadDir.exists()
    assert client.files.contentCalls == []


def testDownloadConfirmWritesAndSkipsExisting(tmp_path):
    listed = FakeListResponse(
        [
            _mediaFile("file_img", "harbour.jpg", "image/jpeg"),
            _mediaFile("file_vid", "harbour.mp4", "video/mp4"),
        ]
    )
    client = FakeClient(
        files=FakeFiles(
            [listed],
            contents={
                "file_img": b"jpeg-bytes",
                "file_vid": b"mp4-bytes",
            },
        )
    )
    downloadDir = tmp_path / "Grok"
    downloadDir.mkdir()
    (downloadDir / "harbour.jpg").write_bytes(b"already-there")
    archive = ImagineArchive(
        dryRun=False,
        client=client,
        catalogPath=tmp_path / "grokCatalog.json",
        downloadDir=downloadDir,
    )

    stats = archive.fileDownload()

    assert stats["skipped"] == 1
    assert stats["downloaded"] == 1
    assert (downloadDir / "harbour.mp4").read_bytes() == b"mp4-bytes"
    assert (downloadDir / "harbour.jpg").read_bytes() == b"already-there"
    assert client.files.contentCalls == ["file_vid"]


def testHelpListsGrokSubcommand(capsys):
    with patch("sys.argv", ["organiseMyVideo", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            omv_main.main()

    assert exc_info.value.code == 0
    assert "grok" in capsys.readouterr().out


def testMainGrokGenerateDryRunDispatches(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    archive = MagicMock()
    archive.imageGenerate.return_value = {
        "fileId": "",
        "filename": "harbour.jpg",
    }

    with patch("organiseMyVideo.grok.ImagineArchive", return_value=archive):
        with patch(
            "sys.argv",
            ["organiseMyVideo", "grok", "generate", "a quiet harbour"],
        ):
            omv_main.main()

    archive.imageGenerate.assert_called_once()
    kwargs = archive.imageGenerate.call_args.kwargs
    assert kwargs["prompt"] == "a quiet harbour"


def testMainGrokGenerateConfirmUsesVideoKind():
    archive = MagicMock()
    archive.videoGenerate.return_value = {
        "fileId": "file_clip",
        "filename": "clip.mp4",
    }

    with patch("organiseMyVideo.grok.ImagineArchive", return_value=archive):
        with patch(
            "sys.argv",
            [
                "organiseMyVideo",
                "--confirm",
                "grok",
                "generate",
                "slow pan",
                "--kind",
                "video",
                "--duration",
                "10",
            ],
        ):
            omv_main.main()

    archive.videoGenerate.assert_called_once()
    kwargs = archive.videoGenerate.call_args.kwargs
    assert kwargs["prompt"] == "slow pan"
    assert kwargs["duration"] == 10


def testGrokCommandRunUnknownAction():
    with pytest.raises(RuntimeError, match="unknown grok action"):
        grokCommandRun(SimpleNamespace(grokAction="explode"), dryRun=True)
