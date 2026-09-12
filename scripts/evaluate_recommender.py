"""Offline evaluation script for the AI Audio Player recommendation engine.

Usage
-----
Run from the project root (or backend directory):

    python scripts/evaluate_recommender.py
    python scripts/evaluate_recommender.py --db path/to/library.db
    python scripts/evaluate_recommender.py --limit 10 --samples 20

What it does
------------
1. Connects to the local SQLite library database.
2. Reports library statistics: total songs, analyzed count, per-feature
   availability.
3. Samples up to ``--samples`` analyzed songs and runs the recommender
   for each.
4. Reports: latency distribution, candidate counts, recommendation counts,
   per-config comparison.
5. Compares two configurations:
   - Config A: audio-only (40% weight, all others 0%)
   - Config B: default multi-signal (audio 40%, mood 25%, …)

   The comparison is descriptive — it shows score distributions per config
   so you can decide whether multi-signal actually produces different (not
   necessarily better) results.

Note on "better"
----------------
This script does NOT claim that Config B is better than Config A.
"Better" requires ground-truth labels (e.g. human ratings or play history).
We only report objective measures: latency, candidate count, and score
distribution. Subjective quality assessment requires real user data.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# ── Allow running from project root or from backend/ ─────────────────────────
_HERE = Path(__file__).resolve().parent
for _candidate in (_HERE.parent / "backend", _HERE / "backend", _HERE.parent):
    if (_candidate / "app").is_dir():
        sys.path.insert(0, str(_candidate))
        break


def _find_default_db() -> Path | None:
    """Walk up from script location looking for a library.db."""
    search_roots = [
        _HERE.parent / "backend" / "data",
        _HERE / "backend" / "data",
        _HERE.parent / "data",
        _HERE,
    ]
    for root in search_roots:
        candidate = root / "library.db"
        if candidate.exists():
            return candidate
    # Also check the Electron app data paths on Windows
    import os
    appdata = os.getenv("APPDATA", "")
    if appdata:
        candidate = Path(appdata) / "ai-audio-player" / "library.db"
        if candidate.exists():
            return candidate
    return None


def _feature_availability(rows: list[dict]) -> dict[str, float]:
    """Return fraction of songs with each numeric feature present."""
    features = [
        "bpm", "tempo", "rms_energy", "loudness",
        "spectral_centroid", "spectral_bandwidth",
        "spectral_contrast_mean", "zero_crossing_rate",
        "mfcc_mean", "chroma_mean", "mood_scores",
    ]
    total = len(rows)
    if total == 0:
        return {f: 0.0 for f in features}
    counts: dict[str, int] = {f: 0 for f in features}
    for row in rows:
        for f in features:
            val = row.get(f)
            if val is not None and val != "" and val != "null":
                counts[f] += 1
    return {f: round(counts[f] / total, 3) for f in features}


def _run_config(engine, song_ids: list[int], limit: int, label: str) -> dict:
    latencies: list[float] = []
    candidate_counts: list[int] = []
    score_sums: list[float] = []
    top1_scores: list[float] = []
    failures = 0

    for song_id in song_ids:
        try:
            t0 = time.perf_counter()
            result = engine.recommend(song_id, limit=limit)
            latencies.append((time.perf_counter() - t0) * 1000)
            candidate_counts.append(result["candidate_count"])
            recs = result["recommendations"]
            if recs:
                scores = [r["score"] for r in recs]
                score_sums.extend(scores)
                top1_scores.append(scores[0])
        except Exception as exc:
            failures += 1
            print(f"  [{label}] song_id={song_id} FAILED: {exc}")

    return {
        "label": label,
        "samples": len(song_ids),
        "failures": failures,
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
            "median": round(statistics.median(latencies), 2) if latencies else 0,
            "p95": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 2),
            "max": round(max(latencies), 2) if latencies else 0,
        },
        "candidates": {
            "mean": round(statistics.mean(candidate_counts), 1) if candidate_counts else 0,
            "min": min(candidate_counts) if candidate_counts else 0,
            "max": max(candidate_counts) if candidate_counts else 0,
        },
        "scores": {
            "mean_top1": round(statistics.mean(top1_scores), 4) if top1_scores else 0,
            "mean_all": round(statistics.mean(score_sums), 4) if score_sums else 0,
            "min_all": round(min(score_sums), 4) if score_sums else 0,
            "max_all": round(max(score_sums), 4) if score_sums else 0,
        },
    }


def _print_report(stats: dict, config_a: dict, config_b: dict) -> None:
    sep = "─" * 60

    print(f"\n{'═' * 60}")
    print("  AI AUDIO PLAYER — Recommender Evaluation Report")
    print(f"{'═' * 60}\n")

    print("Library Statistics")
    print(sep)
    print(f"  Total songs (non-missing):  {stats['total_songs']}")
    print(f"  Analyzed songs:             {stats['analyzed_songs']}")
    print(f"  Analysis coverage:          {stats['analysis_pct']:.1f}%")
    print()

    print("Feature Availability (fraction of analyzed songs with each feature)")
    print(sep)
    for feat, frac in stats["feature_availability"].items():
        bar = "█" * int(frac * 20) + "░" * (20 - int(frac * 20))
        print(f"  {feat:<28} {bar} {frac * 100:.0f}%")
    print()

    for cfg in (config_a, config_b):
        print(f"Configuration: {cfg['label']}")
        print(sep)
        print(f"  Samples run:          {cfg['samples']}")
        print(f"  Failures:             {cfg['failures']}")
        lms = cfg["latency_ms"]
        print(f"  Latency (ms)          mean={lms['mean']}  median={lms['median']}  p95={lms['p95']}  max={lms['max']}")
        cnd = cfg["candidates"]
        print(f"  Candidates per query  mean={cnd['mean']}  min={cnd['min']}  max={cnd['max']}")
        sc = cfg["scores"]
        print(f"  Score (top-1)         mean={sc['mean_top1']}")
        print(f"  Score (all recs)      mean={sc['mean_all']}  min={sc['min_all']}  max={sc['max_all']}")
        print()

    print("Comparison Notes")
    print(sep)
    print("  Score difference (Config B − Config A, top-1 mean):",
          round(config_b["scores"]["mean_top1"] - config_a["scores"]["mean_top1"], 4))
    print()
    print("  ⚠  Score differences do not imply quality differences.")
    print("     Config B uses more signals, so scores may be lower when")
    print("     metadata signals disagree with audio signals.")
    print("     Ground-truth quality requires human ratings or play-history data.")
    print()

    print("Limitations")
    print(sep)
    print("  This is a content-based baseline. It does not learn preferences.")
    print("  Mood is a heuristic estimate, not a trained classifier.")
    print("  Language metadata may be absent for many local libraries.")
    print(f"\n{'═' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline recommender evaluation")
    parser.add_argument("--db", type=Path, default=None, help="Path to library.db")
    parser.add_argument("--limit", type=int, default=5, help="Recommendations per query")
    parser.add_argument("--samples", type=int, default=30, help="Number of songs to sample")
    args = parser.parse_args()

    db_path = args.db or _find_default_db()
    if db_path is None or not db_path.exists():
        print("ERROR: Could not find library.db. Use --db to specify the path.")
        print("  Example: python scripts/evaluate_recommender.py --db backend/data/library.db")
        sys.exit(1)

    print(f"Database: {db_path}")

    from app.db.connection import Database
    from app.recommendation.recommender import RecommendationEngine
    from app.recommendation.config import RecommendationWeights

    db = Database(db_path)

    # ── Library statistics ────────────────────────────────────────────────
    total_row = db.fetchone("SELECT COUNT(*) AS c FROM songs WHERE is_missing = 0")
    total_songs = int(total_row["c"]) if total_row else 0

    analyzed_rows = db.fetchall(
        """
        SELECT
            s.id,
            af.bpm, af.tempo, af.rms_energy, af.loudness,
            af.spectral_centroid, af.spectral_bandwidth,
            af.spectral_contrast_mean, af.zero_crossing_rate,
            af.mfcc_mean, af.chroma_mean, af.mood_scores
        FROM songs s
        JOIN audio_features af ON af.song_id = s.id
        WHERE s.is_missing = 0
        """
    )
    analyzed_songs = len(analyzed_rows)

    if analyzed_songs == 0:
        print("No analyzed songs found. Run the processing engine first.")
        sys.exit(0)

    feature_avail = _feature_availability([dict(r) for r in analyzed_rows])
    analysis_pct = round(analyzed_songs / total_songs * 100, 1) if total_songs else 0.0

    stats = {
        "total_songs": total_songs,
        "analyzed_songs": analyzed_songs,
        "analysis_pct": analysis_pct,
        "feature_availability": feature_avail,
    }

    # ── Sample songs to test ──────────────────────────────────────────────
    import random
    all_ids = [int(r["id"]) for r in analyzed_rows]
    sample_size = min(args.samples, len(all_ids))
    if sample_size < len(all_ids):
        random.shuffle(all_ids)
    song_ids = all_ids[:sample_size]

    if len(song_ids) < 2:
        print("Need at least 2 analyzed songs to generate recommendations.")
        sys.exit(0)

    print(f"Sampling {len(song_ids)} songs for evaluation (limit={args.limit})…\n")

    # ── Config A: audio-only ──────────────────────────────────────────────
    audio_only_weights = RecommendationWeights(
        audio=1.0, mood=0.0, genre=0.0, artist=0.0,
        language=0.0, album=0.0, other=0.0,
    )
    engine_a = RecommendationEngine(db, weights=audio_only_weights)
    print("Running Config A (audio-only)…")
    config_a = _run_config(engine_a, song_ids, args.limit, "Config A: audio-only")

    # ── Config B: default multi-signal ───────────────────────────────────
    engine_b = RecommendationEngine(db)  # uses DEFAULT_WEIGHTS
    print("Running Config B (multi-signal default)…")
    config_b = _run_config(engine_b, song_ids, args.limit, "Config B: multi-signal (default)")

    _print_report(stats, config_a, config_b)


if __name__ == "__main__":
    main()
