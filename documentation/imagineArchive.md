# Imagine API archive

`organiseMyVideo grok` generates images and videos through the official xAI
Imagine API, always persists them with `storage_options`, then lists and
downloads those stored files.

To retrieve images you already created on grok.com, use `--grok`. It imports
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

## Commands

Generate is a paid API call. Dry-run is the default; add `--confirm` to execute.

```bash
python -m organiseMyVideo grok generate "a quiet harbour at dusk"
python -m organiseMyVideo grok generate "a quiet harbour at dusk" --confirm
python -m organiseMyVideo grok generate "slow pan across the harbour" --kind video --confirm
python -m organiseMyVideo grok generate "slow pan" --kind video --image ./harbour.jpg --confirm
python -m organiseMyVideo grok list
python -m organiseMyVideo grok download
python -m organiseMyVideo grok download --confirm
python -m organiseMyVideo grok download --file-id file_abc --confirm
```

`--confirm` may be placed before or after `grok`.

## Local files

| Path | Purpose |
| --- | --- |
| `~/.config/organiseMyVideo/grokCatalog.json` | Prompt, model, kind, and `file_id` for generations from this app |
| `~/Downloads/Grok/` | Downloaded images and videos |

`grok list` reads the Files API and shows stored image and video files. Other
file types in the same xAI team are omitted.

## Models

| Kind | Model |
| --- | --- |
| image | `grok-imagine-image-2.0` |
| video | `grok-imagine-video-1.5` |

Video duration is 1–15 seconds and defaults to 6.
