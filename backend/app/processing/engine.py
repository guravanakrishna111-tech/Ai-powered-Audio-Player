import json
import logging
import threading
import time
from pathlib import Path

from app.analysis.audio_analyzer import analyze_audio
from app.analysis.mood_estimator import mood_scores_to_json
from app.config import settings
from app.db.connection import Database

logger = logging.getLogger(__name__)


class ProcessingEngine:
    def __init__(self, database: Database) -> None:
        self.db = database
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.is_running = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="processing-engine")
        self._thread.start()
        self.is_running = True

    def stop(self) -> None:
        self._stop_event.set()
        self.is_running = False

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self._claim_job()
            if not job:
                self._ensure_model_trained()
                time.sleep(1.0)
                continue
            try:
                self._process_job(job)
                self._complete_job(job["id"])
            except Exception as exc:
                logger.exception("Job %s failed", job["id"])
                self._fail_job(job["id"], str(exc))

    def _ensure_model_trained(self) -> None:
        try:
            from app.recommendation.normalization import RecommendationNormalizer
            norm = RecommendationNormalizer(self.db)
            state = norm.load()
            if norm._is_stale(state):
                new_state = norm.fit()
                norm.save(new_state)
                logger.info("Auto-updated recommender normalization model (%d songs)", new_state.analyzed_song_count)
        except Exception as exc:
            logger.debug("Failed auto-training model: %s", exc)

    def train_now(self) -> dict:
        """Process all queued jobs and update recommender normalizer."""
        processed = 0
        while True:
            job = self._claim_job()
            if not job:
                break
            try:
                self._process_job(job)
                self._complete_job(job["id"])
                processed += 1
            except Exception as exc:
                self._fail_job(job["id"], str(exc))
        from app.recommendation.normalization import RecommendationNormalizer
        norm = RecommendationNormalizer(self.db)
        state = norm.fit()
        norm.save(state)
        return {
            "processed_jobs": processed,
            "analyzed_song_count": state.analyzed_song_count,
            "version": state.version,
        }

    def _claim_job(self) -> dict | None:
        row = self.db.fetchone(
            """
            SELECT j.id, j.song_id, j.job_type, j.attempts, s.file_path
            FROM analysis_jobs j
            JOIN songs s ON s.id = j.song_id
            WHERE j.status = 'queued' AND s.is_missing = 0
            ORDER BY j.priority DESC, j.created_at ASC
            LIMIT 1
            """
        )
        if not row:
            return None
        self.db.execute(
            """
            UPDATE analysis_jobs
            SET status = 'running', started_at = ?, attempts = attempts + 1
            WHERE id = ? AND status = 'queued'
            """,
            (time.time(), row["id"]),
        )
        return dict(row)

    def _process_job(self, job: dict) -> None:
        if job["job_type"] == "analysis":
            self._run_analysis(job["song_id"], Path(job["file_path"]))
        elif job["job_type"] == "metadata":
            self.db.execute(
                "UPDATE analysis_jobs SET status = 'complete', completed_at = ? WHERE id = ?",
                (time.time(), job["id"]),
            )

    def _run_analysis(self, song_id: int, file_path: Path) -> None:
        self.db.execute(
            "UPDATE songs SET analysis_status = 'processing' WHERE id = ?", (song_id,)
        )
        features = analyze_audio(file_path)
        mood_json = mood_scores_to_json(features)
        feature_vector = self._build_feature_vector(features, mood_json)

        self.db.execute(
            """
            INSERT INTO audio_features (
                song_id, bpm, tempo, rms_energy, loudness,
                spectral_centroid, spectral_bandwidth, spectral_contrast_mean,
                zero_crossing_rate, mfcc_mean, chroma_mean,
                estimated_key, key_confidence, mood_scores, feature_vector,
                analyzed_at, analyzer_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(song_id) DO UPDATE SET
                bpm = excluded.bpm, tempo = excluded.tempo,
                rms_energy = excluded.rms_energy, loudness = excluded.loudness,
                spectral_centroid = excluded.spectral_centroid,
                spectral_bandwidth = excluded.spectral_bandwidth,
                spectral_contrast_mean = excluded.spectral_contrast_mean,
                zero_crossing_rate = excluded.zero_crossing_rate,
                mfcc_mean = excluded.mfcc_mean, chroma_mean = excluded.chroma_mean,
                estimated_key = excluded.estimated_key, key_confidence = excluded.key_confidence,
                mood_scores = excluded.mood_scores, feature_vector = excluded.feature_vector,
                analyzed_at = excluded.analyzed_at, analyzer_version = excluded.analyzer_version
            """,
            (
                song_id, features["bpm"], features["tempo"],
                features["rms_energy"], features["loudness"],
                features["spectral_centroid"], features["spectral_bandwidth"],
                features["spectral_contrast_mean"], features["zero_crossing_rate"],
                features["mfcc_mean"], features["chroma_mean"],
                features["estimated_key"], features["key_confidence"],
                mood_json, feature_vector, time.time(), features["analyzer_version"],
            ),
        )
        self.db.execute(
            "UPDATE songs SET analysis_status = 'complete', updated_at = ? WHERE id = ?",
            (time.time(), song_id),
        )
        self._detect_duplicates_for_song(song_id)

    def _build_feature_vector(self, features: dict, mood_json: str) -> str:
        mood = json.loads(mood_json)
        mfcc = json.loads(features["mfcc_mean"])
        chroma = json.loads(features["chroma_mean"])
        vector = [
            features["bpm"], features["rms_energy"], features["loudness"],
            features["spectral_centroid"], features["spectral_bandwidth"],
            features["spectral_contrast_mean"], features["zero_crossing_rate"],
            *mfcc[:8], *chroma[:6], *list(mood.values())[:6],
        ]
        return json.dumps(vector)

    def _detect_duplicates_for_song(self, song_id: int) -> None:
        song = self.db.fetchone(
            "SELECT id, file_hash, title, artist_id, duration FROM songs WHERE id = ?",
            (song_id,),
        )
        if not song:
            return

        if song["file_hash"]:
            rows = self.db.fetchall(
                """
                SELECT id FROM songs
                WHERE file_hash = ? AND id != ? AND is_missing = 0
                """,
                (song["file_hash"], song_id),
            )
            for row in rows:
                self._insert_duplicate(song_id, row["id"], 1.0, "identical_file_hash")

        if song["duration"]:
            rows = self.db.fetchall(
                """
                SELECT id, title FROM songs
                WHERE artist_id = ? AND id != ? AND is_missing = 0
                  AND ABS(duration - ?) < 2.0
                """,
                (song["artist_id"], song_id, song["duration"]),
            )
            for row in rows:
                if song["title"] and row["title"]:
                    if song["title"].casefold() == row["title"].casefold():
                        self._insert_duplicate(song_id, row["id"], 0.85, "metadata_and_duration")

    def _insert_duplicate(self, a: int, b: int, score: float, reason: str) -> None:
        low, high = sorted((a, b))
        self.db.execute(
            """
            INSERT OR IGNORE INTO duplicate_candidates
            (song_id_a, song_id_b, similarity_score, match_reason)
            VALUES (?, ?, ?, ?)
            """,
            (low, high, score, reason),
        )

    def _complete_job(self, job_id: int) -> None:
        self.db.execute(
            """
            UPDATE analysis_jobs SET status = 'complete', completed_at = ?
            WHERE id = ? AND status = 'running'
            """,
            (time.time(), job_id),
        )

    def _fail_job(self, job_id: int, error: str) -> None:
        row = self.db.fetchone(
            "SELECT attempts, max_attempts, song_id FROM analysis_jobs WHERE id = ?",
            (job_id,),
        )
        if not row:
            return
        if row["attempts"] >= row["max_attempts"]:
            self.db.execute(
                """
                UPDATE analysis_jobs SET status = 'failed', error_message = ?, completed_at = ?
                WHERE id = ?
                """,
                (error, time.time(), job_id),
            )
            self.db.execute(
                "UPDATE songs SET analysis_status = 'failed' WHERE id = ?",
                (row["song_id"],),
            )
        else:
            self.db.execute(
                """
                UPDATE analysis_jobs SET status = 'retry', error_message = ?
                WHERE id = ?
                """,
                (error, job_id),
            )
            self.db.execute(
                "UPDATE analysis_jobs SET status = 'queued' WHERE id = ? AND status = 'retry'",
                (job_id,),
            )

    def get_progress(self) -> dict:
        total = self.db.fetchone("SELECT COUNT(*) AS c FROM songs WHERE is_missing = 0")
        metadata_done = self.db.fetchone(
            """
            SELECT COUNT(DISTINCT song_id) AS c FROM analysis_jobs
            WHERE job_type = 'metadata' AND status = 'complete'
            """
        )
        analysis_done = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM songs WHERE analysis_status = 'complete'"
        )
        enrichment_done = self.db.fetchone(
            """
            SELECT COUNT(*) AS c FROM song_metadata WHERE enriched_at IS NOT NULL
            """
        )
        total_count = total["c"] if total else 0

        def pct(count: int) -> float:
            return round((count / total_count) * 100, 1) if total_count else 100.0

        return {
            "scanning": 100.0,
            "metadata": pct(metadata_done["c"] if metadata_done else 0),
            "audio_analysis": pct(analysis_done["c"] if analysis_done else 0),
            "enrichment": pct(enrichment_done["c"] if enrichment_done else 0),
            "total_songs": total_count,
            "is_processing": self.is_running,
        }
