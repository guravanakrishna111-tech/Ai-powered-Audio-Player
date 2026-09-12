from __future__ import annotations

import logging
import time
from dataclasses import asdict

from fastapi import HTTPException

from app.db.connection import Database
from app.recommendation.audit import RecommendationAudit
from app.recommendation.candidate_generator import CandidateGenerator
from app.recommendation.config import ALGORITHM_VERSION, CONFIG_VERSION, DEFAULT_WEIGHTS, DIVERSITY_ARTIST_PENALTY, DIVERSITY_MAX_PER_ARTIST, RecommendationWeights
from app.recommendation.diversity import apply_diversity
from app.recommendation.explanations import build_reasons
from app.recommendation.feature_builder import RecommendationFeatureBuilder
from app.recommendation.models import RecommendationItem, ScoreBreakdown, SongFeatureVector
from app.recommendation.normalization import RecommendationNormalizer
from app.recommendation.similarity import audio_similarity, metadata_similarity, mood_similarity

logger = logging.getLogger(__name__)


class RecommendationEngine:
    def __init__(
        self,
        database: Database,
        weights: RecommendationWeights | None = None,
    ) -> None:
        self.db = database
        self.weights = weights or DEFAULT_WEIGHTS
        self.feature_builder = RecommendationFeatureBuilder(database)
        self.candidate_generator = CandidateGenerator(self.feature_builder)
        self.normalizer = RecommendationNormalizer(database)
        self.audit = RecommendationAudit(database)

    def recommend(
        self,
        song_id: int,
        limit: int = 5,
        *,
        diversity_max_per_artist: int | None = None,
        diversity_penalty: float | None = None,
    ) -> dict:
        """Return top-``limit`` recommendations for *song_id*.

        Parameters
        ----------
        diversity_max_per_artist:
            Override ``DIVERSITY_MAX_PER_ARTIST`` for this call.
            Pass ``0`` to disable diversity re-ranking entirely.
        diversity_penalty:
            Override ``DIVERSITY_ARTIST_PENALTY`` for this call.
        """
        start = time.perf_counter()
        source, candidates = self.candidate_generator.generate(song_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Song not found")

        normalizer_state = self.normalizer.load()
        scored = self._score_candidates(source, candidates, normalizer_state)

        # ── Stage 1: pure relevance ranking ──────────────────────────────────
        scored.sort(key=lambda item: (-item.score, item.song.artist_name or "", item.song.title or ""))

        # ── Stage 2: diversity re-ranking ─────────────────────────────────────
        # Prevents the top-N from being dominated by a single artist.
        # apply_diversity() preserves relevance ordering within non-penalised
        # candidates and never removes candidates — it only demotes.
        max_per_artist = diversity_max_per_artist if diversity_max_per_artist is not None else DIVERSITY_MAX_PER_ARTIST
        penalty = diversity_penalty if diversity_penalty is not None else DIVERSITY_ARTIST_PENALTY
        scored = apply_diversity(scored, max_per_artist=max_per_artist, penalty=penalty)

        # ── Stage 3: slice top-N and assign ranks ────────────────────────────
        top = scored[: max(1, limit)]
        for index, item in enumerate(top, start=1):
            item.rank = index

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        self.audit.record(song_id, top, len(candidates), latency_ms)

        logger.info(
            "Recommendation run song_id=%s candidate_count=%s returned=%s latency_ms=%s",
            song_id,
            len(candidates),
            len(top),
            latency_ms,
        )
        return {
            "song_id": song_id,
            "source_song": self._song_payload(source),
            "recommendations": [
                {
                    "rank": item.rank,
                    "score": round(item.score, 4),
                    "reasons": item.reasons,
                    "song": self._song_payload(item.song),
                    "breakdown": {name: value for name, value in item.breakdown.details.items() if value is not None},
                }
                for item in top
            ],
            "candidate_count": len(candidates),
            "latency_ms": latency_ms,
            "algorithm_version": ALGORITHM_VERSION,
            "config_version": CONFIG_VERSION,
            "weights": asdict(self.weights),
        }

    def _score_candidates(
        self,
        source: SongFeatureVector,
        candidates: list[SongFeatureVector],
        normalizer_state,
    ) -> list[RecommendationItem]:
        scored: list[RecommendationItem] = []
        for candidate in candidates:
            breakdown = self._score_pair(source, candidate, normalizer_state)
            if breakdown.score <= 0:
                continue
            reasons = build_reasons(source, candidate, breakdown)
            breakdown.reasons = reasons
            scored.append(
                RecommendationItem(
                    rank=0,
                    score=breakdown.score,
                    reasons=reasons,
                    song=candidate,
                    breakdown=breakdown,
                )
            )
        return scored

    def _score_pair(
        self,
        source: SongFeatureVector,
        candidate: SongFeatureVector,
        normalizer_state,
    ) -> ScoreBreakdown:
        audio_score, audio_parts = audio_similarity(source, candidate, self.normalizer, normalizer_state)
        mood_score = mood_similarity(source, candidate)
        metadata_score, metadata_parts = metadata_similarity(source, candidate)

        breakdown = ScoreBreakdown()
        breakdown.details.update(
            {
                "audio": audio_score,
                "mood": mood_score,
                "genre": metadata_parts.get("genre"),
                "artist": metadata_parts.get("artist"),
                "language": metadata_parts.get("language"),
                "album": metadata_parts.get("album"),
                "other": metadata_parts.get("other"),
                "audio_tempo": audio_parts.get("tempo"),
                "audio_energy": audio_parts.get("energy"),
                "audio_timbre": audio_parts.get("timbre"),
                "audio_harmony": audio_parts.get("harmony"),
                "other_composer": 1.0 if source.composer and candidate.composer and source.composer.strip().casefold() == candidate.composer.strip().casefold() else None,
                "other_year": None,
                "other_duration": None,
            }
        )

        if source.album_year is not None and candidate.album_year is not None:
            breakdown.details["other_year"] = max(
                0.0,
                1.0 - abs(source.album_year - candidate.album_year) / 12.0,
            )
        if source.duration is not None and candidate.duration is not None:
            breakdown.details["other_duration"] = max(
                0.0,
                1.0 - abs(source.duration - candidate.duration) / 120.0,
            )

        components = {
            "audio": audio_score,
            "mood": mood_score,
            "genre": metadata_parts.get("genre"),
            "artist": metadata_parts.get("artist"),
            "language": metadata_parts.get("language"),
            "album": metadata_parts.get("album"),
            "other": metadata_score,
        }

        weighted_sum = 0.0
        active_weight = 0.0
        for name, value in components.items():
            if value is None:
                continue
            weight = getattr(self.weights, name)
            weighted_sum += weight * float(value)
            active_weight += weight

        breakdown.audio = audio_score
        breakdown.mood = mood_score
        breakdown.genre = metadata_parts.get("genre")
        breakdown.artist = metadata_parts.get("artist")
        breakdown.language = metadata_parts.get("language")
        breakdown.album = metadata_parts.get("album")
        breakdown.other = metadata_score
        breakdown.score = weighted_sum / active_weight if active_weight else 0.0
        return breakdown

    def _song_payload(self, song: SongFeatureVector) -> dict:
        return {
            "id": song.song_id,
            "file_path": song.file_path,
            "title": song.title,
            "duration": song.duration,
            "track_number": song.track_number,
            "disc_number": song.disc_number,
            "artwork_path": song.artwork_path,
            "artist_id": song.artist_id,
            "artist_name": song.artist_name,
            "album_id": song.album_id,
            "album_title": song.album_title,
            "album_year": song.album_year,
            "analysis_status": song.analysis_status,
            "is_favorite": song.is_favorite,
            "play_count": song.play_count,
        }
