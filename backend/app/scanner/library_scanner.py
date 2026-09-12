import time
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.db.connection import Database
from app.metadata.extractor import compute_file_hash, extract_metadata, metadata_to_json
from app.metadata.normalizer import normalize_display_name, normalize_text


@dataclass
class ScanProgress:
    total_files: int = 0
    scanned: int = 0
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    is_scanning: bool = False


class LibraryScanner:
    SUPPORTED = set(settings.supported_extensions)

    def __init__(self, database: Database) -> None:
        self.db = database
        self.progress = ScanProgress()

    def add_folder(self, folder_path: str) -> None:
        path = str(Path(folder_path).resolve())
        self.db.execute(
            """
            INSERT INTO music_folders (path, enabled)
            VALUES (?, 1)
            ON CONFLICT(path) DO UPDATE SET enabled = 1
            """,
            (path,),
        )

    def list_folders(self) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT id, path, enabled, last_scanned_at FROM music_folders ORDER BY path"
        )
        return [dict(row) for row in rows]

    def remove_folder(self, folder_id: int) -> None:
        self.db.execute("DELETE FROM music_folders WHERE id = ?", (folder_id,))

    def scan_all(self) -> ScanProgress:
        self.progress = ScanProgress(is_scanning=True)
        folders = self.db.fetchall("SELECT id, path FROM music_folders WHERE enabled = 1")
        files: list[Path] = []
        for folder in folders:
            files.extend(self._discover_files(Path(folder["path"])))

        self.progress.total_files = len(files)
        seen_paths: set[str] = set()

        for file_path in files:
            seen_paths.add(str(file_path.resolve()))
            try:
                outcome = self._process_file(file_path)
                if outcome == "added":
                    self.progress.added += 1
                elif outcome == "updated":
                    self.progress.updated += 1
                else:
                    self.progress.skipped += 1
            except Exception:
                self.progress.errors += 1
            finally:
                self.progress.scanned += 1

        self._mark_missing_files(seen_paths)
        for folder in folders:
            self.db.execute(
                "UPDATE music_folders SET last_scanned_at = ? WHERE id = ?",
                (time.time(), folder["id"]),
            )

        self.progress.is_scanning = False
        return self.progress

    def _discover_files(self, root: Path) -> list[Path]:
        if not root.exists():
            return []
        discovered: list[Path] = []
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.SUPPORTED:
                discovered.append(path)
        return discovered

    def _process_file(self, file_path: Path) -> str:
        resolved = str(file_path.resolve())
        stat = file_path.stat()
        existing = self.db.fetchone(
            "SELECT id, file_size, file_mtime, file_hash FROM songs WHERE file_path = ?",
            (resolved,),
        )

        if existing and existing["file_size"] == stat.st_size and existing["file_mtime"] == stat.st_mtime:
            self.db.execute("UPDATE songs SET is_missing = 0 WHERE id = ?", (existing["id"],))
            return "skipped"

        file_hash = None
        if existing and existing["file_hash"]:
            file_hash = existing["file_hash"]
        else:
            try:
                file_hash = compute_file_hash(file_path)
            except OSError:
                file_hash = None

        meta = extract_metadata(file_path)
        artist_id = self._get_or_create_artist(meta.artist or "Unknown Artist")
        album_id = self._get_or_create_album(meta.album or "Unknown Album", artist_id, meta.year)
        artwork_path = self._save_artwork(existing["id"] if existing else None, meta.artwork_bytes)

        if existing:
            song_id = existing["id"]
            self.db.execute(
                """
                UPDATE songs SET
                    file_size = ?, file_mtime = ?, file_hash = ?,
                    title = ?, artist_id = ?, album_id = ?,
                    track_number = ?, disc_number = ?, duration = ?,
                    artwork_path = ?, is_missing = 0, updated_at = ?
                WHERE id = ?
                """,
                (
                    stat.st_size, stat.st_mtime, file_hash,
                    meta.title, artist_id, album_id,
                    meta.track_number, meta.disc_number, meta.duration,
                    artwork_path, time.time(), song_id,
                ),
            )
            self._upsert_metadata(song_id, meta)
            self._queue_job(song_id, "metadata")
            self._queue_job(song_id, "analysis")
            return "updated"

        cur = self.db.execute(
            """
            INSERT INTO songs (
                file_path, file_size, file_mtime, file_hash,
                title, artist_id, album_id, track_number, disc_number,
                duration, artwork_path, analysis_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                resolved, stat.st_size, stat.st_mtime, file_hash,
                meta.title, artist_id, album_id, meta.track_number,
                meta.disc_number or 1, meta.duration, artwork_path,
            ),
        )
        song_id = cur.lastrowid
        self._upsert_metadata(song_id, meta)
        if meta.genre:
            genre_id = self._get_or_create_genre(meta.genre)
            self.db.execute(
                "INSERT OR IGNORE INTO song_genres (song_id, genre_id) VALUES (?, ?)",
                (song_id, genre_id),
            )
        self._queue_job(song_id, "metadata")
        self._queue_job(song_id, "analysis")
        return "added"

    def _get_or_create_artist(self, name: str) -> int:
        normalized = normalize_text(name)
        row = self.db.fetchone(
            "SELECT id FROM artists WHERE normalized_name = ?", (normalized,)
        )
        if row:
            return row["id"]
        cur = self.db.execute(
            "INSERT INTO artists (name, normalized_name) VALUES (?, ?)",
            (normalize_display_name(name), normalized),
        )
        return cur.lastrowid

    def _get_or_create_album(self, title: str, artist_id: int, year: int | None) -> int:
        normalized = normalize_text(title)
        row = self.db.fetchone(
            "SELECT id FROM albums WHERE normalized_title = ? AND album_artist_id = ?",
            (normalized, artist_id),
        )
        if row:
            return row["id"]
        cur = self.db.execute(
            """
            INSERT INTO albums (title, normalized_title, album_artist_id, year)
            VALUES (?, ?, ?, ?)
            """,
            (normalize_display_name(title), normalized, artist_id, year),
        )
        return cur.lastrowid

    def _get_or_create_genre(self, name: str) -> int:
        normalized = normalize_text(name)
        row = self.db.fetchone(
            "SELECT id FROM genres WHERE normalized_name = ?", (normalized,)
        )
        if row:
            return row["id"]
        cur = self.db.execute(
            "INSERT INTO genres (name, normalized_name) VALUES (?, ?)",
            (normalize_display_name(name), normalized),
        )
        return cur.lastrowid

    def _upsert_metadata(self, song_id: int, meta) -> None:
        self.db.execute(
            """
            INSERT INTO song_metadata (
                song_id, album_artist, composer, comments, lyrics,
                bitrate, sample_rate, channels, codec, source, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'embedded', ?)
            ON CONFLICT(song_id) DO UPDATE SET
                album_artist = excluded.album_artist,
                composer = excluded.composer,
                comments = excluded.comments,
                lyrics = excluded.lyrics,
                bitrate = excluded.bitrate,
                sample_rate = excluded.sample_rate,
                channels = excluded.channels,
                codec = excluded.codec,
                raw_json = excluded.raw_json
            """,
            (
                song_id, meta.album_artist, meta.composer, meta.comments, meta.lyrics,
                meta.bitrate, meta.sample_rate, meta.channels, meta.codec,
                metadata_to_json(meta),
            ),
        )

    def _save_artwork(self, song_id: int | None, artwork: bytes | None) -> str | None:
        if not artwork:
            if song_id:
                row = self.db.fetchone("SELECT artwork_path FROM songs WHERE id = ?", (song_id,))
                return row["artwork_path"] if row else None
            return None
        target = settings.artwork_dir / f"{song_id or 'new'}_{int(time.time())}.jpg"
        target.write_bytes(artwork)
        return str(target)

    def _queue_job(self, song_id: int, job_type: str) -> None:
        self.db.execute(
            """
            INSERT INTO analysis_jobs (song_id, job_type, status, priority)
            SELECT ?, ?, 'queued', ?
            WHERE NOT EXISTS (
                SELECT 1 FROM analysis_jobs
                WHERE song_id = ? AND job_type = ? AND status IN ('queued', 'running')
            )
            """,
            (song_id, job_type, 1 if job_type == "analysis" else 0, song_id, job_type),
        )

    def _mark_missing_files(self, seen_paths: set[str]) -> None:
        rows = self.db.fetchall("SELECT id, file_path FROM songs WHERE is_missing = 0")
        for row in rows:
            if row["file_path"] not in seen_paths:
                path = Path(row["file_path"])
                if not path.exists():
                    self.db.execute("UPDATE songs SET is_missing = 1 WHERE id = ?", (row["id"],))
