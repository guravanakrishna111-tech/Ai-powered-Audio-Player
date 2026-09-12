# Audio Analysis

## Purpose

Extract compact numerical features from local audio for future music recommendation.

## Input

- Local audio file path (MP3, FLAC, WAV, M4A, OGG)
- First 90 seconds loaded at 22050 Hz mono (configurable in `audio_analyzer.py`)

## Output

Stored in `audio_features`:

| Feature | Description |
|---------|-------------|
| `bpm` / `tempo` | Beat-tracked tempo |
| `rms_energy` | Root-mean-square energy |
| `loudness` | Log-scaled loudness (dB-like) |
| `spectral_centroid` | Brightness |
| `spectral_bandwidth` | Frequency spread |
| `spectral_contrast_mean` | Harmonic vs noise |
| `zero_crossing_rate` | Noisiness / percussiveness |
| `mfcc_mean` | 13 MFCC means (JSON) |
| `chroma_mean` | 12-bin chroma means (JSON) |
| `estimated_key` | Krumhansl-Schmuckler key |
| `mood_scores` | Probabilistic mood vector (baseline) |
| `feature_vector` | Unified normalized vector for ML |

## Algorithms

### Tempo / BPM
- **librosa.beat.beat_track** — onset strength + dynamic programming
- Assumes quasi-stable tempo in analyzed segment

### MFCC
- Log-mel spectrogram → DCT
- Captures timbral envelope

### Key estimation
- Correlate mean chroma with major/minor key profiles (Krumhansl-Schmuckler)

### Mood (baseline)
- Heuristic mapping from BPM, energy, loudness, ZCR, centroid
- **Not a trained classifier** — documented probabilities only

## Limitations

- Analyzes up to 90s sample, not full track
- Key detection unreliable for atonal / ambient music
- Mood baseline is transparent heuristic, not validated accuracy
- librosa load may fail on corrupt files → job marked failed with retry

## Alternatives (Part 2+)

- Essentia for production-grade descriptors
- Pretrained models (OpenL3, CLAP) for embeddings
- Full-track analysis with streaming feature extraction

## Simplified from-scratch

1. Load PCM samples
2. Compute STFT → magnitude spectrum
3. Mel filterbank → log energies
4. DCT → MFCCs
5. Beat tracking via autocorrelation of onset envelope
