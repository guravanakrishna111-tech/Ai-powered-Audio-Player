# 🎵 AI-Powered Audio Player

A privacy-focused, local-first desktop music player that combines native audio playback with local AI acoustic analysis, mood modeling, and content-based recommendation algorithms.

---

## 📖 Overview: What Does It Do?

**AI-Powered Audio Player** turns your local music collection into an intelligent streaming and discovery experience—without sending any audio or personal listening data to the cloud.

1. **Automatic Library Scanning & Tag Extraction**  
   Discovers audio files across any local directory (or your workspace's `Audio folder`), extracts embedded metadata (artist, title, album, release year, track number, genre), and caches album artwork.
2. **Deep Acoustic Feature Extraction**  
   A background Python processing engine analyzes raw audio signals using digital signal processing to extract:
   - **Rhythm & Tempo**: Beat tracking and BPM estimation.
   - **Energy & Dynamics**: Root-Mean-Square (RMS) energy and loudness levels.
   - **Timbre & Texture**: 13 Mel-Frequency Cepstral Coefficients (MFCCs), spectral centroid (brightness), spectral bandwidth, and zero-crossing rate.
   - **Harmonics & Key**: 12-bin chroma vectors and Krumhansl-Schmuckler musical key detection.
3. **Probabilistic Mood Estimation**  
   Maps acoustic features to high-level emotional dimensions (energetic, calm, happy, sad, intense).
4. **Explainable AI Recommendations**  
   Whenever a song plays, a multi-stage recommendation pipeline compares feature vectors across your entire library using median/IQR robust scaling, cosine similarity, and diversity penalties (preventing artist repetition). Each recommendation surfaces human-readable reason badges, such as:
   - *Similar mood profile*
   - *Similar harmonic profile*
   - *Similar tempo*
   - *Similar track length*
5. **Continuous Smart Playback**  
   When a track finishes, the player automatically queues and plays top-recommended songs from your local collection, creating an endless, personalized radio station from your own files.

---

## 💡 Why Is This Helpful?

- **100% Privacy & Zero Tracking**: Your songs, playlists, and listening habits never leave your computer. There are no subscriptions, ads, or tracking cookies.
- **Rediscover Offline Music Collections**: Perfect for DJs, audiophiles, and collectors who store MP3, FLAC, WAV, and M4A files on local storage or external drives.
- **No Internet Required**: Everything—from audio playback to machine learning feature normalization and recommendation ranking—runs 100% offline.
- **Transparent & Explainable**: Unlike commercial streaming algorithms ("black boxes"), this player reveals exactly *why* a song was recommended based on acoustic similarity.

---

## 🛠️ Technologies Used

### Frontend & Desktop Shell
- **[Electron](https://www.electronjs.org/) (v36)**: Desktop shell providing native OS integration, window management, and hardware audio pipeline.
- **[React](https://react.dev/) (v19) + [TypeScript](https://www.typescriptlang.org/)**: Modular component architecture with strict type safety.
- **[Vite](https://vite.dev/) (v6)**: Lightning-fast frontend tooling and bundling.
- **[Zustand](https://zustand.docs.pmnd.rs/)**: Lightweight, reactive state management for playback queues, volume, seeking, and shuffle/repeat modes.
- **[Lucide React](https://lucide.dev/)**: Modern UI iconography.

### Backend & Machine Learning
- **[Python](https://www.python.org/) (3.11 – 3.13)**: Core backend processing language.
- **[FastAPI](https://fastapi.tiangolo.com/) & [Uvicorn](https://www.uvicorn.org/)**: High-performance asynchronous REST API handling library data and RFC 7233 byte-range audio streaming.
- **[librosa](https://librosa.org/)**: Audio and music signal processing library for extracting tempo, MFCC, chroma, and spectral properties.
- **[mutagen](https://mutagen.readthedocs.io/)**: Metadata tagging library supporting ID3v1, ID3v2, FLAC, MP4, and Vorbis tags.
- **[scikit-learn](https://scikit-learn.org/) & [NumPy](https://numpy.org/)**: Vector operations, cosine similarity, and robust feature normalization.
- **[SQLite](https://www.sqlite.org/)**: Local transactional database storing tracks, albums, artists, acoustic feature vectors, and recommendation audit logs.

---

## 🚀 Local Installation & Setup Guide

### 1. Prerequisites

Ensure the following tools are installed on your machine:
- **Node.js**: `v20.0.0` or higher ([Download Node.js](https://nodejs.org/))
- **Python**: `v3.11` through `v3.13` ([Download Python](https://www.python.org/))
- **Git**: ([Download Git](https://git-scm.com/))
- *(Optional)* **ffmpeg**: Recommended for extended audio format support (`.m4a`, `.aac`).

Verify installations in your terminal:
```bash
node -v
npm -v
python --version
```

---

### 2. Clone the Repository

```bash
git clone https://github.com/your-username/ai-powered-audio-player.git
cd "ai-powered-audio-player"
```

---

### 3. Install Dependencies

#### A. Frontend & Electron Dependencies
From the project root:
```bash
npm install
```

#### B. Python Backend Dependencies
It is recommended to set up a virtual environment:
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

---

### 4. Running the Application

#### Option A: Run Full Desktop App in Development Mode (Recommended)
This command launches the Vite dev server and opens the Electron desktop window:
```bash
npm run electron:dev
```
*The Electron app will automatically launch its background Python service on `http://127.0.0.1:8765`.*

#### Option B: Run Backend and Frontend Separately
If you want to inspect backend logs or run in a standard web browser:

1. **Terminal 1 (Backend API)**:
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
   ```
2. **Terminal 2 (Frontend Web Server)**:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

### 5. Running Tests

Verify that both test suites pass:

```bash
# Run all tests (frontend Vitest + backend Pytest)
npm run test

# Or run separately:
npm run test:frontend
npm run test:backend
```

---

### 6. Packaging & Deployment (Creating Windows `.exe`)

To package the player as a standalone desktop application:

```bash
npm run electron:build
```

After building:
- **Windows Installer**: Located at `release/AI Audio Player Setup 0.1.0.exe` (NSIS installer).
- **Portable Version**: Located at `release/win-unpacked/AI Audio Player.exe` (run directly without installation).

---

## 🎧 Getting Started in the App

1. **Launch the player**: Run `npm run electron:dev` or open the installed app.
2. **Import Songs**:
   - Go to **Settings → Add Folder** and select any folder containing your `.mp3`, `.flac`, `.wav`, or `.m4a` files.
   - Or click **Import "Audio folder"** from the Home/Library screen to scan the workspace sample playlist.
3. **Play Music**: Click on any track to start listening. Use the bottom player bar to seek, adjust volume, toggle shuffle, or cycle repeat modes.
4. **Discover Recommendations**: Open the **Now Playing** tab to view AI-ranked recommendations tailored specifically to the currently playing song.
