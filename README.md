# AI Audio Player (Part 1)

Local-first desktop music player with automatic library scanning, metadata extraction, audio analysis, and background processing.

## Stack

- **Frontend:** React + TypeScript + Vite
- **Desktop:** Electron
- **Backend:** Python + FastAPI
- **Database:** SQLite
- **Audio/ML:** librosa, mutagen, scikit-learn, NumPy

## Quick start

### Prerequisites

- Node.js 20+
- Python 3.11+ (3.13 supported)
- Windows/macOS/Linux

### Install

```bash
# Frontend / Electron
npm install

# Python backend
cd backend
python -m pip install -r requirements.txt
cd ..
```

### Development

```bash
# Terminal 1 — Python API
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765

# Terminal 2 — Vite dev server + Electron
npm run electron:dev
```

### Production build

```bash
npm run electron:build
```

## Usage

1. Launch the app
2. Open **Settings → Add folder** and select your music directories
3. Scan runs automatically; songs appear in **Library**
4. Double-click a song or press Play
5. Background analysis extracts audio features and mood scores

## Privacy

- Audio files **never leave your device**
- Optional MusicBrainz enrichment sends only title/artist search queries
- All library data is stored locally in SQLite

## Tests

```bash
npm run test:backend
npm run test:frontend
```

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [DATABASE.md](docs/DATABASE.md)
- [AUDIO_ANALYSIS.md](docs/AUDIO_ANALYSIS.md)
- [METADATA.md](docs/METADATA.md)
- [DEVELOPMENT.md](docs/DEVELOPMENT.md)

## Part 1 status

Phase 1 (functional player) and foundational Phases 2–10 scaffolding are implemented. See acceptance criteria in the project specification.
