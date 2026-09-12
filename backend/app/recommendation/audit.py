from __future__ import annotations

import json
from typing import Iterable

from app.db.connection import Database
from app.recommendation.config import ALGORITHM_VERSION, CONFIG_VERSION
from app.recommendation.models import RecommendationItem


class RecommendationAudit:
    def __init__(self, database: Database) -> None:
        self.db = database

    def record(
        self,
        source_song_id: int,
        recommendations: Iterable[RecommendationItem],
        candidate_count: int,
        latency_ms: float,
    ) -> None:
        for item in recommendations:
            self.db.execute(
                """
                INSERT INTO recommendation_history (
                    source_song_id, recommended_song_id, rank, score, reasons_json,
                    candidate_count, latency_ms, algorithm_version, config_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_song_id,
                    item.song.song_id,
                    item.rank,
                    item.score,
                    json.dumps(item.reasons),
                    candidate_count,
                    latency_ms,
                    ALGORITHM_VERSION,
                    CONFIG_VERSION,
                ),
            )

