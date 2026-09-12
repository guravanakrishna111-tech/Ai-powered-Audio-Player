from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from app.db.connection import Database
from app.metadata.normalizer import normalize_text
from app.recommendation.models import MOOD_ORDER, SongFeatureVector


class RecommendationFeatureBuilder:
    def __init__(self, database: Database) -> None:
        self.db = database

    def load_song(self, song_id: int) -> SongFeatureVector | None:
        rows = self._load_rows(song_id)
        return rows[0] if rows else None

    def load_candidates(self, exclude_song_id: int) -> list[SongFeatureVector]:
        rows = self._load_rows(exclude_song_id, exclude=True)
        if not rows:
            return []

        excluded_ids = self._load_duplicate_ids(exclude_song_id)
        return [row for row in rows if row.song_id not in excluded_ids]

    def _load_rows(self, song_id: int, exclude: bool = False) -> list[SongFeatureVector]:
        clause = "AND s.id != ?" if exclude else "AND s.id = ?"
        rows = self.db.fetchall(
            f"""
            SELECT
                s.id AS song_id, s.file_path, s.title, s.artist_id, s.album_id,
                s.track_number, s.disc_number, s.duration, s.artwork_path,
                s.analysis_status, s.file_hash, s.is_missing, s.is_favorite, s.play_count,
                ar.name AS artist_name,
                al.title AS album_title, al.year AS album_year,
                sm.album_artist, sm.composer, sm.raw_json,
                af.bpm, af.tempo, af.rms_energy, af.loudness,
                af.spectral_centroid, af.spectral_bandwidth,
                af.spectral_contrast_mean, af.zero_crossing_rate,
                af.mfcc_mean, af.chroma_mean, af.estimated_key,
                af.key_confidence, af.mood_scores
            FROM songs s
            LEFT JOIN artists ar ON ar.id = s.artist_id
            LEFT JOIN albums al ON al.id = s.album_id
            LEFT JOIN song_metadata sm ON sm.song_id = s.id
            LEFT JOIN audio_features af ON af.song_id = s.id
            WHERE s.is_missing = 0 {clause}
            ORDER BY ar.name, al.title, s.disc_number, s.track_number, s.title
            """,
            (song_id,),
        )
        genres = self._load_genres()
        return [self._row_to_feature(row, genres.get(row["song_id"], ())) for row in rows]

    def _load_genres(self) -> dict[int, tuple[str, ...]]:
        rows = self.db.fetchall(
            """
            SELECT sg.song_id, g.name
            FROM song_genres sg
            JOIN genres g ON g.id = sg.genre_id
            ORDER BY sg.song_id, g.name
            """
        )
        grouped: dict[int, list[str]] = defaultdict(list)
        for row in rows:
            grouped[int(row["song_id"])].append(str(row["name"]))
        return {song_id: tuple(names) for song_id, names in grouped.items()}

    def _load_duplicate_ids(self, song_id: int) -> set[int]:
        rows = self.db.fetchall(
            """
            SELECT song_id_a AS left_id, song_id_b AS right_id
            FROM duplicate_candidates
            WHERE song_id_a = ? OR song_id_b = ?
            """,
            (song_id, song_id),
        )
        excluded = {song_id}
        for row in rows:
            left_id = int(row["left_id"])
            right_id = int(row["right_id"])
            excluded.add(right_id if left_id == song_id else left_id)

        hash_row = self.db.fetchone("SELECT file_hash FROM songs WHERE id = ?", (song_id,))
        file_hash = hash_row["file_hash"] if hash_row else None
        if file_hash:
            rows = self.db.fetchall(
                "SELECT id FROM songs WHERE file_hash = ? AND id != ?",
                (file_hash, song_id),
            )
            excluded.update(int(row["id"]) for row in rows)
        return excluded

    def _row_to_feature(self, row: Any, genres: tuple[str, ...]) -> SongFeatureVector:
        raw_metadata = self._parse_json(row["raw_json"])
        mood_scores = self._parse_json(row["mood_scores"], default={})
        mfcc = self._parse_float_tuple(row["mfcc_mean"])
        chroma = self._parse_float_tuple(row["chroma_mean"])
        language = self._extract_language(raw_metadata)

        return SongFeatureVector(
            song_id=int(row["song_id"]),
            file_path=str(row["file_path"]),
            title=row["title"],
            artist_id=int(row["artist_id"]) if row["artist_id"] is not None else None,
            artist_name=row["artist_name"],
            album_id=int(row["album_id"]) if row["album_id"] is not None else None,
            album_title=row["album_title"],
            album_year=int(row["album_year"]) if row["album_year"] is not None else None,
            track_number=int(row["track_number"]) if row["track_number"] is not None else None,
            disc_number=int(row["disc_number"]) if row["disc_number"] is not None else None,
            duration=float(row["duration"]) if row["duration"] is not None else None,
            artwork_path=row["artwork_path"],
            analysis_status=row["analysis_status"],
            file_hash=row["file_hash"],
            is_favorite=int(row["is_favorite"]) if row["is_favorite"] is not None else 0,
            play_count=int(row["play_count"]) if row["play_count"] is not None else 0,
            genres=genres,
            composer=row["composer"],
            album_artist=row["album_artist"],
            language=language,
            bpm=float(row["bpm"]) if row["bpm"] is not None else None,
            tempo=float(row["tempo"]) if row["tempo"] is not None else None,
            rms_energy=float(row["rms_energy"]) if row["rms_energy"] is not None else None,
            loudness=float(row["loudness"]) if row["loudness"] is not None else None,
            spectral_centroid=float(row["spectral_centroid"]) if row["spectral_centroid"] is not None else None,
            spectral_bandwidth=float(row["spectral_bandwidth"]) if row["spectral_bandwidth"] is not None else None,
            spectral_contrast_mean=float(row["spectral_contrast_mean"]) if row["spectral_contrast_mean"] is not None else None,
            zero_crossing_rate=float(row["zero_crossing_rate"]) if row["zero_crossing_rate"] is not None else None,
            mfcc_mean=mfcc,
            chroma_mean=chroma,
            estimated_key=row["estimated_key"],
            key_confidence=float(row["key_confidence"]) if row["key_confidence"] is not None else None,
            mood_scores={k: float(v) for k, v in mood_scores.items()},
            raw_metadata=raw_metadata,
        )

    def _parse_json(self, value: str | None, default: Any | None = None) -> Any:
        if not value:
            return {} if default is None else default
        try:
            parsed = json.loads(value)
            if parsed is None:
                return {} if default is None else default
            return parsed
        except json.JSONDecodeError:
            return {} if default is None else default

    def _parse_float_tuple(self, value: str | None) -> tuple[float, ...]:
        if not value:
            return ()
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return tuple(float(item) for item in parsed)
        except json.JSONDecodeError:
            return ()
        return ()

    def _extract_language(self, raw_metadata: dict[str, Any]) -> str | None:
        for key in ("language", "lang", "lyrics_language", "track_language"):
            value = raw_metadata.get(key)
            if isinstance(value, str) and value.strip():
                return normalize_text(value)
        return None
