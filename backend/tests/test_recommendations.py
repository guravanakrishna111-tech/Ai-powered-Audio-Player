"""
Tests for the Part 2B recommendation engine.

Windows tmp_path note
---------------------
The three integration tests that previously used pytest's ``tmp_path`` fixture
failed on this machine with::

    PermissionError: [WinError 5] Access is denied:
        'C:\\Users\\gurav\\AppData\\Local\\Temp\\pytest-of-gurav'

Root cause: the Windows TEMP directory has restricted ACLs on this account.
Fix: create a temporary database file directly in the workspace's own
``backend/data/`` test subdirectory, which we have write access to, and
clean it up in a finalizer.  We no longer depend on the system TEMP dir.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.connection import Database
from app.recommendation.config import RecommendationWeights
from app.recommendation.diversity import apply_diversity
from app.recommendation.models import FeatureScale, NormalizationState, RecommendationItem, ScoreBreakdown, SongFeatureVector
from app.recommendation.normalization import RecommendationNormalizer
from app.recommendation.recommender import RecommendationEngine
from app.recommendation.similarity import (
    audio_similarity,
    cosine_similarity,
    jaccard_similarity,
    metadata_similarity,
    mood_similarity,
)
from app.main import app
from app.api.routes import recommendations as recommendations_route


# ── Helpers ────────────────────────────────────────────────────────────────

# Stable writable directory: use the backend/data folder which is always
# accessible.  Fall back to a random sub-folder of the current working dir.
_WORKSPACE_DATA = Path(__file__).parent.parent / "data"


def _make_db(request) -> Database:
    """Create a fresh in-process SQLite Database and register cleanup."""
    _WORKSPACE_DATA.mkdir(parents=True, exist_ok=True)
    db_path = _WORKSPACE_DATA / f"_test_{uuid.uuid4().hex}.db"

    def _cleanup():
        try:
            db_path.unlink(missing_ok=True)
        except OSError:
            pass  # best-effort

    request.addfinalizer(_cleanup)
    return Database(db_path)


def _insert_song(
    db: Database,
    *,
    song_id: int,
    title: str,
    artist_id: int,
    album_id: int,
    artist_name: str,
    album_title: str,
    genre_name: str,
    bpm: float,
    tempo: float,
    rms_energy: float,
    loudness: float,
    spectral_centroid: float,
    spectral_bandwidth: float,
    spectral_contrast_mean: float,
    zero_crossing_rate: float,
    mfcc: list[float],
    chroma: list[float],
    mood: dict[str, float],
    file_hash: str | None = None,
    is_missing: int = 0,
    language: str | None = None,
    composer: str | None = None,
    duration: float = 180.0,
    album_year: int = 2020,
) -> None:
    genre_row = db.fetchone("SELECT id FROM genres WHERE normalized_name = ?", (genre_name.casefold(),))
    if genre_row:
        genre_id = int(genre_row["id"])
    else:
        cur = db.execute(
            "INSERT INTO genres (name, normalized_name) VALUES (?, ?)",
            (genre_name, genre_name.casefold()),
        )
        genre_id = int(cur.lastrowid)

    db.execute(
        "INSERT OR IGNORE INTO artists (id, name, normalized_name) VALUES (?, ?, ?)",
        (artist_id, artist_name, artist_name.casefold()),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO albums (id, title, normalized_title, album_artist_id, year)
        VALUES (?, ?, ?, ?, ?)
        """,
        (album_id, album_title, album_title.casefold(), artist_id, album_year),
    )
    db.execute(
        """
        INSERT INTO songs (
            id, file_path, file_size, file_mtime, file_hash, title, artist_id, album_id,
            track_number, disc_number, duration, artwork_path, analysis_status,
            is_missing, is_favorite, play_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """,
        (
            song_id,
            f"C:/music/{title}_{song_id}.mp3",
            1024,
            1000.0 + song_id,
            file_hash,
            title,
            artist_id,
            album_id,
            song_id,
            1,
            duration,
            None,
            "complete",
            is_missing,
        ),
    )
    db.execute(
        """
        INSERT INTO song_metadata (
            song_id, album_artist, composer, comments, lyrics,
            bitrate, sample_rate, channels, codec, source, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'embedded', ?)
        """,
        (
            song_id,
            artist_name,
            composer,
            None,
            None,
            320,
            44100,
            2,
            "MP3",
            json.dumps({"language": language}) if language else json.dumps({}),
        ),
    )
    db.execute(
        """
        INSERT INTO song_genres (song_id, genre_id) VALUES (?, ?)
        """,
        (song_id, genre_id),
    )
    db.execute(
        """
        INSERT INTO audio_features (
            song_id, bpm, tempo, rms_energy, loudness,
            spectral_centroid, spectral_bandwidth, spectral_contrast_mean,
            zero_crossing_rate, mfcc_mean, chroma_mean,
            estimated_key, key_confidence, mood_scores, feature_vector,
            analyzed_at, analyzer_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            song_id,
            bpm,
            tempo,
            rms_energy,
            loudness,
            spectral_centroid,
            spectral_bandwidth,
            spectral_contrast_mean,
            zero_crossing_rate,
            json.dumps(mfcc),
            json.dumps(chroma),
            "C major",
            0.9,
            json.dumps(mood),
            json.dumps([bpm, rms_energy, loudness]),
            1234.0 + song_id,
            "0.1.0",
        ),
    )


def _build_feature(
    song_id: int,
    title: str,
    artist_id: int,
    album_id: int,
    genres: tuple[str, ...],
    bpm: float,
    rms_energy: float,
    mood: dict[str, float],
) -> SongFeatureVector:
    return SongFeatureVector(
        song_id=song_id,
        file_path=f"C:/music/{title}.mp3",
        title=title,
        artist_id=artist_id,
        artist_name=f"Artist {artist_id}",
        album_id=album_id,
        album_title=f"Album {album_id}",
        album_year=2020,
        track_number=1,
        disc_number=1,
        duration=180.0,
        artwork_path=None,
        analysis_status="complete",
        file_hash=None,
        is_favorite=0,
        play_count=0,
        genres=genres,
        composer=None,
        album_artist=f"Artist {artist_id}",
        language="hindi",
        bpm=bpm,
        tempo=bpm,
        rms_energy=rms_energy,
        loudness=-12.0,
        spectral_centroid=2500.0,
        spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5,
        zero_crossing_rate=0.05,
        mfcc_mean=tuple(float(v) for v in range(1, 14)),
        chroma_mean=tuple(float(v) for v in range(1, 13)),
        estimated_key="C major",
        key_confidence=0.9,
        mood_scores=mood,
    )


def _make_item(song_id: int, artist_id: int, score: float) -> RecommendationItem:
    """Minimal RecommendationItem for diversity unit tests."""
    fv = _build_feature(song_id, f"Song{song_id}", artist_id, song_id, ("rock",), 120.0, 0.5, {"happy": 1.0})
    bd = ScoreBreakdown(score=score)
    return RecommendationItem(rank=0, score=score, reasons=[], song=fv, breakdown=bd)


# ── Unit tests ─────────────────────────────────────────────────────────────

def test_normalization_scales_feature_values():
    state = NormalizationState(
        version="test",
        source_song_count=3,
        analyzed_song_count=3,
        feature_scales={"bpm": FeatureScale(median=120.0, iqr=20.0, count=3)},
        updated_at=0.0,
    )
    _WORKSPACE_DATA.mkdir(parents=True, exist_ok=True)
    tmp_db = _WORKSPACE_DATA / f"_tmp_norm_{uuid.uuid4().hex}.db"
    try:
        normalizer = RecommendationNormalizer(Database(tmp_db))
        assert normalizer.scale_with_state(state, "bpm", 120.0) == 0.0
        assert normalizer.scale_with_state(state, "bpm", 140.0) == 1.0
        assert normalizer.similarity_with_state(state, "bpm", 120.0, 120.0) == 1.0
    finally:
        tmp_db.unlink(missing_ok=True)


def test_similarity_functions_handle_identical_and_missing_values():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity(None, [1.0, 0.0]) is None
    assert jaccard_similarity(["rock", "pop"], ["rock"]) == 0.5
    assert jaccard_similarity([], ["rock"]) is None


def test_metadata_and_mood_similarity_respect_feature_presence():
    source = _build_feature(1, "Song A", 1, 1, ("rock",), 120.0, 0.6, {"happy": 0.8, "calm": 0.2})
    same_artist = _build_feature(2, "Song B", 1, 2, ("rock",), 122.0, 0.58, {"happy": 0.78, "calm": 0.22})
    different_artist = _build_feature(3, "Song C", 3, 3, ("jazz",), 90.0, 0.25, {"sad": 0.9, "calm": 0.1})

    _, same_parts = metadata_similarity(source, same_artist)
    _, diff_parts = metadata_similarity(source, different_artist)

    assert same_parts["artist"] == 1.0
    assert diff_parts["artist"] == 0.0
    assert same_parts["genre"] > diff_parts["genre"]
    assert mood_similarity(source, same_artist) > mood_similarity(source, different_artist)


def test_cosine_similarity_clamped_non_negative():
    """_vector_cosine must return >= 0 even when raw cosine is negative."""
    # Anti-correlated vectors → raw cosine is negative.
    raw = cosine_similarity([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])
    assert raw == -1.0, "Baseline: raw cosine can be negative"

    # After clamping via _vector_cosine the timbre/harmony score must be >= 0.
    from app.recommendation.similarity import _vector_cosine
    clamped = _vector_cosine((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
    assert clamped == 0.0, "Clamped vector cosine must floor at 0.0"

    clamped_identical = _vector_cosine((1.0, 1.0), (1.0, 1.0))
    assert clamped_identical == pytest.approx(1.0), "Identical vectors still give 1.0"


def test_mood_similarity_clamped_non_negative():
    """mood_similarity must return a value in [0, 1], never negative."""
    a = _build_feature(1, "A", 1, 1, (), 120.0, 0.5, {"happy": 1.0, "sad": 0.0})
    b = _build_feature(2, "B", 2, 2, (), 90.0, 0.3, {"happy": 0.0, "sad": 1.0})
    result = mood_similarity(a, b)
    # These mood vectors are orthogonal → cosine = 0 (not negative).
    assert result is not None
    assert 0.0 <= result <= 1.0, f"mood_similarity must be in [0, 1], got {result}"


def test_mood_missing_data_does_not_crash():
    """Songs without mood data must not cause an error."""
    a = _build_feature(1, "A", 1, 1, (), 120.0, 0.5, {})  # no mood
    b = _build_feature(2, "B", 2, 2, (), 90.0, 0.3, {"happy": 0.7})
    assert mood_similarity(a, b) is None
    assert mood_similarity(a, a) is None


def test_score_stays_in_zero_to_one_range(request):
    """Final recommendation scores must be in [0.0, 1.0]."""
    db = _make_db(request)
    base = dict(
        bpm=120.0, tempo=121.0, rms_energy=0.60, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12,
        mood={"happy": 0.8, "calm": 0.2},
    )
    for i in range(1, 6):
        _insert_song(
            db, song_id=i, title=f"Track{i}", artist_id=i, album_id=i,
            artist_name=f"Artist{i}", album_title=f"Album{i}", genre_name="rock",
            **base,
        )
    result = RecommendationEngine(db).recommend(1, limit=5)
    for rec in result["recommendations"]:
        score = rec["score"]
        assert 0.0 <= score <= 1.0, f"Score {score} out of range [0, 1]"


def test_diversity_unit_apply_diversity():
    """apply_diversity should demote 3rd+ occurrences of same artist."""
    items = [
        _make_item(1, artist_id=10, score=0.90),
        _make_item(2, artist_id=10, score=0.85),
        _make_item(3, artist_id=10, score=0.80),  # 3rd from artist 10 → penalised
        _make_item(4, artist_id=20, score=0.75),
        _make_item(5, artist_id=10, score=0.70),  # 4th from artist 10 → penalised
    ]
    result = apply_diversity(items, max_per_artist=2, penalty=0.15)

    scores = {item.song.song_id: item.score for item in result}
    assert scores[1] == pytest.approx(0.90)
    assert scores[2] == pytest.approx(0.85)
    # song 3 is 3rd from artist 10 → score × 0.85
    assert scores[3] == pytest.approx(0.80 * 0.85, abs=1e-4)
    # song 4 is 1st from artist 20 → no penalty
    assert scores[4] == pytest.approx(0.75)
    # song 5 is 4th from artist 10 → score × 0.85
    assert scores[5] == pytest.approx(0.70 * 0.85, abs=1e-4)


def test_diversity_zero_disables_reranking():
    """max_per_artist=0 should return list unchanged."""
    items = [_make_item(i, artist_id=10, score=1.0 - i * 0.1) for i in range(1, 5)]
    result = apply_diversity(items, max_per_artist=0, penalty=0.15)
    assert [i.song.song_id for i in result] == [1, 2, 3, 4]


def test_diversity_unknown_artist_no_penalty():
    """Songs with artist_id=None must not accumulate against each other."""
    items = [
        _make_item(i, artist_id=i, score=0.80) for i in range(1, 5)
    ]
    # Patch artist_id to None for all
    for item in items:
        object.__setattr__(item.song, "artist_id", None)
    result = apply_diversity(items, max_per_artist=2, penalty=0.15)
    # All should be unpunished since each None gets a unique sentinel
    for item in result:
        assert item.score == pytest.approx(0.80)


def test_explanation_reasons_match_contributing_features(request):
    """Reasons must only appear when the corresponding component actually fired."""
    db = _make_db(request)
    # Source song: rock, Artist 1
    _insert_song(
        db, song_id=1, title="Source", artist_id=1, album_id=1,
        artist_name="Artist One", album_title="Album One", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.60, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12,
        mood={"happy": 0.8, "calm": 0.2},
        language="hindi",
    )
    # Candidate: different artist, different genre, very different audio
    _insert_song(
        db, song_id=2, title="Different", artist_id=99, album_id=99,
        artist_name="Artist Ninety", album_title="Album Z", genre_name="jazz",
        bpm=60.0, tempo=60.0, rms_energy=0.05, loudness=-30.0,
        spectral_centroid=800.0, spectral_bandwidth=400.0,
        spectral_contrast_mean=1.0, zero_crossing_rate=0.01,
        mfcc=[10.0] * 13, chroma=[5.0] * 12,
        mood={"sad": 0.9, "calm": 0.1},
        language="english",
    )
    result = RecommendationEngine(db).recommend(1, limit=5)
    recs = result["recommendations"]
    assert recs, "Expected at least one recommendation"
    for rec in recs:
        reasons = rec["reasons"]
        breakdown = rec["breakdown"]
        # Verify: if "Same artist" is in reasons, artist score must be 1.0
        if "Same artist" in reasons:
            assert breakdown.get("artist") == pytest.approx(1.0)
        # Verify: "Same artist" not in reasons when artist score is 0.0
        if breakdown.get("artist") == pytest.approx(0.0):
            assert "Same artist" not in reasons


# ── Integration tests (use workspace-local tmpdir) ─────────────────────────

def test_final_scoring_changes_with_weights(request):
    db = _make_db(request)
    _insert_song(
        db, song_id=1, title="Source", artist_id=1, album_id=1,
        artist_name="Artist One", album_title="Album One", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.60, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.8, "calm": 0.2},
    )
    _insert_song(
        db, song_id=2, title="AudioMatch", artist_id=2, album_id=2,
        artist_name="Artist Two", album_title="Album Two", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.59, loudness=-11.2,
        spectral_centroid=2510.0, spectral_bandwidth=1390.0,
        spectral_contrast_mean=3.6, zero_crossing_rate=0.051,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.79, "calm": 0.21},
    )
    _insert_song(
        db, song_id=3, title="ArtistMatch", artist_id=1, album_id=3,
        artist_name="Artist One", album_title="Album Three", genre_name="rock",
        bpm=95.0, tempo=94.0, rms_energy=0.25, loudness=-18.0,
        spectral_centroid=1800.0, spectral_bandwidth=1000.0,
        spectral_contrast_mean=2.0, zero_crossing_rate=0.02,
        mfcc=[0.1] * 13, chroma=[0.1] * 12, mood={"sad": 0.8, "calm": 0.2},
    )

    high_audio = RecommendationEngine(
        db,
        weights=RecommendationWeights(audio=0.80, mood=0.05, genre=0.05, artist=0.05, language=0.02, album=0.02, other=0.01),
    ).recommend(1, limit=5, diversity_max_per_artist=0)  # disable diversity for this test

    high_artist = RecommendationEngine(
        db,
        weights=RecommendationWeights(audio=0.05, mood=0.05, genre=0.05, artist=0.70, language=0.05, album=0.05, other=0.05),
    ).recommend(1, limit=5, diversity_max_per_artist=0)

    assert high_audio["recommendations"][0]["song"]["id"] == 2
    assert high_artist["recommendations"][0]["song"]["id"] == 3


def test_candidate_generation_excludes_current_missing_and_duplicates(request):
    db = _make_db(request)
    _insert_song(
        db, song_id=1, title="Source", artist_id=1, album_id=1,
        artist_name="Artist One", album_title="Album One", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.6, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.8, "calm": 0.2},
        file_hash="same-hash",
    )
    _insert_song(
        db, song_id=2, title="Valid", artist_id=2, album_id=2,
        artist_name="Artist Two", album_title="Album Two", genre_name="rock",
        bpm=121.0, tempo=121.0, rms_energy=0.59, loudness=-11.2,
        spectral_centroid=2520.0, spectral_bandwidth=1410.0,
        spectral_contrast_mean=3.4, zero_crossing_rate=0.051,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.77, "calm": 0.23},
    )
    _insert_song(
        db, song_id=3, title="Duplicate", artist_id=3, album_id=3,
        artist_name="Artist Three", album_title="Album Three", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.6, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.8, "calm": 0.2},
        file_hash="same-hash",
    )
    _insert_song(
        db, song_id=4, title="Missing", artist_id=4, album_id=4,
        artist_name="Artist Four", album_title="Album Four", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.6, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.8, "calm": 0.2},
        is_missing=1,
    )
    db.execute(
        "INSERT INTO duplicate_candidates (song_id_a, song_id_b, similarity_score, match_reason) VALUES (?, ?, ?, ?)",
        (1, 3, 1.0, "identical_file_hash"),
    )

    result = RecommendationEngine(db).recommend(1, limit=10)
    recommended_ids = [item["song"]["id"] for item in result["recommendations"]]
    assert 1 not in recommended_ids
    assert 3 not in recommended_ids
    assert 4 not in recommended_ids
    assert 2 in recommended_ids


def test_diversity_limits_same_artist_in_results(request):
    """Top-N must not be overwhelmed by a single artist when alternatives exist."""
    db = _make_db(request)
    # Source song from artist 1
    _insert_song(
        db, song_id=1, title="Source", artist_id=1, album_id=1,
        artist_name="ArtistA", album_title="Album1", genre_name="pop",
        bpm=120.0, tempo=120.0, rms_energy=0.5, loudness=-12.0,
        spectral_centroid=2000.0, spectral_bandwidth=1200.0,
        spectral_contrast_mean=3.0, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.9},
    )
    # 4 very similar songs from artist 2 (same audio features)
    for i in range(2, 6):
        _insert_song(
            db, song_id=i, title=f"TrackA{i}", artist_id=2, album_id=2,
            artist_name="ArtistA2", album_title="AlbumA", genre_name="pop",
            bpm=120.0, tempo=120.0, rms_energy=0.5, loudness=-12.0,
            spectral_centroid=2000.0, spectral_bandwidth=1200.0,
            spectral_contrast_mean=3.0, zero_crossing_rate=0.05,
            mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.9},
        )
    # 1 song from a different artist (slightly less similar audio)
    _insert_song(
        db, song_id=6, title="OtherArtistTrack", artist_id=3, album_id=3,
        artist_name="ArtistB", album_title="AlbumB", genre_name="pop",
        bpm=118.0, tempo=118.0, rms_energy=0.48, loudness=-13.0,
        spectral_centroid=1950.0, spectral_bandwidth=1180.0,
        spectral_contrast_mean=2.9, zero_crossing_rate=0.048,
        mfcc=[0.95] * 13, chroma=[0.95] * 12, mood={"happy": 0.88},
    )

    result_diversity = RecommendationEngine(db).recommend(1, limit=5, diversity_penalty=0.50)
    result_no_diversity = RecommendationEngine(db).recommend(1, limit=5, diversity_max_per_artist=0)

    recs_d = result_diversity["recommendations"]
    recs_nd = result_no_diversity["recommendations"]

    artist_ids_d = [r["song"]["artist_id"] for r in recs_d]
    artist_ids_nd = [r["song"]["artist_id"] for r in recs_nd]

    # Without diversity: artist 3 should be last (lower audio similarity).
    # With a 50% penalty: penalised artist-2 tracks must drop enough to let
    # artist-3 rise above them in the ranking.
    # The key assertion: artist-3 must appear EARLIER with diversity than without.
    pos_d = artist_ids_d.index(3) if 3 in artist_ids_d else len(artist_ids_d)
    pos_nd = artist_ids_nd.index(3) if 3 in artist_ids_nd else len(artist_ids_nd)

    assert 3 in artist_ids_d, (
        f"Artist 3 must appear in results with diversity. Got: {artist_ids_d}"
    )
    assert pos_d < pos_nd, (
        f"Diversity must move artist-3 earlier in ranking: "
        f"position with diversity={pos_d}, without={pos_nd}. "
        f"With diversity: {artist_ids_d}, without: {artist_ids_nd}"
    )



def test_api_returns_recommendations(request, monkeypatch):
    db = _make_db(request)
    _insert_song(
        db, song_id=1, title="Source", artist_id=1, album_id=1,
        artist_name="Artist One", album_title="Album One", genre_name="rock",
        bpm=120.0, tempo=121.0, rms_energy=0.60, loudness=-11.0,
        spectral_centroid=2500.0, spectral_bandwidth=1400.0,
        spectral_contrast_mean=3.5, zero_crossing_rate=0.05,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.8, "calm": 0.2},
    )
    _insert_song(
        db, song_id=2, title="Candidate", artist_id=2, album_id=2,
        artist_name="Artist Two", album_title="Album Two", genre_name="rock",
        bpm=119.0, tempo=120.0, rms_energy=0.59, loudness=-11.1,
        spectral_centroid=2490.0, spectral_bandwidth=1395.0,
        spectral_contrast_mean=3.4, zero_crossing_rate=0.051,
        mfcc=[1.0] * 13, chroma=[1.0] * 12, mood={"happy": 0.79, "calm": 0.21},
    )

    temp_engine = RecommendationEngine(db)
    monkeypatch.setattr(recommendations_route, "recommender", temp_engine)
    client = TestClient(app)

    response = client.get("/api/recommendations/1?limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["song_id"] == 1
    assert payload["recommendations"]
    assert payload["recommendations"][0]["song"]["id"] == 2
    # Verify response structure has required fields
    rec = payload["recommendations"][0]
    assert "score" in rec
    assert "reasons" in rec
    assert "song" in rec
    assert 0.0 <= rec["score"] <= 1.0
