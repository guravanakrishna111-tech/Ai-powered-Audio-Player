from app.db.connection import Database


class LibraryRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def get_songs(
        self,
        search: str | None = None,
        artist_id: int | None = None,
        album_id: int | None = None,
        favorites_only: bool = False,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict]:
        clauses = ["s.is_missing = 0"]
        params: list = []

        if search:
            clauses.append("(s.title LIKE ? OR ar.name LIKE ? OR al.title LIKE ?)")
            term = f"%{search}%"
            params.extend([term, term, term])
        if artist_id:
            clauses.append("s.artist_id = ?")
            params.append(artist_id)
        if album_id:
            clauses.append("s.album_id = ?")
            params.append(album_id)
        if favorites_only:
            clauses.append("s.is_favorite = 1")

        where = " AND ".join(clauses)
        rows = self.db.fetchall(
            f"""
            SELECT
                s.id, s.file_path, s.title, s.duration, s.track_number,
                s.disc_number, s.artwork_path, s.is_favorite, s.play_count,
                s.analysis_status, ar.id AS artist_id, ar.name AS artist_name,
                al.id AS album_id, al.title AS album_title, al.year AS album_year
            FROM songs s
            LEFT JOIN artists ar ON ar.id = s.artist_id
            LEFT JOIN albums al ON al.id = s.album_id
            WHERE {where}
            ORDER BY ar.name, al.title, s.disc_number, s.track_number, s.title
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [dict(row) for row in rows]

    def get_song(self, song_id: int) -> dict | None:
        row = self.db.fetchone(
            """
            SELECT
                s.*, ar.name AS artist_name, al.title AS album_title
            FROM songs s
            LEFT JOIN artists ar ON ar.id = s.artist_id
            LEFT JOIN albums al ON al.id = s.album_id
            WHERE s.id = ?
            """,
            (song_id,),
        )
        return dict(row) if row else None

    def get_artists(self) -> list[dict]:
        rows = self.db.fetchall(
            """
            SELECT ar.id, ar.name, COUNT(s.id) AS song_count
            FROM artists ar
            LEFT JOIN songs s ON s.artist_id = ar.id AND s.is_missing = 0
            GROUP BY ar.id
            HAVING song_count > 0
            ORDER BY ar.name
            """
        )
        return [dict(row) for row in rows]

    def get_albums(self) -> list[dict]:
        rows = self.db.fetchall(
            """
            SELECT al.id, al.title, al.year, al.artwork_path,
                   ar.name AS artist_name, COUNT(s.id) AS song_count
            FROM albums al
            LEFT JOIN artists ar ON ar.id = al.album_artist_id
            LEFT JOIN songs s ON s.album_id = al.id AND s.is_missing = 0
            GROUP BY al.id
            HAVING song_count > 0
            ORDER BY al.title
            """
        )
        return [dict(row) for row in rows]

    def toggle_favorite(self, song_id: int) -> bool:
        row = self.db.fetchone("SELECT is_favorite FROM songs WHERE id = ?", (song_id,))
        if not row:
            return False
        new_value = 0 if row["is_favorite"] else 1
        self.db.execute("UPDATE songs SET is_favorite = ? WHERE id = ?", (new_value, song_id))
        return bool(new_value)

    def record_play(self, song_id: int) -> None:
        import time
        self.db.execute(
            """
            UPDATE songs SET play_count = play_count + 1, last_played_at = ?
            WHERE id = ?
            """,
            (time.time(), song_id),
        )

    def get_processing_stats(self) -> dict:
        total = self.db.fetchone("SELECT COUNT(*) AS c FROM songs WHERE is_missing = 0")
        analyzed = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM songs WHERE analysis_status = 'complete' AND is_missing = 0"
        )
        pending_jobs = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM analysis_jobs WHERE status IN ('queued', 'running')"
        )
        return {
            "total_songs": total["c"] if total else 0,
            "analyzed_songs": analyzed["c"] if analyzed else 0,
            "pending_jobs": pending_jobs["c"] if pending_jobs else 0,
        }

    def get_duplicates(self) -> list[dict]:
        rows = self.db.fetchall(
            """
            SELECT dc.id, dc.similarity_score, dc.match_reason,
                   sa.title AS title_a, sa.file_path AS path_a,
                   sb.title AS title_b, sb.file_path AS path_b
            FROM duplicate_candidates dc
            JOIN songs sa ON sa.id = dc.song_id_a
            JOIN songs sb ON sb.id = dc.song_id_b
            WHERE dc.reviewed = 0
            ORDER BY dc.similarity_score DESC
            LIMIT 100
            """
        )
        return [dict(row) for row in rows]
