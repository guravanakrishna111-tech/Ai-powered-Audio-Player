# Architecture

## Overview

```text
Electron shell
├── React UI (Vite)
│   ├── Library views
│   ├── Audio player
│   └── Settings and progress
├── IPC (folder picker, file URLs, backend URL)
└── Python service (FastAPI, child process)
    ├── Library scanner
    ├── Metadata extractor
    ├── Audio analyzer
    ├── Mood estimator
    ├── Metadata enricher
    ├── Feature processor
    ├── Processing engine
    └── SQLite database layer
```

## Communication

| Layer | Protocol |
| --- | --- |
| React <-> FastAPI | HTTP REST (`127.0.0.1:8765`) |
| React <-> Electron | IPC via `contextBridge` |
| Electron <-> Python | Subprocess (`uvicorn`) |
| Playback | `local-audio://` custom protocol |

## Design principles

1. Local-first: playback and recommendations use local data.
2. Incremental processing: unchanged files are skipped via size, mtime, and hash.
3. Background workers: scanning and analysis do not block the UI.
4. Pluggable recommendation: feature vectors and recommendation history are stored locally.

## Part 2 extension points

- `audio_features.feature_vector` for normalized numeric representation
- `audio_features.mood_scores` for probabilistic mood labels
- `song_metadata` and `genres` for categorical features
- `settings.recommendation_normalization_v1` for persisted robust scaling state
- `recommendation_history` for audit trails and future offline evaluation
- `backend/app/recommendation/` for the recommendation service modules

## Directory structure

```text
electron/          Main process, preload, backend lifecycle
src/               React application
backend/
  app/
    api/           REST routes
    db/            SQLite schema + repository
    scanner/       Folder discovery + indexing
    metadata/      Extraction + normalization
    analysis/      librosa features + mood baseline
    enrichment/    MusicBrainz integration
    processing/    Background job engine
    recommendation/ Content-based recommendation service
    services.py
  tests/
docs/
```

