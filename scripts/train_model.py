"""Train and update the recommendation model on local music libraries.

Usage:
------
    python scripts/train_model.py
    python scripts/train_model.py --folder "Audio folder"
    python scripts/train_model.py --workers 4 --evaluate
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root and backend to sys.path
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
for candidate in (_PROJECT_ROOT / "backend", _PROJECT_ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.analysis.audio_analyzer import analyze_audio
from app.analysis.mood_estimator import mood_scores_to_json
from app.config import settings
from app.db.connection import Database
from app.recommendation.normalization import RecommendationNormalizer
from app.recommendation.recommender import RecommendationEngine
from app.scanner.library_scanner import LibraryScanner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_model")


def find_db_path() -> Path:
    # 1. Check environment variable
    if "AAP_DATA_DIR" in os.environ:
        cand = Path(os.environ["AAP_DATA_DIR"]) / "library.db"
        if cand.exists():
            return cand
    # 2. Check settings default (Path.home() / .ai-audio-player / data / library.db)
    if settings.db_path.exists():
        return settings.db_path
    # 3. Check workspace backend/data
    cand = _PROJECT_ROOT / "backend" / "data" / "library.db"
    if cand.exists():
        return cand
    return settings.db_path


def resolve_folder_path(folder_str: str) -> Path:
    p = Path(folder_str.strip('\'"'))
    if p.is_absolute() and p.exists():
        return p
    # Check relative to project root
    cand1 = _PROJECT_ROOT / p
    if cand1.exists():
        return cand1.resolve()
    # Check relative to backend
    cand2 = _PROJECT_ROOT / "backend" / p
    if cand2.exists():
        return cand2.resolve()
    # Check relative to cwd
    cand3 = Path.cwd() / p
    if cand3.exists():
        return cand3.resolve()
    raise FileNotFoundError(f"Audio folder not found: {folder_str}")


def process_single_song(db_path: Path, song_id: int, file_path_str: str, job_id: int | None = None) -> bool:
    """Analyze a single audio file and update the database."""
    file_path = Path(file_path_str)
    if not file_path.exists():
        logger.warning("File not found: %s", file_path)
        return False

    db = Database(db_path)
    try:
        features = analyze_audio(file_path)
        mood_json = mood_scores_to_json(features)

        # Build feature vector for fast vector indexing
        mood = json.loads(mood_json)
        mfcc = json.loads(features["mfcc_mean"])
        chroma = json.loads(features["chroma_mean"])
        vector = [
            features["bpm"], features["rms_energy"], features["loudness"],
            features["spectral_centroid"], features["spectral_bandwidth"],
            features["spectral_contrast_mean"], features["zero_crossing_rate"],
            *mfcc[:8], *chroma[:6], *list(mood.values())[:6],
        ]
        feature_vector_json = json.dumps(vector)

        db.execute(
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
                mood_json, feature_vector_json, time.time(), features["analyzer_version"],
            ),
        )

        db.execute(
            "UPDATE songs SET analysis_status = 'complete', updated_at = ? WHERE id = ?",
            (time.time(), song_id),
        )

        if job_id:
            db.execute(
                "UPDATE analysis_jobs SET status = 'complete', completed_at = ? WHERE id = ?",
                (time.time(), job_id),
            )
        return True
    except Exception as exc:
        logger.error("Analysis failed for song_id=%s (%s): %s", song_id, file_path.name, exc)
        if job_id:
            db.execute(
                "UPDATE analysis_jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
                (str(exc), time.time(), job_id),
            )
        db.execute(
            "UPDATE songs SET analysis_status = 'failed', updated_at = ? WHERE id = ?",
            (time.time(), song_id),
        )
        return False


def train(folder: str | None = None, workers: int = 4, evaluate: bool = True, force: bool = False) -> None:
    db_path = find_db_path()
    print("=" * 60)
    print("  AI AUDIO PLAYER -- MODEL TRAINING & UPGRADE")
    print("=" * 60)
    print(f"Database: {db_path}")

    db = Database(db_path)
    scanner = LibraryScanner(db)

    # 1. If folder is specified or defaults to Audio folder, scan it
    target_folder = folder
    if not target_folder:
        workspace_audio = _PROJECT_ROOT / "Audio folder"
        if workspace_audio.is_dir():
            target_folder = str(workspace_audio)

    if target_folder:
        resolved = resolve_folder_path(target_folder)
        print(f"Adding/scanning audio folder: {resolved}")
        scanner.add_folder(str(resolved))
        scan_progress = scanner.scan_all()
        print(f"Scan finished: total_files={scan_progress.total_files}, added={scan_progress.added}, skipped={scan_progress.skipped}")

    # Mark metadata jobs as complete
    db.execute("UPDATE analysis_jobs SET status = 'complete', completed_at = ? WHERE job_type = 'metadata' AND status = 'queued'", (time.time(),))

    # 2. Query pending or forced songs
    if force:
        db.execute("UPDATE songs SET analysis_status = 'pending' WHERE is_missing = 0")
        rows = db.fetchall("SELECT id, file_path FROM songs WHERE is_missing = 0")
        jobs_map = {}
    else:
        rows = db.fetchall(
            """
            SELECT s.id, s.file_path, j.id AS job_id
            FROM songs s
            LEFT JOIN analysis_jobs j ON j.song_id = s.id AND j.job_type = 'analysis' AND j.status = 'queued'
            WHERE s.is_missing = 0 AND (s.analysis_status != 'complete' OR s.analysis_status IS NULL)
            """
        )
        jobs_map = {row["id"]: row["job_id"] for row in rows}

    pending_songs = [(row["id"], row["file_path"], jobs_map.get(row["id"])) for row in rows]
    print(f"\nSongs pending audio feature analysis: {len(pending_songs)}")

    # 3. Multi-worker audio analysis
    t0 = time.time()
    succeeded = 0
    failed = 0

    if pending_songs:
        print(f"Starting feature extraction with {workers} parallel workers...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_song = {
                executor.submit(process_single_song, db_path, s_id, f_path, j_id): (s_id, f_path)
                for s_id, f_path, j_id in pending_songs
            }

            for i, future in enumerate(concurrent.futures.as_completed(future_to_song), 1):
                s_id, f_path = future_to_song[future]
                try:
                    ok = future.result()
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    logger.error("Worker error on song %s: %s", s_id, exc)

                if i % 10 == 0 or i == len(pending_songs):
                    pct = (i / len(pending_songs)) * 100
                    elapsed = time.time() - t0
                    print(f"  Progress: {i}/{len(pending_songs)} ({pct:.1f}%) -- {elapsed:.1f}s elapsed")

        print(f"\nFeature extraction complete: {succeeded} succeeded, {failed} failed in {time.time() - t0:.1f}s")
    else:
        print("All songs already have up-to-date audio features!")

    # 4. Train Normalization Model & Upgrade Feature Scales
    print("\nFitting Recommendation Normalization Model...")
    normalizer = RecommendationNormalizer(db)
    state = normalizer.fit()
    normalizer.save(state)

    print("Model fitted successfully:")
    print(f"  - Version: {state.version}")
    print(f"  - Total library songs: {state.source_song_count}")
    print(f"  - Analyzed feature vectors: {state.analyzed_song_count}")
    print("  - Learned feature scales (median, IQR):")
    for feat, scale in state.feature_scales.items():
        print(f"      {feat:<24} median={scale.median:<10.2f} iqr={scale.iqr:<10.2f} count={scale.count}")

    # 5. Offline Evaluation & Recommendation Quality Check
    if evaluate and state.analyzed_song_count >= 2:
        print("\n" + "=" * 60)
        print("  RECOMMENDATION MODEL EVALUATION & PLAYLIST TESTING")
        print("=" * 60)
        engine = RecommendationEngine(db)

        # Sample 3 test songs to inspect recommendation output
        sample_rows = db.fetchall(
            """
            SELECT s.id, s.title, ar.name as artist, af.bpm, af.mood_scores
            FROM songs s
            JOIN artists ar ON ar.id = s.artist_id
            JOIN audio_features af ON af.song_id = s.id
            WHERE s.is_missing = 0
            ORDER BY RANDOM()
            LIMIT 3
            """
        )

        for row in sample_rows:
            song_id = row["id"]
            title = row["title"]
            artist = row["artist"]
            mood_scores = json.loads(row["mood_scores"]) if row["mood_scores"] else {}
            top_mood = max(mood_scores.items(), key=lambda x: x[1])[0] if mood_scores else "unknown"

            print(f"\nSeed Track: '{title}' by {artist} (BPM: {row['bpm']:.1f}, Top Mood: {top_mood})")
            print("-" * 60)

            rec_res = engine.recommend(song_id, limit=4)
            recs = rec_res.get("recommendations", [])
            for rec in recs:
                r_song = rec["song"]
                r_score = rec["score"]
                r_reasons = ", ".join(rec["reasons"][:3])
                b = rec.get("breakdown", {})
                print(f"  #{rec['rank']} [{r_score * 100:.1f}% match] '{r_song['title']}' by {r_song['artist_name']}")
                print(f"      Reasons: {r_reasons}")
                print(f"      Signals: audio={b.get('audio', 0):.2f}, mood={b.get('mood', 0):.2f}, artist={b.get('artist', 0):.2f}")

    print("\n" + "=" * 60)
    print("  MODEL TRAINING COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and upgrade recommendation model")
    parser.add_argument("--folder", type=str, default=None, help="Audio folder to scan and train on")
    parser.add_argument("--workers", type=int, default=4, help="Number of analysis worker threads")
    parser.add_argument("--force", action="store_true", help="Re-analyze all songs")
    parser.add_argument("--no-eval", action="store_true", help="Skip evaluation")
    args = parser.parse_args()

    train(folder=args.folder, workers=args.workers, evaluate=not args.no_eval, force=args.force)
