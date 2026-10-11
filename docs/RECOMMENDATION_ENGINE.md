# Recommendation Engine

> **This is a content-based baseline recommender and does not yet learn
> individual user preferences.**

---

## 1. Current Architecture

The recommender lives in `backend/app/recommendation/` and is invoked from
the FastAPI endpoint `GET /api/recommendations/{song_id}?limit=N`.

```
Currently playing song
        │
        ▼
CandidateGenerator          ← loads all eligible songs from SQLite
        │
        ▼
Eligibility filter          ← drops: current song, missing files, duplicates
        │
        ▼
RecommendationFeatureBuilder
  builds SongFeatureVector  ← unified feature representation for each candidate
        │
        ▼
RecommendationNormalizer    ← loads/fits robust scaling statistics (median/IQR)
        │
        ▼
Scoring (per candidate)
  ├── audio_similarity()    ← tempo · energy · timbre · harmony
  ├── mood_similarity()     ← cosine on 9-dim mood vector
  └── metadata_similarity() ← genre · artist · album · language · other
        │
        ▼
Weighted sum (RecommendationWeights from config.py)
        │
        ▼
Stage 1: sort by relevance score (descending)
        │
        ▼
Stage 2: apply_diversity()  ← penalty for artist repetition
        │
        ▼
Stage 3: slice top-N, assign ranks, generate reason chips
        │
        ▼
RecommendationAudit         ← persists results in recommendation_history
        │
        ▼
JSON response to frontend
```

**Algorithm version:** `part2b-v1`  
**Config version:** `weights-v2`

---

## 2. Feature Representation

All data for a song is gathered into a single `SongFeatureVector` dataclass
(`backend/app/recommendation/models.py`). It is the single source of truth
for the recommender — no other layer reads raw database fields directly.

| Category | Fields | Source table |
|---|---|---|
| **Audio scalars** | `bpm`, `tempo`, `rms_energy`, `loudness`, `spectral_centroid`, `spectral_bandwidth`, `spectral_contrast_mean`, `zero_crossing_rate` | `audio_features` |
| **Audio vectors** | `mfcc_mean` (13-dim), `chroma_mean` (12-dim) | `audio_features` |
| **Audio categorical** | `estimated_key`, `key_confidence` | `audio_features` |
| **Metadata categorical** | `genres`, `artist_id`, `album_id`, `language`, `composer`, `album_artist` | `songs`, `song_genres`, `song_metadata` |
| **Metadata scalar** | `album_year`, `duration` | `albums`, `songs` |
| **Mood probabilistic** | `mood_scores` — dict of 9 labels → float | `audio_features.mood_scores` |
| **Playback state** | `is_favorite`, `play_count` | `songs` |

`SongFeatureVector` exposes helper predicates: `has_audio_features()`,
`has_mood()`, `has_metadata()`.

---

## 3. Audio Similarity

Audio similarity is broken into four interpretable components. This avoids
the trap of concatenating everything into one vector and running blind cosine.

```
audio_similarity(A, B) = weighted_avg([tempo, energy, timbre, harmony])
  weights: tempo=0.30, energy=0.25, timbre=0.25, harmony=0.20
```

### 3a. Tempo similarity

```
tempo_sim = mean(
    scalar_sim(bpm_A, bpm_B),
    scalar_sim(tempo_A, tempo_B)
)
```

Both `bpm` and `tempo` encode beats-per-minute from the same librosa tracker,
so they move together. Averaging reduces per-value noise.

### 3b. Energy similarity

```
energy_sim = mean(
    scalar_sim(rms_energy_A, rms_energy_B),
    scalar_sim(loudness_A, loudness_B),
    scalar_sim(zero_crossing_rate_A, zero_crossing_rate_B)
)
```

RMS measures signal power, loudness is dB-scale RMS, ZCR correlates with
percussiveness and brightness. Together they capture subjective loudness and
liveliness.

### 3c. Timbral similarity

```
timbre_sim = mean(
    scalar_sim(spectral_centroid),
    scalar_sim(spectral_bandwidth),
    scalar_sim(spectral_contrast_mean),
    clamp_to_0(cosine(mfcc_A, mfcc_B))
)
```

MFCCs are the most powerful timbral descriptor: 13 coefficients capture the
"colour" of the sound regardless of pitch. Cosine is clamped to `[0, 1]`
(see §3e).

### 3d. Harmonic similarity

```
harmony_sim = mean(
    clamp_to_0(cosine(chroma_A, chroma_B)),
    key_sim(estimated_key_A, estimated_key_B)
)
```

Chroma captures the 12-pitch-class energy distribution. Key similarity is
a 3-level rule: same key = 1.0, same root note but different mode = 0.5,
different = 0.0.

### 3e. Why cosine is clamped to [0, 1]

Raw cosine lies in `[-1, 1]`. A negative value means the vectors are
anti-correlated — their features point in opposite directions.

For **similarity** semantics, anti-correlation should count as zero, not as
negative evidence that drags down averages. Allowing unclamped negatives in
`mean_similarity()` would produce misleading timbral and harmonic scores.

Example: MFCC cosine = −0.3 (very different timbre). Without clamping, it
reduces the `timbre` average even though the other spectral features might
agree. With clamping, it contributes 0 (no positive evidence), which is the
correct interpretation.

---

## 4. Metadata Similarity

```
metadata_similarity(A, B) = weighted_avg([artist, album, genre, language, other])
  weights: artist=0.24, album=0.20, genre=0.28, language=0.12, other=0.16
```

| Signal | Method | Score | Rationale |
|---|---|---|---|
| Artist | Binary (`artist_id` match) | 0 or 1 | Same artist = very strong signal |
| Album | Tiered (`album_id` → `album_artist`) | 1.0 / 0.35 / 0 | Same album strong; same album-artist moderate |
| Genre | Jaccard index on genre name sets | [0, 1] | Partial overlap contributes |
| Language | Exact casefold match | 0 or 1 | Listening in a language you understand matters |
| Other | avg(composer, year, duration) | [0, 1] | Weak signals combined |

Year similarity uses exponential decay: `exp(-Δyears / 6)` capped at 20 years.  
Duration similarity: `exp(-Δseconds / 75)` capped at 600 seconds.

---

## 5. Mood Similarity

```
mood_similarity(A, B) = max(0, cosine(mood_vector_A, mood_vector_B))
```

Mood is stored as a probability distribution over 9 labels:
`romantic, sad, happy, calm, energetic, party, melancholic, peaceful, motivational`.

These are produced by `mood_estimator.py` — a transparent heuristic mapping
from audio features (BPM, energy, loudness, ZCR, spectral centroid) to
pseudo-probabilities. **It is not a trained classifier.**

Cosine similarity on probability vectors is well-motivated: two songs with
`happy=0.9` are closer than one with `happy=0.9` vs `sad=0.9`. The cosine
captures the shape of the distribution, not just the peak.

Clamped to `[0, 1]` for consistency. In practice, mood vectors are
non-negative so the raw cosine is already ≥ 0; the clamp is a safety guard.

If either song has no mood data: `mood_similarity = None` → excluded from
weighted average denominator.

---

## 6. Normalization

Raw feature values cannot be compared directly because they live on
completely different scales:

```
BPM            ≈ 60–200     (large absolute values)
RMS energy     ≈ 0.01–0.3   (very small)
Loudness (dB)  ≈ -40 to -3  (negative, large range)
Spectral cen.  ≈ 500–6000   (very large)
```

### Method: Robust Median-IQR Scaling

```
scaled_value = (raw_value − median) / IQR
```

Where `IQR` = 75th percentile − 25th percentile of all analyzed songs.

### Why Robust?

Unlike Z-score (mean/std), median-IQR is resistant to outliers. Music
libraries often have extreme values — extremely fast or slow songs that
would inflate the standard deviation and compress everything else.

### Scalar Similarity

After scaling, similarity is computed as exponential decay of the absolute
difference:

```
sim(a, b) = exp(-min(|scaled_a - scaled_b|, 8.0))
```

This maps 0 difference → 1.0, large difference → approaches 0.

### Fitting and Persistence

- Parameters are fit on **all analyzed songs** in the library.
- Persisted in `settings.recommendation_normalization_v1` (SQLite JSON).
- Staleness check: if `source_song_count` or `analyzed_song_count` changed,
  the normalizer re-fits automatically on next recommendation request.
- Fallback scales (hardcoded per-feature in `normalization.py`) are used if
  IQR ≈ 0 (e.g. all songs have identical BPM) or no analyzed songs exist.

---

## 7. Candidate Generation

Implemented in `candidate_generator.py` and `feature_builder.py`.

**Included:** all non-missing songs in the library except the current song.

**Excluded:**
- Current song (by `song_id`)
- Songs marked `is_missing = 1`
- Songs in `duplicate_candidates` table linked to the current song
- Songs with the same `file_hash` as the current song

No pre-filtering by audio proximity (no ANN/FAISS). Comparing all analyzed
songs is acceptable at current library scale and keeps the system simple and
inspectable.

Candidates with a final score ≤ 0 are dropped after scoring.

---

## 8. Ranking

Three-stage pipeline:

**Stage 1 — Relevance sort:**
```
sort by: score DESC, artist_name ASC, title ASC
```

**Stage 2 — Diversity re-ranking** (see §10):
```
apply_diversity(items, max_per_artist, penalty)
re-sort by: effective_score DESC
```

**Stage 3 — Slice and assign ranks:**
```
top = ranked[:limit]
for i, item in enumerate(top): item.rank = i + 1
```

---

## 9. Weight Configuration

All weights are in `backend/app/recommendation/config.py`:

```python
class RecommendationWeights:
    audio:    float = 0.40   # librosa audio features
    mood:     float = 0.25   # heuristic mood vector
    genre:    float = 0.15   # tag-based genre overlap
    artist:   float = 0.08   # same artist signal
    language: float = 0.05   # same language signal
    album:    float = 0.04   # same album / album artist
    other:    float = 0.03   # composer, year, duration
```

These are **engineering starting values, not claimed optimal weights**.

Missing components are excluded from both numerator and denominator of the
weighted average, so unavailable signals don't penalise candidates.

**Weights sum to 1.0** here, but this is not required — the code normalises
by `sum(active_weights)`.

### Running an Experiment

```python
from app.recommendation.config import RecommendationWeights
from app.recommendation.recommender import RecommendationEngine
from app.db.connection import db

audio_only = RecommendationEngine(
    db,
    weights=RecommendationWeights(
        audio=1.0, mood=0.0, genre=0.0,
        artist=0.0, language=0.0, album=0.0, other=0.0,
    )
)
result = audio_only.recommend(song_id=42, limit=10)
```

See also: `scripts/evaluate_recommender.py` for a full Config A vs Config B comparison.

---

## 10. Diversity

After relevance ranking, `apply_diversity()` reduces same-artist repetition.

### Algorithm

```
artist_counts = {}
for item in sorted_by_score:
    count = artist_counts.get(artist_id, 0)
    if count >= max_per_artist:
        item.score = item.score × (1 - penalty)
    artist_counts[artist_id] += 1
re-sort by effective score
```

### Configuration (config.py)

```python
DIVERSITY_MAX_PER_ARTIST = 2     # appearances before penalty kicks in
DIVERSITY_ARTIST_PENALTY = 0.15  # 15% score reduction per excess appearance
```

### Properties

- **Conservative:** does not remove candidates, only demotes. A single-artist
  library still returns results.
- **Interpretable:** `diversity_penalty` is stored in `breakdown.details` so
  the audit log is honest.
- **Overridable per call:** `recommender.recommend(id, diversity_max_per_artist=0)`
  disables diversity entirely (used in tests that check pure relevance).
- **Unknown artist:** `artist_id=None` gets a unique sentinel per song, so
  songs without an artist tag never penalise each other.

### Effect

Without diversity: top-5 may be `[A, A, A, A, B]` if one artist dominates.  
With diversity (penalty=0.15): `[A, A, B, A, A]` — artist B rises because
the 3rd A-track gets score × 0.85.

---

## 11. Explanations

Reason chips are generated in `explanations.py` after scoring. Each reason
requires its corresponding component to exceed a threshold:

| Reason | Condition |
|---|---|
| Similar tempo | `audio_tempo` ≥ 0.78 AND `audio` ≥ 0.65 |
| Similar energy | `audio_energy` ≥ 0.74 AND `audio` ≥ 0.65 |
| Similar timbral profile | `audio_timbre` ≥ 0.70 AND `audio` ≥ 0.65 |
| Similar harmonic profile | `audio_harmony` ≥ 0.72 AND `audio` ≥ 0.65 |
| Similar mood profile | `mood` ≥ 0.65 |
| Shared genre: X | `genre` > 0 and at least one genre overlaps |
| Same artist | `artist` == 1.0 |
| Same language | `language` == 1.0 |
| Same album | `album` == 1.0 |
| Same album artist | `album` ≥ 0.35 |
| Same composer | `other_composer` == 1.0 |
| Similar release year | `other_year` ≥ 0.70 |
| Similar track length | `other_duration` ≥ 0.70 |

Up to 4 reasons are returned, sorted by their contributing score descending.
**A reason is never emitted unless its threshold is actually met.**

---

## 12. API

```
GET /api/recommendations/{song_id}?limit=5
```

Response:

```json
{
  "song_id": 42,
  "source_song": { "id": 42, "title": "...", ... },
  "recommendations": [
    {
      "rank": 1,
      "score": 0.8231,
      "reasons": ["Similar tempo", "Same genre: pop"],
      "song": { "id": 17, "title": "...", "artist_name": "...", ... },
      "breakdown": {
        "audio": 0.85,
        "mood": 0.72,
        "genre": 1.0,
        "artist": 0.0,
        ...
      }
    }
  ],
  "candidate_count": 143,
  "latency_ms": 18.4,
  "algorithm_version": "part2b-v1",
  "config_version": "weights-v2",
  "weights": { "audio": 0.40, "mood": 0.25, ... }
}
```

**Score range:** `[0.0, 1.0]` — represents combined content similarity.  
**UI display:** score × 100 shown as `"Similarity: 82%"` — this is accurate.  
**Do not interpret as:** `"82% likely to be liked"` (that would require user
feedback data).

Each recommendation run is persisted in `recommendation_history` for future
offline analysis.

---

## 13. Performance

Current implementation does a full scan of all analyzed songs per request.

| Library size | Typical latency | Notes |
|---|---|---|
| < 500 songs | < 20 ms | Easily fits in memory |
| 500–2000 songs | 20–80 ms | Still fast |
| > 2000 songs | Profile first | May need caching or ANN indexing |

Normalization parameters are cached in SQLite and only refitted when the
library changes, so they do not add per-request latency.

Run `scripts/evaluate_recommender.py` against your actual library for
measured latency with your dataset.

---

## 14. Limitations

1. **No personalization.** The system does not learn from play history, skips,
   or explicit ratings. Every user gets the same results.

2. **Mood is heuristic.** The mood estimator maps BPM/energy/loudness to
   pseudo-probabilities via hand-tuned formulas. It is NOT a trained classifier
   and may be inaccurate for unusual songs.

3. **Language is sparse.** Language is extracted from `raw_json` metadata if
   present. Most local libraries do not have language tags; the language signal
   will be `None` for most songs.

4. **Genre quality varies.** Genre depends on embedded tags or MusicBrainz
   enrichment. Poorly tagged libraries will have weak genre signals.

5. **Weights are unvalidated.** The baseline weights are not derived from user
   study data. They are reasonable engineering estimates.

6. **Diversity is conservative.** The penalty-based approach never removes
   candidates. In small single-artist libraries, all results may still be from
   one artist. This is by design.

7. **Key estimation is approximate.** The Krumhansl-Schmuckler key estimator
   is a heuristic that works well for tonal music but poorly for atonal, modal,
   or electronic genres.

---

## 15. Future Improvements (Next Phase)

The recommended next phase is **User Behavior + Implicit Feedback + Personalization**.

Specific improvements:

- **User feedback loop:** record play-throughs vs skips, use as implicit labels
- **Learned weights:** fit `RecommendationWeights` from feedback data
- **Trained mood classifier:** replace heuristic with audio ML model
- **Vector caching:** pre-compute and cache normalized feature vectors
- **ANN indexing:** add approximate nearest-neighbour search (e.g. FAISS) for
  very large libraries (> 5000 songs)
- **Language enrichment:** improve language detection via text metadata
- **Diversity controls:** progressive penalty (3rd occurrence = 15%, 4th = 30%, ...)
- **Collaborative signals:** add play-history co-occurrence for users with
  multiple listening sessions
