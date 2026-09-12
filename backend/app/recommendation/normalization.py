from __future__ import annotations

import json
import math
import time
from dataclasses import asdict
from typing import Iterable

import numpy as np

from app.db.connection import Database
from app.recommendation.config import NORMALIZATION_STATE_KEY
from app.recommendation.models import FeatureScale, NormalizationState


NUMERIC_FEATURES = (
    "bpm",
    "tempo",
    "rms_energy",
    "loudness",
    "spectral_centroid",
    "spectral_bandwidth",
    "spectral_contrast_mean",
    "zero_crossing_rate",
    "duration",
    "album_year",
)

FALLBACK_SCALES = {
    "bpm": 12.0,
    "tempo": 12.0,
    "rms_energy": 0.08,
    "loudness": 6.0,
    "spectral_centroid": 800.0,
    "spectral_bandwidth": 600.0,
    "spectral_contrast_mean": 2.0,
    "zero_crossing_rate": 0.05,
    "duration": 60.0,
    "album_year": 5.0,
}


class RecommendationNormalizer:
    def __init__(self, database: Database) -> None:
        self.db = database
        self._state: NormalizationState | None = None

    def load(self, refresh: bool = False) -> NormalizationState:
        if not refresh and self._state is not None and not self._is_stale(self._state):
            return self._state

        if not refresh:
            row = self.db.fetchone("SELECT value FROM settings WHERE key = ?", (NORMALIZATION_STATE_KEY,))
            if row:
                state = self._from_json(row["value"])
                if not self._is_stale(state):
                    self._state = state
                    return state

        state = self.fit()
        self.save(state)
        self._state = state
        return state

    def fit(self) -> NormalizationState:
        rows = self.db.fetchall(
            """
            SELECT
                s.duration,
                al.year AS album_year,
                af.bpm, af.tempo, af.rms_energy, af.loudness,
                af.spectral_centroid, af.spectral_bandwidth,
                af.spectral_contrast_mean, af.zero_crossing_rate
            FROM songs s
            LEFT JOIN albums al ON al.id = s.album_id
            JOIN audio_features af ON af.song_id = s.id
            WHERE s.is_missing = 0
            """
        )

        values: dict[str, list[float]] = {name: [] for name in NUMERIC_FEATURES}
        for row in rows:
            for feature in NUMERIC_FEATURES:
                value = row["album_year"] if feature == "album_year" else row[feature]
                if value is not None:
                    values[feature].append(float(value))

        feature_scales = {
            feature: self._build_scale(samples)
            for feature, samples in values.items()
            if samples
        }
        source_song_count = self._scalar_count("SELECT COUNT(*) AS c FROM songs WHERE is_missing = 0")
        analyzed_song_count = len(rows)

        return NormalizationState(
            version="robust-median-iqr-v1",
            source_song_count=source_song_count,
            analyzed_song_count=analyzed_song_count,
            feature_scales=feature_scales,
            updated_at=time.time(),
        )

    def save(self, state: NormalizationState) -> None:
        self.db.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (NORMALIZATION_STATE_KEY, self._to_json(state), state.updated_at),
        )

    def scale(self, feature: str, value: float | None) -> float | None:
        state = self.load()
        return self.scale_with_state(state, feature, value)

    def scale_with_state(
        self,
        state: NormalizationState,
        feature: str,
        value: float | None,
    ) -> float | None:
        if value is None:
            return None
        scale = state.feature_scales.get(feature)
        if not scale:
            return None
        denom = scale.iqr if abs(scale.iqr) > 1e-9 else FALLBACK_SCALES.get(feature, 1.0)
        if denom == 0:
            denom = 1.0
        return (float(value) - scale.median) / denom

    def similarity(self, feature: str, left: float | None, right: float | None) -> float | None:
        state = self.load()
        return self.similarity_with_state(state, feature, left, right)

    def similarity_with_state(
        self,
        state: NormalizationState,
        feature: str,
        left: float | None,
        right: float | None,
    ) -> float | None:
        left_scaled = self.scale_with_state(state, feature, left)
        right_scaled = self.scale_with_state(state, feature, right)
        if left_scaled is None or right_scaled is None:
            return None
        delta = abs(left_scaled - right_scaled)
        return float(math.exp(-min(delta, 8.0)))

    def _is_stale(self, state: NormalizationState) -> bool:
        current_source_count = self._scalar_count("SELECT COUNT(*) AS c FROM songs WHERE is_missing = 0")
        current_analyzed_count = self._scalar_count("SELECT COUNT(*) AS c FROM audio_features")
        return (
            state.source_song_count != current_source_count
            or state.analyzed_song_count != current_analyzed_count
        )

    def _scalar_count(self, sql: str) -> int:
        row = self.db.fetchone(sql)
        return int(row["c"]) if row else 0

    def _build_scale(self, samples: Iterable[float]) -> FeatureScale:
        values = np.array(list(samples), dtype=float)
        median = float(np.median(values))
        q75, q25 = np.percentile(values, [75, 25])
        iqr = float(q75 - q25)
        if abs(iqr) < 1e-9:
            iqr = 1.0
        return FeatureScale(median=median, iqr=iqr, count=int(values.size))

    def _to_json(self, state: NormalizationState) -> str:
        payload = {
            "version": state.version,
            "source_song_count": state.source_song_count,
            "analyzed_song_count": state.analyzed_song_count,
            "feature_scales": {
                feature: asdict(scale) for feature, scale in state.feature_scales.items()
            },
            "updated_at": state.updated_at,
        }
        return json.dumps(payload)

    def _from_json(self, payload: str) -> NormalizationState:
        data = json.loads(payload)
        feature_scales = {
            feature: FeatureScale(
                median=float(scale["median"]),
                iqr=float(scale["iqr"]),
                count=int(scale["count"]),
            )
            for feature, scale in data.get("feature_scales", {}).items()
        }
        return NormalizationState(
            version=str(data.get("version", "robust-median-iqr-v1")),
            source_song_count=int(data.get("source_song_count", 0)),
            analyzed_song_count=int(data.get("analyzed_song_count", 0)),
            feature_scales=feature_scales,
            updated_at=float(data.get("updated_at", time.time())),
        )
