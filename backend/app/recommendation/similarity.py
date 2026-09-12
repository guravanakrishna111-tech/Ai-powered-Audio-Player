from __future__ import annotations

import math
from statistics import mean
from typing import Iterable

import numpy as np

from app.analysis.mood_estimator import MOOD_LABELS
from app.recommendation.models import ScoreBreakdown, SongFeatureVector
from app.recommendation.normalization import RecommendationNormalizer


def cosine_similarity(left: Iterable[float] | None, right: Iterable[float] | None) -> float | None:
    if left is None or right is None:
        return None
    left_array = np.array(list(left), dtype=float)
    right_array = np.array(list(right), dtype=float)
    if left_array.size == 0 or right_array.size == 0 or left_array.size != right_array.size:
        return None
    left_norm = float(np.linalg.norm(left_array))
    right_norm = float(np.linalg.norm(right_array))
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return None
    cosine = float(np.dot(left_array, right_array) / (left_norm * right_norm))
    return max(-1.0, min(1.0, cosine))


def jaccard_similarity(left: Iterable[str] | None, right: Iterable[str] | None) -> float | None:
    if left is None or right is None:
        return None
    left_set = {item for item in left if item}
    right_set = {item for item in right if item}
    if not left_set or not right_set:
        return None
    intersection = left_set & right_set
    union = left_set | right_set
    return len(intersection) / len(union) if union else None


def exact_similarity(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    return 1.0 if left.casefold() == right.casefold() else 0.0


def binary_similarity(left: object | None, right: object | None) -> float | None:
    if left is None or right is None:
        return None
    return 1.0 if left == right else 0.0


def scalar_similarity(
    feature: str,
    left: float | None,
    right: float | None,
    normalizer: RecommendationNormalizer,
    state=None,
) -> float | None:
    if left is None or right is None:
        return None
    if state is None:
        return normalizer.similarity(feature, left, right)
    return normalizer.similarity_with_state(state, feature, left, right)


def mean_similarity(values: Iterable[float | None]) -> float | None:
    collected = [value for value in values if value is not None]
    if not collected:
        return None
    return float(mean(collected))


def key_similarity(left: str | None, right: str | None) -> float | None:
    if not left or not right:
        return None
    left_norm = left.casefold().strip()
    right_norm = right.casefold().strip()
    if left_norm == right_norm:
        return 1.0
    left_root = left_norm.split()[0]
    right_root = right_norm.split()[0]
    if left_root == right_root:
        return 0.5
    return 0.0


def mood_similarity(left: SongFeatureVector, right: SongFeatureVector) -> float | None:
    """Compare mood probability vectors with cosine similarity, clamped to [0, 1].

    Mood vectors are non-negative probability distributions (all values ≥ 0,
    sum ≈ 1). For such vectors the raw cosine is always ≥ 0, so the clamp is
    a safety guard rather than a common correction. It also makes the return
    range consistent with all other similarity functions in this module.
    """
    if not left.mood_scores or not right.mood_scores:
        return None
    left_vector = [float(left.mood_scores.get(label, 0.0)) for label in MOOD_LABELS]
    right_vector = [float(right.mood_scores.get(label, 0.0)) for label in MOOD_LABELS]
    raw = cosine_similarity(left_vector, right_vector)
    if raw is None:
        return None
    return max(0.0, raw)


def audio_similarity(
    left: SongFeatureVector,
    right: SongFeatureVector,
    normalizer: RecommendationNormalizer,
    state=None,
) -> tuple[float | None, dict[str, float | None]]:
    tempo = mean_similarity(
        [
            scalar_similarity("bpm", left.bpm, right.bpm, normalizer, state),
            scalar_similarity("tempo", left.tempo, right.tempo, normalizer, state),
        ]
    )
    energy = mean_similarity(
        [
            scalar_similarity("rms_energy", left.rms_energy, right.rms_energy, normalizer, state),
            scalar_similarity("loudness", left.loudness, right.loudness, normalizer, state),
            scalar_similarity(
                "zero_crossing_rate",
                left.zero_crossing_rate,
                right.zero_crossing_rate,
                normalizer,
                state,
            ),
        ]
    )
    timbre = mean_similarity(
        [
            scalar_similarity(
                "spectral_centroid",
                left.spectral_centroid,
                right.spectral_centroid,
                normalizer,
                state,
            ),
            scalar_similarity(
                "spectral_bandwidth",
                left.spectral_bandwidth,
                right.spectral_bandwidth,
                normalizer,
                state,
            ),
            scalar_similarity(
                "spectral_contrast_mean",
                left.spectral_contrast_mean,
                right.spectral_contrast_mean,
                normalizer,
                state,
            ),
            _vector_cosine(left.mfcc_mean, right.mfcc_mean),
        ]
    )
    harmony = mean_similarity(
        [
            _vector_cosine(left.chroma_mean, right.chroma_mean),
            key_similarity(left.estimated_key, right.estimated_key),
        ]
    )

    components = {
        "tempo": tempo,
        "energy": energy,
        "timbre": timbre,
        "harmony": harmony,
    }
    score = _weighted_average(components, {"tempo": 0.30, "energy": 0.25, "timbre": 0.25, "harmony": 0.20})
    return score, components


def metadata_similarity(left: SongFeatureVector, right: SongFeatureVector) -> tuple[float | None, dict[str, float | None]]:
    artist = binary_similarity(left.artist_id, right.artist_id)
    album = _album_similarity(left, right)
    genre = jaccard_similarity(left.genres, right.genres)
    language = exact_similarity(left.language, right.language)
    other = mean_similarity(
        [
            exact_similarity(_normalize_field(left.composer), _normalize_field(right.composer)),
            _year_similarity(left.album_year, right.album_year),
            _duration_similarity(left.duration, right.duration),
        ]
    )
    components = {
        "artist": artist,
        "album": album,
        "genre": genre,
        "language": language,
        "other": other,
    }
    score = _weighted_average(components, {"artist": 0.24, "album": 0.20, "genre": 0.28, "language": 0.12, "other": 0.16})
    return score, components


def _weighted_average(components: dict[str, float | None], weights: dict[str, float]) -> float | None:
    weighted_sum = 0.0
    active_weight = 0.0
    for name, value in components.items():
        if value is None:
            continue
        weight = weights.get(name, 0.0)
        weighted_sum += float(value) * weight
        active_weight += weight
    if active_weight <= 0:
        return None
    return weighted_sum / active_weight


def _vector_cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float | None:
    """Cosine similarity clamped to [0, 1].

    Raw cosine lives in [-1, 1]. A negative value means the feature vectors
    point in opposite directions (anti-correlated timbre or harmony). For
    *similarity* semantics we treat anti-correlation as zero similarity —
    it provides no positive evidence. Allowing raw negatives to enter
    mean_similarity would silently depress scores and make timbre/harmony
    components misleading.
    """
    raw = cosine_similarity(left, right)
    if raw is None:
        return None
    return max(0.0, raw)


def _normalize_field(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().casefold()


def _album_similarity(left: SongFeatureVector, right: SongFeatureVector) -> float | None:
    if left.album_id is not None and right.album_id is not None:
        if left.album_id == right.album_id:
            return 1.0
        if _normalize_field(left.album_artist) and _normalize_field(right.album_artist):
            if _normalize_field(left.album_artist) == _normalize_field(right.album_artist):
                return 0.35
        return 0.0
    return None


def _year_similarity(left: int | None, right: int | None) -> float | None:
    if left is None or right is None:
        return None
    delta = abs(left - right)
    return float(math.exp(-min(delta, 20) / 6.0))


def _duration_similarity(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    delta = abs(left - right)
    return float(math.exp(-min(delta, 600.0) / 75.0))
