"""Optional MusicBrainz metadata enrichment — minimal data only."""

import logging
import time
from urllib.parse import quote

import httpx

from app.config import settings
from app.db.connection import Database
from app.metadata.normalizer import normalize_display_name

logger = logging.getLogger(__name__)

MUSICBRAINZ_BASE = "https://musicbrainz.org/ws/2"


class MetadataEnricher:
    def __init__(self, database: Database) -> None:
        self.db = database

    def enrich_song(self, song_id: int) -> bool:
        if not settings.enrichment_enabled:
            return False

        song = self.db.fetchone(
            """
            SELECT s.title, ar.name AS artist, sm.album_artist
            FROM songs s
            LEFT JOIN artists ar ON ar.id = s.artist_id
            LEFT JOIN song_metadata sm ON sm.song_id = s.id
            WHERE s.id = ?
            """,
            (song_id,),
        )
        if not song:
            return False

        query = f"{song['title']} AND artist:{song['artist']}"
        cache_key = normalize_display_name(query).casefold()
        cached = self.db.fetchone(
            "SELECT response_json FROM enrichment_cache WHERE lookup_key = ?",
            (cache_key,),
        )
        if cached:
            return self._apply_enrichment(song_id, cached["response_json"])

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{MUSICBRAINZ_BASE}/recording",
                    params={"query": query, "fmt": "json", "limit": 1},
                    headers={"User-Agent": settings.musicbrainz_user_agent},
                )
                response.raise_for_status()
                payload = response.text
                self.db.execute(
                    """
                    INSERT INTO enrichment_cache (lookup_key, provider, response_json, expires_at)
                    VALUES (?, 'musicbrainz', ?, ?)
                    ON CONFLICT(lookup_key) DO UPDATE SET response_json = excluded.response_json
                    """,
                    (cache_key, payload, time.time() + 86400 * 30),
                )
                return self._apply_enrichment(song_id, payload)
        except Exception as exc:
            logger.warning("Enrichment failed for song %s: %s", song_id, exc)
            return False

    def _apply_enrichment(self, song_id: int, response_json: str) -> bool:
        import json
        data = json.loads(response_json)
        recordings = data.get("recordings", [])
        if not recordings:
            return False
        rec = recordings[0]
        release = (rec.get("releases") or [{}])[0]
        date = release.get("date")
        year = int(date[:4]) if date and len(date) >= 4 and date[:4].isdigit() else None

        self.db.execute(
            """
            UPDATE song_metadata SET enriched_at = ?, source = 'musicbrainz'
            WHERE song_id = ?
            """,
            (time.time(), song_id),
        )
        if year:
            self.db.execute(
                """
                UPDATE albums SET year = COALESCE(year, ?)
                WHERE id = (SELECT album_id FROM songs WHERE id = ?)
                """,
                (year, song_id),
            )
        return True
