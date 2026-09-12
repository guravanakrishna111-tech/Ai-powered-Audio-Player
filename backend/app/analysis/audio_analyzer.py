import json
import logging
from pathlib import Path

import librosa
import numpy as np

logger = logging.getLogger(__name__)

ANALYZER_VERSION = "0.1.0"


def analyze_audio(file_path: Path, duration_limit: float = 90.0) -> dict:
    """Extract compact audio features suitable for future recommendation."""
    y, sr = librosa.load(str(file_path), sr=22050, mono=True, duration=duration_limit)

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])

    rms = librosa.feature.rms(y=y)[0]
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)

    loudness = float(20 * np.log10(np.mean(rms) + 1e-9))

    key, key_confidence = _estimate_key(chroma)

    return {
        "bpm": bpm,
        "tempo": bpm,
        "rms_energy": float(np.mean(rms)),
        "loudness": loudness,
        "spectral_centroid": float(np.mean(spectral_centroid)),
        "spectral_bandwidth": float(np.mean(spectral_bandwidth)),
        "spectral_contrast_mean": float(np.mean(spectral_contrast)),
        "zero_crossing_rate": float(np.mean(zcr)),
        "mfcc_mean": json.dumps(np.mean(mfcc, axis=1).tolist()),
        "chroma_mean": json.dumps(np.mean(chroma, axis=1).tolist()),
        "estimated_key": key,
        "key_confidence": key_confidence,
        "analyzer_version": ANALYZER_VERSION,
    }


def _estimate_key(chroma: np.ndarray) -> tuple[str | None, float | None]:
    """Simple Krumhansl-Schmuckler key estimation baseline."""
    try:
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        chroma_mean = np.mean(chroma, axis=1)
        if np.sum(chroma_mean) <= 0:
            return None, None

        keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        best_key = None
        best_corr = -1.0
        for i, name in enumerate(keys):
            rotated = np.roll(chroma_mean, -i)
            for mode, profile in [(" major", major_profile), (" minor", minor_profile)]:
                corr = float(np.corrcoef(rotated, profile)[0, 1])
                if corr > best_corr:
                    best_corr = corr
                    best_key = name + mode
        return best_key, best_corr
    except Exception as exc:
        logger.debug("Key estimation failed: %s", exc)
        return None, None
