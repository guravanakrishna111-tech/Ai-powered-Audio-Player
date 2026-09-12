from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MOOD_ORDER = (
    "romantic",
    "sad",
    "happy",
    "calm",
    "energetic",
    "party",
    "melancholic",
    "peaceful",
    "motivational",
)


@dataclass(slots=True)
class SongFeatureVector:
    song_id: int
    file_path: str
    title: str | None
    artist_id: int | None
    artist_name: str | None
    album_id: int | None
    album_title: str | None
    album_year: int | None
    track_number: int | None
    disc_number: int | None
    duration: float | None
    artwork_path: str | None
    analysis_status: str | None
    file_hash: str | None
    is_favorite: int = 0
    play_count: int = 0
    genres: tuple[str, ...] = ()
    composer: str | None = None
    album_artist: str | None = None
    language: str | None = None
    bpm: float | None = None
    tempo: float | None = None
    rms_energy: float | None = None
    loudness: float | None = None
    spectral_centroid: float | None = None
    spectral_bandwidth: float | None = None
    spectral_contrast_mean: float | None = None
    zero_crossing_rate: float | None = None
    mfcc_mean: tuple[float, ...] = ()
    chroma_mean: tuple[float, ...] = ()
    estimated_key: str | None = None
    key_confidence: float | None = None
    mood_scores: dict[str, float] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def has_audio_features(self) -> bool:
        return any(
            value is not None
            for value in (
                self.bpm,
                self.tempo,
                self.rms_energy,
                self.loudness,
                self.spectral_centroid,
                self.spectral_bandwidth,
                self.spectral_contrast_mean,
                self.zero_crossing_rate,
            )
        )

    def has_mood(self) -> bool:
        return bool(self.mood_scores)

    def has_metadata(self) -> bool:
        return any(
            value is not None
            for value in (
                self.artist_id,
                self.album_id,
                self.album_year,
                self.composer,
                self.language,
            )
        ) or bool(self.genres)


@dataclass(slots=True)
class FeatureScale:
    median: float
    iqr: float
    count: int


@dataclass(slots=True)
class NormalizationState:
    version: str
    source_song_count: int
    analyzed_song_count: int
    feature_scales: dict[str, FeatureScale]
    updated_at: float


@dataclass(slots=True)
class ScoreBreakdown:
    audio: float | None = None
    mood: float | None = None
    genre: float | None = None
    artist: float | None = None
    language: float | None = None
    album: float | None = None
    other: float | None = None
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    details: dict[str, float | None] = field(default_factory=dict)


@dataclass(slots=True)
class RecommendationItem:
    rank: int
    score: float
    reasons: list[str]
    song: SongFeatureVector
    breakdown: ScoreBreakdown
