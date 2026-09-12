"""Baseline mood estimation from audio features.

This is a transparent heuristic baseline — not a trained classifier.
Probabilities are derived from normalized feature mappings and should
not be interpreted as ground-truth mood labels.
"""

import json
from typing import Any


MOOD_LABELS = [
    "romantic", "sad", "happy", "calm", "energetic",
    "party", "melancholic", "peaceful", "motivational",
]


def estimate_mood_scores(features: dict[str, Any]) -> dict[str, float]:
    bpm = float(features.get("bpm") or 120)
    energy = float(features.get("rms_energy") or 0.05)
    loudness = float(features.get("loudness") or -20)
    zcr = float(features.get("zero_crossing_rate") or 0.05)
    centroid = float(features.get("spectral_centroid") or 2000)

    def clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    scores = {
        "energetic": clamp((bpm - 80) / 80) * clamp(energy * 15),
        "party": clamp((bpm - 100) / 70) * clamp((loudness + 30) / 30),
        "calm": clamp(1 - (bpm - 60) / 100) * clamp(1 - energy * 20),
        "peaceful": clamp(1 - zcr * 10) * clamp(1 - (centroid / 4000)),
        "sad": clamp(1 - (bpm / 140)) * clamp(1 - (loudness + 15) / 25),
        "melancholic": clamp(1 - (bpm / 130)) * clamp(centroid / 3500) * 0.7,
        "happy": clamp((bpm - 90) / 80) * clamp((loudness + 25) / 35) * clamp(energy * 10),
        "romantic": clamp(1 - abs(bpm - 85) / 85) * clamp(1 - zcr * 8) * 0.8,
        "motivational": clamp((bpm - 110) / 60) * clamp(energy * 12) * clamp((loudness + 20) / 30),
    }

    total = sum(scores.values()) or 1.0
    return {label: round(scores[label] / total, 4) for label in MOOD_LABELS}


def mood_scores_to_json(features: dict[str, Any]) -> str:
    return json.dumps(estimate_mood_scores(features))
