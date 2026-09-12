from __future__ import annotations

from app.recommendation.feature_builder import RecommendationFeatureBuilder
from app.recommendation.models import SongFeatureVector


class CandidateGenerator:
    def __init__(self, feature_builder: RecommendationFeatureBuilder) -> None:
        self.feature_builder = feature_builder

    def generate(self, source_song_id: int) -> tuple[SongFeatureVector | None, list[SongFeatureVector]]:
        source = self.feature_builder.load_song(source_song_id)
        if source is None:
            return None, []
        candidates = self.feature_builder.load_candidates(source_song_id)
        return source, candidates

