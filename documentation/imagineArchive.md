# Imagine API archive

The `organiseMyVideo.grok.ImagineArchive` Python service generates images and
videos through the official xAI Imagine API, persists them with
`storage_options`, and can list or download those stored files. These API
operations are module functionality rather than public CLI commands.

To retrieve images you already created on grok.com, use
`organiseMyVideo grok --scan`. It imports
your Firefox grok.com session and lists **this login's** Imagine workspace
assets and Imagine conversations. The public explore feed is not downloaded.

The API commands below are for new generations. Create an API key at
[console.x.ai](https://console.x.ai) and export it:

```bash
export XAI_API_KEY="..."
```

Default Imagine URLs expire. This command always sets `storage_options` so the
Files API can list and download the asset later. It only covers media generated
through this application. It does not retrieve images or videos created earlier
in the grok.com gallery.

## Python API

Generation is a paid API call. Constructing the service with `dryRun=True` is
the safe default; pass `dryRun=False` to execute downloads or generation.

```python
from organiseMyVideo.grok import ImagineArchive

archive = ImagineArchive(dryRun=False)
image = archive.imageGenerate("a quiet harbour at dusk")
video = archive.videoGenerate("slow pan across the harbour", duration=10)
files = archive.fileList()
stats = archive.fileDownload()
```

## Local files

| Path | Purpose |
| --- | --- |
| `~/.config/organiseMyVideo/grokCatalog.json` | Prompt, model, kind, and `file_id` for generations from this app |
| `~/Downloads/Grok/` | Downloaded images and videos |

`fileList()` reads the Files API and returns stored image and video files. Other
file types in the same xAI team are omitted.

## Models

| Kind | Model |
| --- | --- |
| image | `grok-imagine-image-2.0` |
| video | `grok-imagine-video-1.5` |

Video duration is 1–15 seconds and defaults to 6.
