# Development Guide

## Environment

```bash
npm install
cd backend && pip install -r requirements.txt
```

## Run backend only

```bash
cd backend
AAP_DATA_DIR=./data python -m uvicorn app.main:app --reload --port 8765
```

Windows PowerShell:

```powershell
$env:AAP_DATA_DIR = ".\data"
python -m uvicorn app.main:app --reload --port 8765
```

## Run full desktop app

```bash
npm run electron:dev
```

## Testing

```bash
cd backend && python -m pytest -v
npm run test:frontend
```

## Key environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AAP_DATA_DIR` | `~/.ai-audio-player/data` | Database, artwork, cache |
| `AAP_ENRICHMENT_ENABLED` | `false` | Enable MusicBrainz |

## Adding a new analysis feature

1. Extract in `app/analysis/audio_analyzer.py`
2. Add column or JSON field in `schema.sql`
3. Include in `feature_vector` builder in `processing/engine.py`
4. Document in `AUDIO_ANALYSIS.md`
5. Add unit test

## Troubleshooting

- **Backend won't start:** ensure port 8765 is free
- **No audio playback:** run via Electron (custom `local-audio://` protocol)
- **librosa install issues:** install ffmpeg; on Windows use prebuilt wheels
